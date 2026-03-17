"""
Publisher for SUMO sensor data.
Handles publishing to Highway Broker (MQTT) and stdout.
"""

import json
import sys
from typing import Optional

# Import HighwayClient from libs
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'libs'))
from rnneb_client import HighwayClient, QoS

from .models import RawSensorData, to_dict
from .config import BrokerConfig
from .utils.logger import get_logger


class Publisher:
    """
    Publishes sensor data to Highway Broker and stdout.
    """

    def __init__(self, broker_config: BrokerConfig):
        """
        Initialize publisher.

        Args:
            broker_config: Broker configuration
        """
        self.broker_config = broker_config
        self.client: Optional[HighwayClient] = None
        self.connected = False
        self.logger = get_logger()

        # Initialize Highway client
        self._init_client()

    def _init_client(self):
        """Initialize Highway broker client"""
        try:
            client_config = {
                'host': self.broker_config.host,
                'port': self.broker_config.port,
                'client_id': self.broker_config.client_id or f'sumo-sensor-{os.getpid()}',
                'keepalive': self.broker_config.keepalive,
                'auto_connect': False  # We'll connect manually
            }

            self.client = HighwayClient(client_config)

            # Set up event handlers
            self.client.on('connect', self._on_connect)
            self.client.on('disconnect', self._on_disconnect)
            self.client.on('error', self._on_error)

            # Connect
            self.logger.info(f"Connecting to Highway Broker at {self.broker_config.host}:{self.broker_config.port}")
            self.client.connect(self._on_connect_callback)

        except Exception as e:
            self.logger.error(f"Failed to initialize Highway client: {e}", exc_info=True)
            self.client = None

    def _on_connect(self):
        """Handle connection established"""
        self.connected = True
        self.logger.info("Connected to Highway Broker")

    def _on_disconnect(self):
        """Handle disconnection"""
        self.connected = False
        self.logger.warning("Disconnected from Highway Broker")

    def _on_error(self, error):
        """Handle error"""
        self.logger.error(f"Highway Broker error: {error}")

    def _on_connect_callback(self, success: bool, error=None):
        """Handle connect callback"""
        if success:
            self.connected = True
            self.logger.info("Successfully connected to Highway Broker")
        else:
            self.connected = False
            self.logger.error(f"Failed to connect to Highway Broker: {error}")

    def wait_for_connection(self, timeout: float = 5.0) -> bool:
        """
        Wait for broker connection to be established.

        Args:
            timeout: Timeout in seconds

        Returns:
            True if connected, False otherwise
        """
        import time
        start = time.time()
        while not self.connected and (time.time() - start) < timeout:
            time.sleep(0.1)
        return self.connected

    def publish(self, sensor_id: str, data: RawSensorData, enable_mqtt: bool = True):
        """
        Publish sensor data to broker and stdout.

        Args:
            sensor_id: Sensor ID
            data: Raw sensor data
            enable_mqtt: Whether to publish to MQTT (default: True)
        """
        # Convert to dict
        data_dict = to_dict(data)

        # Convert to JSON
        json_str = json.dumps(data_dict, indent=2)

        # Print to stdout
        self._print_to_stdout(sensor_id, json_str)

        # Publish to broker if enabled and connected
        if enable_mqtt and self.connected and self.client:
            self._publish_to_broker(sensor_id, data_dict)

    def _print_to_stdout(self, sensor_id: str, json_str: str):
        """Print formatted sensor data to stdout"""
        print(f"\n{'=' * 80}")
        print(f"Sensor: {sensor_id}")
        print(f"{'=' * 80}")
        print(json_str)
        print(f"{'=' * 80}\n")
        sys.stdout.flush()

    def _publish_to_broker(self, sensor_id: str, data_dict: dict):
        """Publish to Highway Broker"""
        try:
            # Build topic from pattern
            topic = self.broker_config.topic_pattern.replace('{id}', sensor_id)

            # Convert to compact JSON bytes
            json_bytes = json.dumps(data_dict, separators=(',', ':')).encode('utf-8')

            # Publish with QoS 0 (fire and forget)
            self.client.publish(topic, json_bytes, qos=QoS.AT_MOST_ONCE)

            self.logger.debug(f"Published to topic: {topic} ({len(json_bytes)} bytes)")

        except Exception as e:
            self.logger.warning(f"Failed to publish to broker: {e}")
            # Continue - stdout still works

    def disconnect(self):
        """Disconnect from broker"""
        if self.client and self.connected:
            try:
                self.client.disconnect()
                self.logger.info("Disconnected from Highway Broker")
            except Exception as e:
                self.logger.error(f"Error disconnecting from broker: {e}")

        self.connected = False
