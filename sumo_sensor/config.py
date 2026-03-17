"""
Configuration management for SUMO sensor simulator.
Loads and validates JSON config file.
"""

import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path

from .models import IntersectionType


@dataclass
class SumoConfig:
    """SUMO connection configuration"""
    binary: str  # Path to sumo or sumo-gui binary
    config_file: str  # Path to .sumocfg file
    mode: str  # 'launch' or 'attach'
    port: int = 8813  # TraCI port


@dataclass
class BrokerConfig:
    """Highway Broker configuration"""
    host: str
    port: int = 1883
    client_id: Optional[str] = None
    topic_pattern: str = "sumo/sensor/{id}/data"
    keepalive: int = 60


@dataclass
class SensorConfig:
    """Configuration for a single sensor"""
    sensorId: str  # Must match SUMO junction ID
    intersectionType: IntersectionType
    detectionRadius: float = 80.0  # metres
    publishInterval: float = 1.0  # seconds
    position: Optional[Dict[str, float]] = None  # {x, y}
    enableRawData: bool = True
    enableMetrics: bool = True


@dataclass
class Config:
    """Root configuration object"""
    sumo: SumoConfig
    broker: BrokerConfig
    sensors: List[SensorConfig]
    auto_discover_junctions: bool = False  # If True, auto-discover ALL junctions


def load_config(config_path: str) -> Config:
    """
    Load and validate configuration from JSON file.

    Args:
        config_path: Path to config.json file

    Returns:
        Config object

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
        json.JSONDecodeError: If JSON is malformed
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file, 'r') as f:
        data = json.load(f)

    # Validate required top-level fields
    if 'sumo' not in data:
        raise ValueError("Missing required field: 'sumo'")
    if 'broker' not in data:
        raise ValueError("Missing required field: 'broker'")

    # Parse SUMO config
    sumo_data = data['sumo']
    if 'binary' not in sumo_data:
        raise ValueError("Missing required field: 'sumo.binary'")
    if 'config_file' not in sumo_data:
        raise ValueError("Missing required field: 'sumo.config_file'")
    if 'mode' not in sumo_data:
        raise ValueError("Missing required field: 'sumo.mode'")

    sumo_mode = sumo_data['mode'].lower()
    if sumo_mode not in ['launch', 'attach']:
        raise ValueError(f"Invalid sumo.mode: {sumo_mode}. Must be 'launch' or 'attach'")

    sumo_config = SumoConfig(
        binary=sumo_data['binary'],
        config_file=sumo_data['config_file'],
        mode=sumo_mode,
        port=sumo_data.get('port', 8813)
    )

    # Validate SUMO config file exists
    sumo_cfg_path = Path(sumo_config.config_file)
    if not sumo_cfg_path.exists():
        raise ValueError(f"SUMO config file not found: {sumo_config.config_file}")

    # Parse broker config
    broker_data = data['broker']
    if 'host' not in broker_data:
        raise ValueError("Missing required field: 'broker.host'")

    broker_config = BrokerConfig(
        host=broker_data['host'],
        port=broker_data.get('port', 1883),
        client_id=broker_data.get('client_id'),
        topic_pattern=broker_data.get('topic_pattern', 'sumo/sensor/{id}/data'),
        keepalive=broker_data.get('keepalive', 60)
    )

    # Parse sensors config
    sensors = []
    auto_discover = data.get('auto_discover_junctions', False)

    if 'sensors' in data and data['sensors']:
        for sensor_data in data['sensors']:
            if 'sensorId' not in sensor_data:
                raise ValueError("Sensor config missing required field: 'sensorId'")
            if 'intersectionType' not in sensor_data:
                raise ValueError(f"Sensor {sensor_data['sensorId']} missing required field: 'intersectionType'")

            # Validate intersection type
            try:
                intersection_type = IntersectionType(sensor_data['intersectionType'])
            except ValueError:
                raise ValueError(
                    f"Invalid intersectionType for sensor {sensor_data['sensorId']}: "
                    f"{sensor_data['intersectionType']}. Must be one of: "
                    f"{', '.join([t.value for t in IntersectionType])}"
                )

            sensor = SensorConfig(
                sensorId=sensor_data['sensorId'],
                intersectionType=intersection_type,
                detectionRadius=sensor_data.get('detectionRadius', 80.0),
                publishInterval=sensor_data.get('publishInterval', 1.0),
                position=sensor_data.get('position'),
                enableRawData=sensor_data.get('enableRawData', True),
                enableMetrics=sensor_data.get('enableMetrics', True)
            )
            sensors.append(sensor)

    # If no sensors configured and auto_discover is False, raise error
    if not sensors and not auto_discover:
        raise ValueError(
            "No sensors configured and auto_discover_junctions is False. "
            "Either provide sensors in config or enable auto_discover_junctions."
        )

    return Config(
        sumo=sumo_config,
        broker=broker_config,
        sensors=sensors,
        auto_discover_junctions=auto_discover
    )


def get_network_file(sumo_config: SumoConfig) -> str:
    """
    Extract network file path from SUMO config file.

    Args:
        sumo_config: SUMO configuration

    Returns:
        Path to .net.xml file

    Raises:
        ValueError: If network file cannot be found
    """
    import xml.etree.ElementTree as ET

    try:
        tree = ET.parse(sumo_config.config_file)
        root = tree.getroot()

        # Look for <net-file value="..."/>
        net_file_elem = root.find('.//net-file')
        if net_file_elem is not None:
            net_file = net_file_elem.get('value')
            if net_file:
                # Resolve relative path from config file directory
                config_dir = Path(sumo_config.config_file).parent
                return str(config_dir / net_file)

        raise ValueError("No <net-file> found in SUMO config")

    except Exception as e:
        raise ValueError(f"Failed to parse SUMO config file: {e}")
