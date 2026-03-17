"""
SUMO visualization utilities for sensor zones.
Draws sensor detection areas as semi-transparent circles.
"""

import math
import traci
from typing import Tuple, List, Optional

from ..models import Position


def create_circle(
    center_x: float,
    center_y: float,
    radius: float,
    num_points: int = 32
) -> List[Tuple[float, float]]:
    """
    Create a circle shape as a list of points.

    Args:
        center_x: X coordinate of circle center
        center_y: Y coordinate of circle center
        radius: Circle radius in meters
        num_points: Number of points to approximate the circle (default: 32)

    Returns:
        List of (x, y) tuples representing the circle polygon
    """
    points = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        points.append((x, y))
    return points


def draw_sensor_zone(
    sensor_id: str,
    position: Position,
    radius: float,
    color: Tuple[int, int, int, int] = (0, 150, 255, 50),
    layer: int = 0
) -> bool:
    """
    Draw a sensor detection zone as a semi-transparent circle in SUMO.

    Args:
        sensor_id: Unique sensor ID (used for polygon ID)
        position: Center position of the sensor
        radius: Detection radius in meters
        color: RGBA color tuple (R, G, B, Alpha) where each value is 0-255
               Default: semi-transparent blue (0, 150, 255, 50)
        layer: Drawing layer (0 = behind roads, 1 = over roads)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Create circle shape
        circle_shape = create_circle(position.x, position.y, radius)

        # Create unique polygon ID
        polygon_id = f"sensor_zone_{sensor_id}"

        # Add polygon to SUMO
        traci.polygon.add(
            polygonID=polygon_id,
            shape=circle_shape,
            color=color,
            fill=True,
            layer=layer
        )

        return True

    except Exception as e:
        print(f"Warning: Failed to draw sensor zone for {sensor_id}: {e}")
        return False


def draw_all_sensor_zones(
    sensors: List,
    color_palette: Optional[List[Tuple[int, int, int, int]]] = None,
    layer: int = 0
) -> int:
    """
    Draw detection zones for all sensors.

    Args:
        sensors: List of Sensor objects
        color_palette: Optional list of RGBA colors to cycle through
                      If None, uses default color palette
        layer: Drawing layer (0 = behind roads, 1 = over roads)

    Returns:
        Number of zones successfully drawn
    """
    # Default color palette: semi-transparent colors
    if color_palette is None:
        color_palette = [
            (0, 150, 255, 50),   # Blue
            (255, 100, 0, 50),   # Orange
            (0, 200, 100, 50),   # Green
            (255, 0, 150, 50),   # Pink
            (150, 0, 255, 50),   # Purple
            (255, 200, 0, 50),   # Yellow
            (0, 255, 255, 50),   # Cyan
            (255, 100, 150, 50), # Rose
        ]

    success_count = 0

    for i, sensor in enumerate(sensors):
        # Cycle through color palette
        color = color_palette[i % len(color_palette)]

        # Get sensor position from geometry
        position = Position(
            x=sensor.junction_info.x,
            y=sensor.junction_info.y
        )

        # Draw sensor zone
        if draw_sensor_zone(
            sensor_id=sensor.junction_id,
            position=position,
            radius=sensor.config.detectionRadius,
            color=color,
            layer=layer
        ):
            success_count += 1

    return success_count


def remove_sensor_zone(sensor_id: str) -> bool:
    """
    Remove a sensor detection zone polygon.

    Args:
        sensor_id: Sensor ID

    Returns:
        True if successful, False otherwise
    """
    try:
        polygon_id = f"sensor_zone_{sensor_id}"
        traci.polygon.remove(polygon_id)
        return True
    except Exception:
        return False


def remove_all_sensor_zones(sensors: List) -> int:
    """
    Remove all sensor detection zone polygons.

    Args:
        sensors: List of Sensor objects

    Returns:
        Number of zones successfully removed
    """
    success_count = 0

    for sensor in sensors:
        if remove_sensor_zone(sensor.junction_id):
            success_count += 1

    return success_count


def update_sensor_zone_color(
    sensor_id: str,
    color: Tuple[int, int, int, int]
) -> bool:
    """
    Update the color of a sensor zone (useful for highlighting active sensors).

    Args:
        sensor_id: Sensor ID
        color: New RGBA color tuple

    Returns:
        True if successful, False otherwise
    """
    try:
        polygon_id = f"sensor_zone_{sensor_id}"
        traci.polygon.setColor(polygon_id, color)
        return True
    except Exception:
        return False


# Predefined color schemes for different use cases

COLOR_SCHEME_DEFAULT = [
    (0, 150, 255, 50),   # Blue
    (255, 100, 0, 50),   # Orange
    (0, 200, 100, 50),   # Green
    (255, 0, 150, 50),   # Pink
    (150, 0, 255, 50),   # Purple
    (255, 200, 0, 50),   # Yellow
    (0, 255, 255, 50),   # Cyan
    (255, 100, 150, 50), # Rose
]

COLOR_SCHEME_HEATMAP = [
    (0, 255, 0, 50),     # Green (low congestion)
    (255, 255, 0, 50),   # Yellow (medium congestion)
    (255, 150, 0, 50),   # Orange (high congestion)
    (255, 0, 0, 50),     # Red (very high congestion)
]

COLOR_SCHEME_MONOCHROME = [
    (128, 128, 128, 50), # Gray - uniform for all sensors
]
