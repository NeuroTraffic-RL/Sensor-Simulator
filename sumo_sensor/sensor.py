"""
Sensor class for SUMO junction monitoring.
One Sensor instance per junction.
"""

import time
from typing import Optional

from .models import RawSensorData
from .config import SensorConfig
from .collector import DataCollector
from .publisher import Publisher
from .utils.net_parser import JunctionInfo
from .utils.logger import SensorLogger, get_logger


class Sensor:
    """
    Represents a single sensor attached to a junction.
    Collects and publishes traffic data at regular intervals.
    """

    def __init__(
        self,
        junction_id: str,
        junction_info: JunctionInfo,
        sensor_config: SensorConfig,
        collector: DataCollector,
        publisher: Publisher
    ):
        """
        Initialize sensor.

        Args:
            junction_id: SUMO junction ID
            junction_info: Junction information from network file
            sensor_config: Sensor configuration
            collector: Data collector instance (shared)
            publisher: Publisher instance (shared)
        """
        self.junction_id = junction_id
        self.junction_info = junction_info
        self.config = sensor_config
        self.collector = collector
        self.publisher = publisher

        # Sensor-specific logger
        self.logger = SensorLogger(junction_id, get_logger())

        # Timing
        self.last_publish_time = 0.0
        self.publish_interval = sensor_config.publishInterval

        # Statistics
        self.total_publishes = 0
        self.errors = 0

        self.logger.info(
            f"Initialized sensor: type={sensor_config.intersectionType.value}, "
            f"radius={sensor_config.detectionRadius}m, "
            f"interval={sensor_config.publishInterval}s"
        )

    def should_publish(self, current_time: float) -> bool:
        """
        Check if sensor should publish based on interval.

        Args:
            current_time: Current wall-clock time (seconds)

        Returns:
            True if should publish, False otherwise
        """
        if current_time - self.last_publish_time >= self.publish_interval:
            return True
        return False

    def collect_and_publish(self) -> bool:
        """
        Collect data and publish to broker/stdout.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Collect data
            data = self.collector.collect(
                self.junction_id,
                self.junction_info,
                self.config
            )

            # Publish data
            self.publisher.publish(
                self.junction_id,
                data,
                enable_mqtt=self.config.enableRawData
            )

            # Update timing and stats
            self.last_publish_time = time.time()
            self.total_publishes += 1

            self.logger.debug(
                f"Published data: vehicles={data.intersectionMetrics.totalVehicles}, "
                f"queue={data.intersectionMetrics.totalQueueLength}"
            )

            return True

        except Exception as e:
            self.errors += 1
            self.logger.exception(f"Failed to collect and publish data: {e}")
            return False

    def get_stats(self) -> dict:
        """
        Get sensor statistics.

        Returns:
            Dictionary of statistics
        """
        return {
            'junction_id': self.junction_id,
            'total_publishes': self.total_publishes,
            'errors': self.errors,
            'publish_interval': self.publish_interval,
            'last_publish_time': self.last_publish_time
        }

    def __repr__(self) -> str:
        return (
            f"Sensor(id={self.junction_id}, "
            f"type={self.config.intersectionType.value}, "
            f"publishes={self.total_publishes})"
        )
