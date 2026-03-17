"""
SUMO network file parser for junction discovery.
Parses .net.xml to extract junction information.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

from ..models import IntersectionType


@dataclass
class JunctionInfo:
    """Information about a junction parsed from .net.xml"""
    id: str
    x: float
    y: float
    type: str  # SUMO junction type
    incoming_edges: List[str]
    shape: Optional[str] = None


def parse_network_file(network_file: str) -> List[JunctionInfo]:
    """
    Parse SUMO .net.xml file and extract all junctions.

    Args:
        network_file: Path to .net.xml file

    Returns:
        List of JunctionInfo objects

    Raises:
        FileNotFoundError: If network file doesn't exist
        ValueError: If network file is invalid
    """
    net_path = Path(network_file)

    if not net_path.exists():
        raise FileNotFoundError(f"Network file not found: {network_file}")

    try:
        tree = ET.parse(network_file)
        root = tree.getroot()

        junctions = []

        # Parse all junction elements
        for junction_elem in root.findall('junction'):
            junction_id = junction_elem.get('id')
            junction_type = junction_elem.get('type')

            # Skip internal junctions and dead ends
            if junction_type in ['internal', 'dead_end']:
                continue

            # Extract coordinates
            x = float(junction_elem.get('x', 0.0))
            y = float(junction_elem.get('y', 0.0))

            # Extract shape if available
            shape = junction_elem.get('shape')

            # Extract incoming edges
            inc_lanes = junction_elem.get('incLanes', '')
            incoming_edges = []
            if inc_lanes:
                # Extract unique edge IDs from lane IDs (format: edgeID_laneIndex)
                lane_ids = inc_lanes.split()
                edge_ids = set()
                for lane_id in lane_ids:
                    if '_' in lane_id:
                        edge_id = lane_id.rsplit('_', 1)[0]
                        edge_ids.add(edge_id)
                incoming_edges = list(edge_ids)

            junction_info = JunctionInfo(
                id=junction_id,
                x=x,
                y=y,
                type=junction_type,
                incoming_edges=incoming_edges,
                shape=shape
            )

            junctions.append(junction_info)

        return junctions

    except ET.ParseError as e:
        raise ValueError(f"Failed to parse network file: {e}")


def map_junction_type_to_intersection_type(
    junction_type: str,
    incoming_edge_count: int
) -> IntersectionType:
    """
    Map SUMO junction type to IntersectionType enum.

    Args:
        junction_type: SUMO junction type string
        incoming_edge_count: Number of incoming edges

    Returns:
        IntersectionType enum value
    """
    junction_type_lower = junction_type.lower()

    # Roundabout
    if 'roundabout' in junction_type_lower:
        return IntersectionType.ROUNDABOUT

    # Traffic light controlled
    if junction_type_lower in ['traffic_light', 'traffic_light_unregulated']:
        return IntersectionType.FOUR_WAY

    # Priority junction - infer from edge count
    if junction_type_lower == 'priority':
        if incoming_edge_count == 3:
            return IntersectionType.T_JUNCTION
        else:
            return IntersectionType.FOUR_WAY

    # Right before left
    if junction_type_lower == 'right_before_left':
        return IntersectionType.FOUR_WAY

    # Unregulated
    if junction_type_lower == 'unregulated':
        return IntersectionType.CUSTOM

    # Default to custom for unknown types
    return IntersectionType.CUSTOM


def get_junction_by_id(junctions: List[JunctionInfo], junction_id: str) -> Optional[JunctionInfo]:
    """
    Find junction by ID.

    Args:
        junctions: List of JunctionInfo objects
        junction_id: Junction ID to find

    Returns:
        JunctionInfo object or None if not found
    """
    for junction in junctions:
        if junction.id == junction_id:
            return junction
    return None


def filter_junctions_by_type(
    junctions: List[JunctionInfo],
    junction_types: List[str]
) -> List[JunctionInfo]:
    """
    Filter junctions by SUMO type.

    Args:
        junctions: List of JunctionInfo objects
        junction_types: List of SUMO junction types to include

    Returns:
        Filtered list of JunctionInfo objects
    """
    return [j for j in junctions if j.type in junction_types]


def validate_junction_ids(
    junctions: List[JunctionInfo],
    sensor_ids: List[str]
) -> tuple[List[str], List[str]]:
    """
    Validate that sensor IDs match junction IDs in the network.

    Args:
        junctions: List of JunctionInfo from network
        sensor_ids: List of sensor IDs from config

    Returns:
        Tuple of (valid_ids, invalid_ids)
    """
    junction_ids = {j.id for j in junctions}
    valid_ids = [sid for sid in sensor_ids if sid in junction_ids]
    invalid_ids = [sid for sid in sensor_ids if sid not in junction_ids]

    return valid_ids, invalid_ids
