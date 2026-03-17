"""
TraCI data collection for SUMO sensor simulator.
Collects traffic data from SUMO simulation for a specific junction.
"""

import traci
import math
from datetime import datetime
from typing import List, Optional, Dict, Set
from collections import defaultdict

from .models import (
    RawSensorData, Road, Vehicle, Lane, Position,
    IntersectionGeometry, RoadMetrics, QueueMetrics, FlowMetrics,
    IntersectionMetrics, TrafficLight, TrafficLightRef, TrafficLightData,
    TrafficLightSignal, TrafficLightProgram, TrafficLightPhase,
    TrafficLightCycle, TrafficLightPerformance,
    TrafficLightColor, VehicleType, IntersectionType, RoadDirection,
    CongestionLevel, get_congestion_level, map_sumo_vehicle_type
)
from .config import SensorConfig
from .utils.net_parser import JunctionInfo


class DataCollector:
    """
    Collects traffic data from SUMO via TraCI for a junction.
    """

    def __init__(self):
        """Initialize data collector"""
        self.previous_data: Dict[str, Dict] = {}  # For trend calculation
        self.traffic_light_cache: Dict[str, TrafficLight] = {}

    def collect(
        self,
        junction_id: str,
        junction_info: JunctionInfo,
        sensor_config: SensorConfig
    ) -> RawSensorData:
        """
        Collect raw sensor data for a junction.

        Args:
            junction_id: SUMO junction ID
            junction_info: Junction information from network file
            sensor_config: Sensor configuration

        Returns:
            RawSensorData object
        """
        # Get position
        if sensor_config.position:
            position = Position(
                x=sensor_config.position['x'],
                y=sensor_config.position['y']
            )
        else:
            position = Position(x=junction_info.x, y=junction_info.y)

        # Build geometry
        geometry = IntersectionGeometry(
            position=position,
            detection_radius=sensor_config.detectionRadius,
            intersection_type=sensor_config.intersectionType,
            radius=None  # TODO: Calculate for roundabouts
        )

        # Collect road data for each incoming edge
        roads = []
        for edge_id in junction_info.incoming_edges:
            try:
                road = self._collect_road_data(
                    edge_id,
                    junction_id,
                    sensor_config.detectionRadius,
                    position
                )
                if road:
                    roads.append(road)
            except Exception as e:
                # Skip this road if data collection fails
                print(f"Warning: Failed to collect data for edge {edge_id}: {e}")
                continue

        # Compute intersection metrics
        intersection_metrics = self._compute_intersection_metrics(roads)

        # Build timestamp
        timestamp = datetime.utcnow().isoformat() + 'Z'

        return RawSensorData(
            sensorId=junction_id,
            sensorType=sensor_config.intersectionType,
            timestamp=timestamp,
            geometry=geometry,
            roads=roads,
            intersectionMetrics=intersection_metrics
        )

    def _collect_road_data(
        self,
        edge_id: str,
        junction_id: str,
        detection_radius: float,
        junction_position: Position
    ) -> Optional[Road]:
        """
        Collect data for a single road (edge).

        Args:
            edge_id: SUMO edge ID
            junction_id: Junction ID
            detection_radius: Detection radius in metres
            junction_position: Position of junction

        Returns:
            Road object or None if collection fails
        """
        try:
            # Get basic road info
            lane_count = traci.edge.getLaneNumber(edge_id)

            # Determine road direction (simplified - based on edge angle)
            direction = self._determine_road_direction(edge_id)

            # Collect road metrics
            road_metrics = self._collect_road_metrics(edge_id, lane_count)

            # Collect queue metrics
            queue_metrics = self._collect_queue_metrics(edge_id)

            # Collect flow metrics
            flow_metrics = self._collect_flow_metrics(edge_id, road_metrics.capacity)

            # Collect lane details
            lane_details = self._collect_lane_details(edge_id, lane_count)

            # Collect traffic light data
            traffic_light_data = self._collect_traffic_light_data(edge_id, junction_id)

            # Collect vehicles
            vehicles = self._collect_vehicles(
                edge_id,
                detection_radius,
                junction_position
            )

            return Road(
                roadId=edge_id,
                direction=direction,
                incomingEdgeId=edge_id,
                lanes=lane_count,
                roadMetrics=road_metrics,
                queueMetrics=queue_metrics,
                flowMetrics=flow_metrics,
                laneDetails=lane_details,
                trafficLight=traffic_light_data,
                vehicles=vehicles
            )

        except traci.exceptions.TraCIException as e:
            print(f"TraCI error collecting data for edge {edge_id}: {e}")
            return None

    def _collect_road_metrics(self, edge_id: str, lane_count: int) -> RoadMetrics:
        """Collect road-level metrics"""
        try:
            # Get edge properties
            length = traci.lane.getLength(f"{edge_id}_0")  # Use first lane
            max_speed = traci.lane.getMaxSpeed(f"{edge_id}_0")

            # Get vehicle IDs on this edge
            vehicle_ids = traci.edge.getLastStepVehicleIDs(edge_id)
            vehicle_count = len(vehicle_ids)

            # Calculate speeds
            speeds = []
            for vid in vehicle_ids:
                try:
                    speed = traci.vehicle.getSpeed(vid) * 3.6  # m/s to km/h
                    speeds.append(speed)
                except:
                    continue

            avg_speed = sum(speeds) / len(speeds) if speeds else 0.0
            min_speed = min(speeds) if speeds else 0.0
            max_speed_observed = max(speeds) if speeds else 0.0

            # Calculate occupancy
            # Occupancy = (number of vehicles * avg vehicle length) / (edge length * lane count)
            avg_vehicle_length = 5.0  # metres (default car length)
            max_vehicles = int((length * lane_count) / avg_vehicle_length)
            occupancy_rate = min(1.0, vehicle_count / max_vehicles if max_vehicles > 0 else 0.0)

            # Calculate capacity (vehicles per hour)
            # Simplified: capacity = (3600 / avg_headway) * lane_count
            # Using typical urban: 1800 veh/hour/lane
            capacity = int(1800 * lane_count)

            # Determine congestion level
            congestion_level = get_congestion_level(occupancy_rate)

            # Speed trend (requires historical data)
            speed_trend = None
            prev_key = f"{edge_id}_avgSpeed"
            if prev_key in self.previous_data:
                prev_speed = self.previous_data[prev_key]
                speed_trend = avg_speed - prev_speed  # km/h change
            self.previous_data[prev_key] = avg_speed

            return RoadMetrics(
                length=length,
                speedLimit=max_speed * 3.6,  # m/s to km/h
                freeFlowSpeed=max_speed * 3.6,
                capacity=capacity,
                occupancyRate=occupancy_rate,
                avgSpeed=avg_speed,
                minSpeed=min_speed,
                maxSpeed=max_speed_observed,
                congestionLevel=congestion_level,
                speedTrend=speed_trend
            )

        except Exception as e:
            # Return default metrics on error
            return RoadMetrics(
                length=100.0,
                speedLimit=50.0,
                freeFlowSpeed=50.0,
                capacity=1800,
                occupancyRate=0.0,
                avgSpeed=0.0,
                minSpeed=0.0,
                maxSpeed=0.0,
                congestionLevel=CongestionLevel.FREE,
                speedTrend=None
            )

    def _collect_queue_metrics(self, edge_id: str) -> QueueMetrics:
        """Collect queue-level metrics"""
        try:
            # Count halting vehicles (speed < 0.1 m/s) as queued
            vehicle_ids = traci.edge.getLastStepVehicleIDs(edge_id)
            queue_length = sum(
                1 for vid in vehicle_ids
                if traci.vehicle.getSpeed(vid) < 0.1
            )

            # Track max queue
            queue_key = f"{edge_id}_maxQueue"
            max_queue = self.previous_data.get(queue_key, 0)
            if queue_length > max_queue:
                max_queue = queue_length
            self.previous_data[queue_key] = max_queue

            # Queue trend (vehicles per second)
            prev_queue_key = f"{edge_id}_queue"
            queue_trend = 0.0
            if prev_queue_key in self.previous_data:
                prev_queue = self.previous_data[prev_queue_key]
                queue_trend = queue_length - prev_queue  # Change per step (1 second)
            self.previous_data[prev_queue_key] = queue_length

            # Saturation ratio (queue / capacity)
            capacity = 1800  # Simplified
            saturation_ratio = min(1.0, queue_length / capacity if capacity > 0 else 0.0)

            return QueueMetrics(
                queueLength=queue_length,
                maxQueueLengthObserved=max_queue,
                queueTrend=queue_trend,
                saturationRatio=saturation_ratio
            )

        except Exception:
            return QueueMetrics(
                queueLength=0,
                maxQueueLengthObserved=0,
                queueTrend=0.0,
                saturation_ratio=0.0
            )

    def _collect_flow_metrics(self, edge_id: str, capacity: int) -> FlowMetrics:
        """Collect flow metrics"""
        try:
            vehicle_count = traci.edge.getLastStepVehicleNumber(edge_id)

            # Track vehicles entered/exited (simplified - would need edge detectors)
            vehicles_entered = 0
            vehicles_exited = 0

            # Flow rate (vehicles per hour)
            # Simplified: current vehicle count * 3600 (assuming 1 second steps)
            flow_rate = vehicle_count * 3600.0

            # Utilization rate
            utilization_rate = min(1.0, flow_rate / capacity if capacity > 0 else 0.0)

            # Time since last vehicle (would need detector data)
            time_last_vehicle_passed = 0.0

            return FlowMetrics(
                vehicleCount=vehicle_count,
                vehiclesExited=vehicles_exited,
                vehiclesEntered=vehicles_entered,
                flowRate=flow_rate,
                utilizationRate=utilization_rate,
                timeLastVehiclePassed=time_last_vehicle_passed
            )

        except Exception:
            return FlowMetrics(
                vehicleCount=0,
                vehiclesExited=0,
                vehiclesEntered=0,
                flowRate=0.0,
                utilizationRate=0.0,
                timeLastVehiclePassed=0.0
            )

    def _collect_lane_details(self, edge_id: str, lane_count: int) -> List[Lane]:
        """Collect per-lane details"""
        lanes = []

        for lane_idx in range(lane_count):
            lane_id = f"{edge_id}_{lane_idx}"

            try:
                # Get vehicles on this lane
                vehicle_ids = traci.lane.getLastStepVehicleIDs(lane_id)
                vehicle_count = len(vehicle_ids)

                # Calculate average speed
                speeds = []
                queue_length = 0
                for vid in vehicle_ids:
                    try:
                        speed = traci.vehicle.getSpeed(vid) * 3.6  # km/h
                        speeds.append(speed)
                        if speed < 0.36:  # < 0.1 m/s = queued
                            queue_length += 1
                    except:
                        continue

                avg_speed = sum(speeds) / len(speeds) if speeds else 0.0

                # Occupancy (simplified)
                length = traci.lane.getLength(lane_id)
                max_vehicles = int(length / 5.0)  # 5m per vehicle
                occupancy = min(1.0, vehicle_count / max_vehicles if max_vehicles > 0 else 0.0)

                lanes.append(Lane(
                    laneId=lane_id,
                    vehicleCount=vehicle_count,
                    avgSpeed=avg_speed,
                    occupancy=occupancy,
                    queueLength=queue_length
                ))

            except Exception:
                # Add empty lane on error
                lanes.append(Lane(
                    laneId=lane_id,
                    vehicleCount=0,
                    avgSpeed=0.0,
                    occupancy=0.0,
                    queueLength=0
                ))

        return lanes

    def _collect_traffic_light_data(
        self,
        edge_id: str,
        junction_id: str
    ) -> TrafficLightData:
        """Collect traffic light data for an edge"""
        try:
            # Get traffic lights at this junction
            tl_ids = traci.trafficlight.getIDList()

            # Find TL controlling this edge
            controlling_tl_id = None
            for tl_id in tl_ids:
                controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
                # Check if any lane from this edge is controlled
                for lane in controlled_lanes:
                    if lane.startswith(edge_id + "_"):
                        controlling_tl_id = tl_id
                        break
                if controlling_tl_id:
                    break

            if not controlling_tl_id:
                return None  # No traffic light for this edge

            # Check if we already collected this TL (use reference)
            if controlling_tl_id in self.traffic_light_cache:
                return TrafficLightRef(ref=controlling_tl_id)

            # Collect full traffic light data
            tl_data = self._collect_full_traffic_light(controlling_tl_id)
            self.traffic_light_cache[controlling_tl_id] = tl_data

            return tl_data

        except Exception as e:
            return None

    def _collect_full_traffic_light(self, tl_id: str) -> TrafficLight:
        """Collect full traffic light data"""
        try:
            # Get controlled roads
            controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
            controlled_roads = list(set(
                lane.rsplit('_', 1)[0] for lane in controlled_lanes
            ))

            # Get current phase
            phase_index = traci.trafficlight.getPhase(tl_id)
            phase_duration = traci.trafficlight.getPhaseDuration(tl_id)
            time_in_phase = traci.trafficlight.getNextSwitch(tl_id) - traci.simulation.getTime()
            time_until_next = phase_duration - time_in_phase

            # Get state
            state_string = traci.trafficlight.getRedYellowGreenState(tl_id)
            current_color = self._parse_traffic_light_color(state_string)

            signal = TrafficLightSignal(
                currentColor=current_color,
                timeInCurrentPhase=time_in_phase,
                timeUntilNextSwitch=max(0, time_until_next)
            )

            # Get program
            program_logic = traci.trafficlight.getAllProgramLogics(tl_id)
            if program_logic:
                logic = program_logic[0]
                phases = [
                    TrafficLightPhase(
                        index=i,
                        name=f"Phase_{i}",
                        state=phase.state,
                        duration=phase.duration,
                        minDuration=phase.minDur if hasattr(phase, 'minDur') else None,
                        maxDuration=phase.maxDur if hasattr(phase, 'maxDur') else None
                    )
                    for i, phase in enumerate(logic.phases)
                ]

                total_cycle = sum(p.duration for p in logic.phases)
                time_in_cycle = sum(
                    phases[i].duration for i in range(phase_index)
                ) + time_in_phase

                program = TrafficLightProgram(
                    currentPhaseIndex=phase_index,
                    totalPhases=len(phases),
                    phases=phases
                )

                cycle = TrafficLightCycle(
                    cycleDuration=total_cycle,
                    timeInCycle=time_in_cycle,
                    cycleNumber=int(traci.simulation.getTime() / total_cycle) if total_cycle > 0 else 0
                )
            else:
                # Default empty program
                program = TrafficLightProgram(
                    currentPhaseIndex=0,
                    totalPhases=1,
                    phases=[]
                )
                cycle = TrafficLightCycle(
                    cycleDuration=90.0,
                    timeInCycle=0.0,
                    cycleNumber=0
                )

            # Performance metrics (simplified)
            performance = TrafficLightPerformance(
                vehiclesClearedThisPhase=0,
                vehiclesClearedLastPhase=0,
                vehiclesWaitingForGreen=0,
                maxWaitingTime=0.0,
                avgWaitingTime=0.0
            )

            return TrafficLight(
                trafficLightId=tl_id,
                controlledRoads=controlled_roads,
                signal=signal,
                phaseProgram=program,
                cycle=cycle,
                performance=performance
            )

        except Exception as e:
            raise

    def _parse_traffic_light_color(self, state: str) -> TrafficLightColor:
        """Parse SUMO TL state string to get dominant color"""
        if not state:
            return TrafficLightColor.RED

        # Count colors
        greens = state.count('G') + state.count('g')
        yellows = state.count('Y') + state.count('y')
        reds = state.count('R') + state.count('r')

        # Return dominant color
        if greens > 0:
            return TrafficLightColor.GREEN
        elif yellows > 0:
            return TrafficLightColor.YELLOW
        else:
            return TrafficLightColor.RED

    def _collect_vehicles(
        self,
        edge_id: str,
        detection_radius: float,
        junction_position: Position
    ) -> List[Vehicle]:
        """Collect vehicle data within detection radius"""
        vehicles = []

        try:
            vehicle_ids = traci.edge.getLastStepVehicleIDs(edge_id)

            for vid in vehicle_ids:
                try:
                    # Check if within detection radius
                    veh_pos = traci.vehicle.getPosition(vid)
                    distance = math.sqrt(
                        (veh_pos[0] - junction_position.x) ** 2 +
                        (veh_pos[1] - junction_position.y) ** 2
                    )

                    if distance > detection_radius:
                        continue

                    # Collect vehicle data
                    lane_id = traci.vehicle.getLaneID(vid)
                    speed = traci.vehicle.getSpeed(vid) * 3.6  # km/h
                    lane_position = traci.vehicle.getLanePosition(vid)
                    waiting_time = traci.vehicle.getWaitingTime(vid)
                    accumulated_waiting = traci.vehicle.getAccumulatedWaitingTime(vid)
                    acceleration = traci.vehicle.getAcceleration(vid)
                    vtype = traci.vehicle.getTypeID(vid)
                    distance_to_stop = traci.vehicle.getDrivingDistance(vid, edge_id, 0)  # To end of edge

                    vehicles.append(Vehicle(
                        vehicleId=vid,
                        laneId=lane_id,
                        speed=speed,
                        position=lane_position,
                        waitingTime=waiting_time,
                        wasteTime=accumulated_waiting - waiting_time,  # Approximation
                        acceleration=acceleration,
                        vehicleType=map_sumo_vehicle_type(vtype),
                        distanceToStop=distance_to_stop if distance_to_stop > 0 else None
                    ))

                except Exception:
                    continue

        except Exception:
            pass

        return vehicles

    def _determine_road_direction(self, edge_id: str) -> RoadDirection:
        """Determine road direction (simplified)"""
        # This is a simplified version - in reality, you'd calculate
        # based on edge geometry
        return RoadDirection.CUSTOM

    def _compute_intersection_metrics(self, roads: List[Road]) -> IntersectionMetrics:
        """Compute aggregated intersection metrics"""
        if not roads:
            return IntersectionMetrics(
                totalVehicles=0,
                totalQueueLength=0,
                avgSpeedAll=0.0,
                globalCongestionLevel=0.0,
                trafficLightCount=0
            )

        total_vehicles = sum(r.flowMetrics.vehicleCount for r in roads)
        total_queue = sum(r.queueMetrics.queueLength for r in roads)

        # Calculate average speed across all vehicles
        all_speeds = []
        for road in roads:
            for vehicle in road.vehicles:
                all_speeds.append(vehicle.speed)
        avg_speed_all = sum(all_speeds) / len(all_speeds) if all_speeds else 0.0

        # Global congestion (weighted average of occupancy)
        total_occupancy = sum(r.roadMetrics.occupancyRate for r in roads)
        global_congestion = total_occupancy / len(roads) if roads else 0.0

        # Find bottleneck (highest saturation)
        bottleneck_road = None
        max_saturation = 0.0
        for road in roads:
            if road.queueMetrics.saturationRatio > max_saturation:
                max_saturation = road.queueMetrics.saturationRatio
                bottleneck_road = road.roadId

        # Count traffic lights
        tl_count = sum(
            1 for r in roads
            if r.trafficLight and isinstance(r.trafficLight, TrafficLight)
        )

        return IntersectionMetrics(
            totalVehicles=total_vehicles,
            totalQueueLength=total_queue,
            avgSpeedAll=avg_speed_all,
            globalCongestionLevel=global_congestion,
            bottleneckRoad=bottleneck_road,
            criticalTrafficLight=None,  # Would need waiting time analysis
            trafficLightCount=tl_count
        )
