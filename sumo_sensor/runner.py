"""
Main simulation runner for SUMO sensor simulator.
Manages TraCI connection, sensor lifecycle, and simulation loop.
"""

import traci
import subprocess
import time
import signal
import sys
from typing import List, Optional, Dict

from .config import Config, SensorConfig, get_network_file
from .collector import DataCollector
from .publisher import Publisher
from .sensor import Sensor
from .utils.net_parser import (
    parse_network_file,
    get_junction_by_id,
    validate_junction_ids,
    map_junction_type_to_intersection_type,
    JunctionInfo
)
from .utils.logger import setup_logger, get_logger
from .utils.visualization import draw_all_sensor_zones, COLOR_SCHEME_DEFAULT


class SimulationRunner:
    """
    Main simulation runner.
    Orchestrates TraCI connection, sensor setup, and simulation loop.
    """

    def __init__(self, config: Config):
        """
        Initialize simulation runner.

        Args:
            config: Configuration object
        """
        self.config = config
        self.logger = get_logger()
        self.sumo_process: Optional[subprocess.Popen] = None
        self.sensors: List[Sensor] = []
        self.collector: Optional[DataCollector] = None
        self.publisher: Optional[Publisher] = None
        self.running = False

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def setup(self) -> bool:
        """
        Setup simulation: connect to SUMO, parse network, create sensors.

        Returns:
            True if setup successful, False otherwise
        """
        try:
            # Connect to SUMO
            if not self._connect_to_sumo():
                return False

            # Parse network file
            network_file = get_network_file(self.config.sumo)
            self.logger.info(f"Parsing network file: {network_file}")
            junctions = parse_network_file(network_file)
            self.logger.info(f"Found {len(junctions)} junctions in network")

            # Determine which sensors to create
            sensor_configs = self._determine_sensors(junctions)
            if not sensor_configs:
                self.logger.error("No sensors configured")
                return False

            # Initialize publisher
            self.publisher = Publisher(self.config.broker)

            # Wait for broker connection
            if not self.publisher.wait_for_connection(timeout=5.0):
                self.logger.warning("Could not connect to broker - will only print to stdout")

            # Initialize data collector (shared across all sensors)
            self.collector = DataCollector()

            # Create sensors
            for sensor_config, junction_info in sensor_configs:
                sensor = Sensor(
                    junction_id=sensor_config.sensorId,
                    junction_info=junction_info,
                    sensor_config=sensor_config,
                    collector=self.collector,
                    publisher=self.publisher
                )
                self.sensors.append(sensor)

            self.logger.info(f"Created {len(self.sensors)} sensors")

            # Draw sensor detection zones in SUMO (if enabled)
            if self.config.enable_visualization:
                self.logger.info("Drawing sensor detection zones...")
                zones_drawn = draw_all_sensor_zones(self.sensors, COLOR_SCHEME_DEFAULT, layer=0)
                self.logger.info(f"Drew {zones_drawn} sensor zones")
            else:
                self.logger.info("Visualization disabled, skipping sensor zones")

            return True

        except Exception as e:
            self.logger.error(f"Setup failed: {e}", exc_info=True)
            return False

    def _connect_to_sumo(self) -> bool:
        """
        Connect to SUMO via TraCI.

        Returns:
            True if connected, False otherwise
        """
        try:
            mode = self.config.sumo.mode
            port = self.config.sumo.port

            if mode == 'launch':
                # Launch SUMO subprocess
                sumo_cmd = [
                    self.config.sumo.binary,
                    '-c', self.config.sumo.config_file,
                    '--remote-port', str(port),
                    '--start',  # Start simulation immediately
                    '--quit-on-end',  # Quit when simulation ends
                ]

                self.logger.info(f"Launching SUMO: {' '.join(sumo_cmd)}")
                self.sumo_process = subprocess.Popen(
                    sumo_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                # Wait a bit for SUMO to start
                time.sleep(2)

                # Connect via TraCI
                self.logger.info(f"Connecting to SUMO via TraCI on port {port}")
                traci.init(port)

            elif mode == 'attach':
                # Attach to existing SUMO instance
                self.logger.info(f"Attaching to SUMO on port {port}")
                traci.init(port)

            else:
                raise ValueError(f"Invalid SUMO mode: {mode}")

            self.logger.info("Connected to SUMO")
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to SUMO: {e}", exc_info=True)
            return False

    def _determine_sensors(
        self,
        junctions: List[JunctionInfo]
    ) -> List[tuple[SensorConfig, JunctionInfo]]:
        """
        Determine which sensors to create based on config.

        Args:
            junctions: List of junctions from network

        Returns:
            List of (SensorConfig, JunctionInfo) tuples
        """
        sensor_configs = []

        if self.config.auto_discover_junctions:
            # Auto-discover: create sensor for every junction
            self.logger.info("Auto-discovering junctions...")

            for junction in junctions:
                # Map junction type to intersection type
                intersection_type = map_junction_type_to_intersection_type(
                    junction.type,
                    len(junction.incoming_edges)
                )

                sensor_config = SensorConfig(
                    sensorId=junction.id,
                    intersectionType=intersection_type,
                    detectionRadius=80.0,
                    publishInterval=1.0,
                    position={'x': junction.x, 'y': junction.y},
                    enableRawData=True,
                    enableMetrics=True
                )

                sensor_configs.append((sensor_config, junction))

            self.logger.info(f"Auto-discovered {len(sensor_configs)} sensors")

        else:
            # Manual configuration: validate and match with junctions
            sensor_ids = [s.sensorId for s in self.config.sensors]
            valid_ids, invalid_ids = validate_junction_ids(junctions, sensor_ids)

            if invalid_ids:
                self.logger.warning(
                    f"Junction IDs not found in network: {', '.join(invalid_ids)}"
                )

            for sensor_config in self.config.sensors:
                junction_info = None

                if sensor_config.sensorId in valid_ids:
                    # Junction exists in network - use actual junction info
                    junction_info = get_junction_by_id(junctions, sensor_config.sensorId)

                elif sensor_config.position is not None:
                    # Junction doesn't exist, but custom position provided - create synthetic junction
                    self.logger.info(
                        f"Creating sensor '{sensor_config.sensorId}' at custom position "
                        f"({sensor_config.position['x']}, {sensor_config.position['y']})"
                    )
                    junction_info = JunctionInfo(
                        id=sensor_config.sensorId,
                        x=sensor_config.position['x'],
                        y=sensor_config.position['y'],
                        type='custom',
                        incoming_edges=[],  # No edges for custom position
                        shape=None
                    )

                else:
                    # Junction doesn't exist and no position provided - skip
                    self.logger.error(
                        f"Sensor '{sensor_config.sensorId}' cannot be created: "
                        f"junction not found in network and no custom position provided"
                    )
                    continue

                if junction_info:
                    sensor_configs.append((sensor_config, junction_info))

            self.logger.info(f"Configured {len(sensor_configs)} sensors from config")

        return sensor_configs

    def run(self):
        """
        Run the main simulation loop.
        Advances SUMO simulation and triggers sensors at their intervals.
        """
        try:
            self.running = True
            step = 0

            self.logger.info("Starting simulation loop")

            while self.running:
                # Check if simulation has ended
                if traci.simulation.getMinExpectedNumber() <= 0:
                    self.logger.info("Simulation ended (no more vehicles)")
                    break

                # Advance SUMO simulation by one step
                traci.simulationStep()
                step += 1

                # Get current wall-clock time
                current_time = time.time()

                # Check each sensor and trigger if interval elapsed
                for sensor in self.sensors:
                    if sensor.should_publish(current_time):
                        sensor.collect_and_publish()

                # Small sleep to avoid busy loop (SUMO steps are typically 1 second)
                time.sleep(0.01)

        except traci.exceptions.FatalTraCIError as e:
            self.logger.error(f"TraCI fatal error: {e}")
            self.running = False

        except KeyboardInterrupt:
            self.logger.info("Simulation interrupted by user")
            self.running = False

        except Exception as e:
            self.logger.error(f"Simulation error: {e}", exc_info=True)
            self.running = False

        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up...")

        # Print sensor statistics
        for sensor in self.sensors:
            stats = sensor.get_stats()
            self.logger.info(
                f"Sensor {stats['junction_id']}: "
                f"publishes={stats['total_publishes']}, "
                f"errors={stats['errors']}"
            )

        # Disconnect from broker
        if self.publisher:
            self.publisher.disconnect()

        # Close TraCI connection
        try:
            traci.close()
            self.logger.info("TraCI connection closed")
        except Exception as e:
            self.logger.warning(f"Error closing TraCI: {e}")

        # Terminate SUMO process if we launched it
        if self.sumo_process:
            try:
                self.sumo_process.terminate()
                self.sumo_process.wait(timeout=5)
                self.logger.info("SUMO process terminated")
            except Exception as e:
                self.logger.warning(f"Error terminating SUMO process: {e}")
                try:
                    self.sumo_process.kill()
                except:
                    pass

        self.logger.info("Cleanup complete")


def run_simulation(config_path: str):
    """
    Run simulation from config file.

    Args:
        config_path: Path to configuration JSON file
    """
    # Setup logger
    logger = setup_logger()
    logger.info("=" * 80)
    logger.info("SUMO-RL Traffic Sensor Simulator v1.0")
    logger.info("=" * 80)

    try:
        # Load configuration
        from .config import load_config
        logger.info(f"Loading configuration from: {config_path}")
        config = load_config(config_path)
        logger.info("Configuration loaded successfully")

        # Create and setup runner
        runner = SimulationRunner(config)

        logger.info("Setting up simulation...")
        if not runner.setup():
            logger.error("Setup failed")
            sys.exit(1)

        logger.info("Setup complete")

        # Run simulation
        runner.run()

        logger.info("Simulation completed")
        sys.exit(0)

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
