"""
Simplified service for fetching and processing train network data.
Works with the DB Timetables API /plan endpoint.
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple
from collections import Counter
from geopy.distance import geodesic

from core.db_api_client import DBAPIClient, STATIONS_BY_NAME, STATIONS_BY_EVA
from core.models import Station, Connection, NetworkData, RouteWaypoint, MultiHopRoute, ConnectionLeg, TransferInfo
from core.cache_service import CacheService
from config import config


class NetworkService:
    """Service for building train network maps."""

    def __init__(
        self,
        api_client: Optional[DBAPIClient] = None,
        cache_service: Optional[CacheService] = None
    ):
        """Initialize the network service."""
        self.api_client = api_client or DBAPIClient()
        self.cache_service = cache_service or CacheService()

    async def get_station_info(self, station_name: str) -> Optional[Station]:
        """Get station information including coordinates."""
        station_data = await self.api_client.get_station_by_name(station_name)
        if not station_data:
            return None

        return Station(
            id=station_data.get("id", ""),
            name=station_data.get("name", station_name),
            lat=station_data.get("lat", 0.0),
            lon=station_data.get("lon", 0.0)
        )

    async def fetch_network_data(
        self,
        station_name: str = "Essen Hbf",
        max_connections: Optional[int] = None,
        max_changeovers: int = 0,
        min_transfer_time: int = None,
        max_routes_per_destination: int = None
    ) -> NetworkData:
        """
        Fetch complete network data for a station.

        NEW APPROACH - No Fake Estimates:
        1. Fetch all departures from origin
        2. Extract ALL unique destinations
        3. Fetch arrival data for ALL destinations (parallel + cached)
        4. Build connections ONLY when we have real arrival data
        5. Optionally find multi-hop routes with changeovers
        """
        # Get origin station info
        origin_station = await self.get_station_info(station_name)
        if not origin_station:
            raise ValueError(f"Station '{station_name}' not found")

        # Fetch departures from origin
        print(f"\n=== FETCHING DEPARTURES FROM {station_name} ===")
        departures = await self.api_client.get_departures(origin_station.id)
        print(f"Found {len(departures)} departures")

        # Extract all unique destinations from these departures
        all_destination_evas = self._extract_all_destinations(departures)
        print(f"Found {len(all_destination_evas)} unique destination stations")

        # Fetch arrival data for ALL destinations (parallel + cached)
        date_str = datetime.now().strftime("%y%m%d")
        destination_plans = await self._fetch_all_destination_plans(all_destination_evas, date_str)

        # Build connections ONLY from real data (no fake estimates!)
        connections = await self._build_connections_from_real_data(
            origin_station,
            departures,
            destination_plans,
            max_connections
        )

        print(f"\n✅ Created {len(connections)} connections (100% real data, no estimates!)\n")

        # Find multi-hop routes if requested
        multi_hop_routes = []
        if max_changeovers > 0:
            multi_hop_routes = await self.find_multi_hop_routes(
                origin_station=origin_station,
                direct_connections=connections,
                max_changeovers=max_changeovers,
                min_transfer_time=min_transfer_time or config.DEFAULT_MIN_TRANSFER_TIME,
                max_routes_per_destination=max_routes_per_destination or config.MAX_ROUTES_PER_DESTINATION,
                date_str=date_str
            )
            print(f"✅ Found {len(multi_hop_routes)} multi-hop routes\n")

        # Create network data object
        network_data = NetworkData(
            origin_station=origin_station,
            connections=connections,
            multi_hop_routes=multi_hop_routes
        )

        # Calculate statistics
        network_data.calculate_statistics()

        return network_data

    async def find_multi_hop_routes(
        self,
        origin_station: Station,
        direct_connections: List[Connection],
        max_changeovers: int,
        min_transfer_time: int,
        max_routes_per_destination: int,
        date_str: str
    ) -> List[MultiHopRoute]:
        """
        Find multi-hop routes with changeovers using BFS expansion.

        Algorithm:
        1. Start with direct connections (0 changeovers)
        2. For each level (1 to max_changeovers):
           - For each route from previous level
           - Fetch connections from that route's destination
           - Match valid transfers (min transfer time)
           - Build new multi-hop routes
        3. Rank by: fewest changeovers → fastest average aerial speed
        4. Return top N routes per destination
        """
        print(f"\n=== FINDING MULTI-HOP ROUTES (max {max_changeovers} changeovers) ===")

        # Track all routes by final destination
        routes_by_destination: Dict[str, List[MultiHopRoute]] = {}

        # Convert direct connections to single-leg MultiHopRoutes (depth 0)
        current_level_routes: List[MultiHopRoute] = []
        for conn in direct_connections:
            leg = ConnectionLeg(
                origin_id=conn.origin_id,
                origin_name=conn.origin_name,
                destination_id=conn.destination_id,
                destination_name=conn.destination_name,
                train_type=conn.train_type,
                train_number=conn.train_number,
                departure_time=conn.departure_time,
                arrival_time=conn.arrival_time,
                travel_time_minutes=conn.travel_time_minutes,
                distance_km=conn.distance_km,
                aerial_speed_kmh=conn.aerial_speed_kmh,
                platform=conn.platform
            )

            route = MultiHopRoute(
                origin_id=origin_station.id,
                origin_name=origin_station.name,
                destination_id=conn.destination_id,
                destination_name=conn.destination_name,
                destination_lat=conn.destination_lat,
                destination_lon=conn.destination_lon,
                legs=[leg],
                transfers=[],
                total_travel_time_minutes=conn.travel_time_minutes,
                total_distance_km=conn.distance_km,
                total_waiting_time_minutes=0,
                number_of_changeovers=0,
                average_aerial_speed_kmh=conn.aerial_speed_kmh,
                departure_time=conn.departure_time,
                arrival_time=conn.arrival_time,
                is_real_time=conn.is_real_time
            )

            current_level_routes.append(route)

            # Add to routes by destination
            if conn.destination_id not in routes_by_destination:
                routes_by_destination[conn.destination_id] = []
            routes_by_destination[conn.destination_id].append(route)

        print(f"Level 0: {len(current_level_routes)} direct connections")

        # Expand routes level by level
        for changeover_level in range(1, max_changeovers + 1):
            print(f"\nLevel {changeover_level}: Expanding routes...")

            next_level_routes: List[MultiHopRoute] = []

            # Get unique intermediate stations from current level
            intermediate_stations: Set[str] = set()
            for route in current_level_routes:
                intermediate_stations.add(route.destination_id)

            print(f"  Fetching connections from {len(intermediate_stations)} intermediate stations...")

            # Fetch connections from all intermediate stations
            station_connections: Dict[str, List[Connection]] = {}
            for station_eva in intermediate_stations:
                try:
                    # Fetch departures from this intermediate station
                    departures = await self.api_client.get_departures(station_eva)

                    # Extract destinations
                    dest_evas = self._extract_all_destinations(departures)

                    # Fetch destination plans
                    dest_plans = await self._fetch_all_destination_plans(dest_evas, date_str)

                    # Build connections
                    station_info = STATIONS_BY_EVA.get(station_eva)
                    if not station_info:
                        continue

                    intermediate_station = Station(
                        id=station_eva,
                        name=station_info["name"],
                        lat=station_info["lat"],
                        lon=station_info["lon"]
                    )

                    connections = await self._build_connections_from_real_data(
                        intermediate_station,
                        departures,
                        dest_plans,
                        None  # No limit
                    )

                    station_connections[station_eva] = connections

                except Exception as e:
                    print(f"  Error fetching connections for {station_eva}: {e}")
                    continue

            print(f"  Successfully fetched connections from {len(station_connections)} stations")

            # Try to extend each route from previous level
            extensions_count = 0
            for base_route in current_level_routes:
                intermediate_eva = base_route.destination_id

                if intermediate_eva not in station_connections:
                    continue

                # Try to connect with each outgoing connection
                for next_conn in station_connections[intermediate_eva]:
                    # Validate transfer time
                    transfer_minutes = int((next_conn.departure_time - base_route.arrival_time).total_seconds() / 60)

                    if transfer_minutes < min_transfer_time:
                        continue  # Too short transfer time

                    if transfer_minutes > 180:  # Max 3 hours waiting
                        continue

                    # Skip if going back to origin (no loops)
                    if next_conn.destination_id == origin_station.id:
                        continue

                    # Skip if already visited this station in the route
                    visited_stations = {leg.destination_id for leg in base_route.legs}
                    if next_conn.destination_id in visited_stations:
                        continue

                    # Create new leg
                    new_leg = ConnectionLeg(
                        origin_id=next_conn.origin_id,
                        origin_name=next_conn.origin_name,
                        destination_id=next_conn.destination_id,
                        destination_name=next_conn.destination_name,
                        train_type=next_conn.train_type,
                        train_number=next_conn.train_number,
                        departure_time=next_conn.departure_time,
                        arrival_time=next_conn.arrival_time,
                        travel_time_minutes=next_conn.travel_time_minutes,
                        distance_km=next_conn.distance_km,
                        aerial_speed_kmh=next_conn.aerial_speed_kmh,
                        platform=next_conn.platform
                    )

                    # Get station info for transfer
                    transfer_station_info = STATIONS_BY_EVA.get(intermediate_eva, {})

                    # Create transfer info
                    transfer = TransferInfo(
                        station_id=intermediate_eva,
                        station_name=base_route.destination_name,
                        station_lat=transfer_station_info.get("lat", 0.0),
                        station_lon=transfer_station_info.get("lon", 0.0),
                        arrival_time=base_route.arrival_time,
                        departure_time=next_conn.departure_time,
                        waiting_time_minutes=transfer_minutes,
                        arrival_platform=base_route.legs[-1].platform,
                        departure_platform=next_conn.platform
                    )

                    # Create extended route
                    new_legs = base_route.legs + [new_leg]
                    new_transfers = base_route.transfers + [transfer]

                    total_distance = base_route.total_distance_km + next_conn.distance_km
                    total_travel_time = int((next_conn.arrival_time - base_route.departure_time).total_seconds() / 60)
                    total_waiting = base_route.total_waiting_time_minutes + transfer_minutes

                    avg_aerial_speed = (total_distance / total_travel_time) * 60 if total_travel_time > 0 else 0

                    extended_route = MultiHopRoute(
                        origin_id=origin_station.id,
                        origin_name=origin_station.name,
                        destination_id=next_conn.destination_id,
                        destination_name=next_conn.destination_name,
                        destination_lat=next_conn.destination_lat,
                        destination_lon=next_conn.destination_lon,
                        legs=new_legs,
                        transfers=new_transfers,
                        total_travel_time_minutes=total_travel_time,
                        total_distance_km=round(total_distance, 2),
                        total_waiting_time_minutes=total_waiting,
                        number_of_changeovers=changeover_level,
                        average_aerial_speed_kmh=round(avg_aerial_speed, 2),
                        departure_time=base_route.departure_time,
                        arrival_time=next_conn.arrival_time,
                        is_real_time=base_route.is_real_time and next_conn.is_real_time
                    )

                    next_level_routes.append(extended_route)

                    # Add to routes by destination
                    if next_conn.destination_id not in routes_by_destination:
                        routes_by_destination[next_conn.destination_id] = []
                    routes_by_destination[next_conn.destination_id].append(extended_route)

                    extensions_count += 1

            print(f"  Created {extensions_count} new routes with {changeover_level} changeover(s)")

            current_level_routes = next_level_routes

            if not next_level_routes:
                print(f"  No more routes to expand at level {changeover_level}")
                break

        # Rank and select top N routes per destination
        # Ranking: fewest changeovers → fastest average aerial speed
        final_routes: List[MultiHopRoute] = []

        for dest_id, routes in routes_by_destination.items():
            # Sort by changeovers (ascending) then by average aerial speed (descending)
            sorted_routes = sorted(
                routes,
                key=lambda r: (r.number_of_changeovers, -r.average_aerial_speed_kmh)
            )

            # Take top N
            top_routes = sorted_routes[:max_routes_per_destination]
            final_routes.extend(top_routes)

        print(f"\n✅ Selected {len(final_routes)} routes across {len(routes_by_destination)} destinations")

        return final_routes

    def _extract_all_destinations(self, departures: List[Dict]) -> List[str]:
        """Extract all unique destination station EVA numbers from departures."""
        destination_evas = set()

        for departure in departures:
            path_stations = departure.get("path_stations", [])
            if not path_stations:
                continue

            # For each station in the path, try to get its EVA number
            for station_name in path_stations:
                station_info = STATIONS_BY_NAME.get(station_name.lower())
                if station_info and station_info.get("eva"):
                    destination_evas.add(station_info["eva"])

        return list(destination_evas)

    async def _fetch_all_destination_plans(
        self,
        destination_evas: List[str],
        date_str: str
    ) -> Dict[str, Dict]:
        """
        Fetch arrival/departure plans for ALL destination stations.
        Uses parallel fetching with caching - much faster than sequential!
        """
        print(f"\n=== FETCHING PLANS FOR {len(destination_evas)} DESTINATIONS ===")

        # Only fetch current and future hours to avoid 404s for past data
        current_hour = datetime.now().hour
        # Fetch from current hour through next 12 hours (wrapping to next day if needed)
        hours_to_fetch = [(current_hour + i) % 24 for i in range(13)]
        print(f"Fetching hours: {hours_to_fetch}")

        # Limit parallelism to avoid overwhelming the API
        semaphore = asyncio.Semaphore(config.MAX_PARALLEL_STATION_FETCHES)

        async def fetch_one(eva: str) -> Tuple[str, Optional[Dict]]:
            """Fetch plan data for one station with rate limiting."""
            async with semaphore:
                # Check cache first
                cached_plan = self.cache_service.load_station_plan(eva, date_str)
                if cached_plan is not None:
                    return (eva, cached_plan)

                # Fetch from API - only fetch current and future hours
                try:
                    plan_data = await self.api_client.get_full_plan(eva, date_str, hours_to_fetch)
                    # Cache it
                    self.cache_service.save_station_plan(eva, date_str, plan_data)
                    return (eva, plan_data)
                except Exception as e:
                    return (eva, None)

        # Fetch all in parallel
        results = await asyncio.gather(*[fetch_one(eva) for eva in destination_evas])

        # Build result dict
        destination_plans = {eva: plan for eva, plan in results if plan is not None}

        cache_hits = sum(1 for eva, plan in results if plan is not None and self.cache_service.load_station_plan(eva, date_str) is not None)
        api_fetches = len(destination_plans) - cache_hits

        print(f"  Cache hits: {cache_hits}, API fetches: {api_fetches}")
        print(f"  Successfully loaded plans for {len(destination_plans)}/{len(destination_evas)} stations\n")

        return destination_plans

    async def _build_connections_from_real_data(
        self,
        origin_station: Station,
        departures: List[Dict],
        destination_plans: Dict[str, Dict],
        max_connections: Optional[int] = None
    ) -> List[Connection]:
        """
        Build connections ONLY when we have real arrival data.
        No fake estimates - if we don't have the destination's arrival data, we skip it.
        """
        print("=== BUILDING CONNECTIONS FROM REAL DATA ===")
        connections = []
        seen_pairs: Set[tuple] = set()  # Track (train_number, destination_eva)

        for departure in departures:
            path_stations = departure.get("path_stations", [])
            if not path_stations:
                continue

            train_number = departure.get("number", "")
            train_type = departure.get("type", "")

            # Parse departure time
            time_str = departure.get("time", "")
            if len(time_str) != 10:
                continue

            try:
                departure_datetime = datetime.strptime(time_str, "%y%m%d%H%M")
            except ValueError:
                continue

            # Try to create a connection for each station in the path
            for dest_name in path_stations:
                # Get destination station info
                dest_station_data = STATIONS_BY_NAME.get(dest_name.lower())
                if not dest_station_data or not dest_station_data.get("eva"):
                    continue

                dest_eva = dest_station_data["eva"]

                # Skip if we've already processed this train-destination pair
                pair_key = (train_number, dest_eva)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # CRITICAL: Only proceed if we have destination plan data
                if dest_eva not in destination_plans:
                    continue

                # Try to find matching arrival in destination's plan
                arrival_time = self._find_arrival_time(
                    destination_plans[dest_eva],
                    train_number,
                    departure_datetime
                )

                # If no real arrival time found, SKIP this connection
                if not arrival_time:
                    continue

                # Create destination station object
                dest_station = Station(
                    id=dest_eva,
                    name=dest_name,
                    lat=dest_station_data.get("lat", 0.0),
                    lon=dest_station_data.get("lon", 0.0)
                )

                # Calculate distance
                distance_km = self._calculate_distance(
                    origin_station.lat, origin_station.lon,
                    dest_station.lat, dest_station.lon
                )

                if distance_km <= 0:
                    continue

                # Calculate travel time from REAL arrival time
                travel_time_minutes = int((arrival_time - departure_datetime).total_seconds() / 60)

                if travel_time_minutes <= 0:
                    continue

                # Calculate aerial speed from real data
                aerial_speed_kmh = round((distance_km / travel_time_minutes) * 60, 2)

                # Build route waypoints
                waypoints = await self._build_route_waypoints(
                    origin_station=origin_station,
                    destination_station=dest_station,
                    path_stations=path_stations,
                    departure_time=departure_datetime,
                    total_travel_minutes=travel_time_minutes
                )

                # Create connection with REAL data only
                connection = Connection(
                    origin_id=origin_station.id,
                    origin_name=origin_station.name,
                    destination_id=dest_station.id,
                    destination_name=dest_station.name,
                    destination_lat=dest_station.lat,
                    destination_lon=dest_station.lon,
                    train_type=train_type,
                    train_number=train_number,
                    departure_time=departure_datetime,
                    arrival_time=arrival_time,  # REAL arrival time from API!
                    travel_time_minutes=travel_time_minutes,
                    distance_km=distance_km,
                    aerial_speed_kmh=aerial_speed_kmh,
                    route_waypoints=waypoints,
                    platform=departure.get("platform", ""),
                    delay=None,
                    is_real_time=True,  # Always true in this new approach!
                    path_station_names=path_stations  # Store for future use
                )

                connections.append(connection)

                # Stop if we hit the max
                if max_connections and len(connections) >= max_connections:
                    break

            if max_connections and len(connections) >= max_connections:
                break

        return connections

    def _find_arrival_time(
        self,
        destination_plan: Dict,
        train_number: str,
        departure_time: datetime
    ) -> Optional[datetime]:
        """Find the arrival time for a specific train at the destination station."""
        arrivals = destination_plan.get("arrivals", [])

        for arrival in arrivals:
            if arrival.get("number") == train_number:
                # Parse arrival time
                time_str = arrival.get("time", "")
                if len(time_str) == 10:
                    try:
                        arrival_dt = datetime.strptime(time_str, "%y%m%d%H%M")

                        # Sanity check: arrival should be after departure
                        time_diff = (arrival_dt - departure_time).total_seconds() / 60

                        # Should be within reasonable range (5 min to 24 hours)
                        if 5 <= time_diff <= 1440:
                            return arrival_dt

                    except ValueError:
                        continue

        return None

    async def _process_departures(
        self,
        origin_station: Station,
        departures: List[Dict],
        max_connections: Optional[int] = None
    ) -> List[Connection]:
        """Process departure data into Connection objects."""
        connections = []
        seen_pairs: Set[tuple] = set()  # Track (train_number, destination) pairs

        for departure in departures[:max_connections] if max_connections else departures:
            try:
                # Get all stations in the path for this train
                path_stations = departure.get("path_stations", [])
                if not path_stations:
                    # Fallback to just destination
                    path_stations = [departure.get("destination", "")]

                train_number = departure.get("number", "")
                train_type = departure.get("type", "")

                # Parse departure time from format: YYMMDDhhmm
                time_str = departure.get("time", "")
                if len(time_str) != 10:
                    continue

                try:
                    departure_datetime = datetime.strptime(time_str, "%y%m%d%H%M")
                except ValueError:
                    continue

                # Check each station in the path
                for dest_name in path_stations:
                    # Create unique key
                    pair_key = (train_number, dest_name)
                    if pair_key in seen_pairs:
                        continue

                    # Get destination station info
                    dest_station = await self.get_station_info(dest_name)
                    if not dest_station or (dest_station.lat == 0.0 and dest_station.lon == 0.0):
                        # Skip if we don't have coordinates
                        continue

                    # Calculate distance
                    distance_km = self._calculate_distance(
                        origin_station.lat, origin_station.lon,
                        dest_station.lat, dest_station.lon
                    )

                    if distance_km <= 0:
                        continue

                    # Use placeholder values - will be replaced with real times during enrichment
                    # Assume 100km/h average speed as a rough initial estimate
                    travel_time_minutes = int((distance_km / 100.0) * 60)

                    if travel_time_minutes <= 0:
                        continue

                    arrival_datetime = departure_datetime + timedelta(minutes=travel_time_minutes)
                    aerial_speed_kmh = (distance_km / travel_time_minutes) * 60 if travel_time_minutes > 0 else 0

                    # Build route waypoints for this connection
                    waypoints = await self._build_route_waypoints(
                        origin_station=origin_station,
                        destination_station=dest_station,
                        path_stations=path_stations,
                        departure_time=departure_datetime,
                        total_travel_minutes=travel_time_minutes
                    )

                    # Create connection
                    connection = Connection(
                        origin_id=origin_station.id,
                        origin_name=origin_station.name,
                        destination_id=dest_station.id,
                        destination_name=dest_station.name,
                        destination_lat=dest_station.lat,
                        destination_lon=dest_station.lon,
                        train_type=train_type,
                        train_number=train_number,
                        departure_time=departure_datetime,
                        arrival_time=arrival_datetime,
                        travel_time_minutes=travel_time_minutes,
                        distance_km=round(distance_km, 2),
                        aerial_speed_kmh=round(aerial_speed_kmh, 2),
                        route_waypoints=waypoints,
                        platform=departure.get("platform"),
                        delay=None,
                    )

                    connections.append(connection)
                    seen_pairs.add(pair_key)

            except Exception as e:
                print(f"Error processing departure: {e}")
                continue

        return connections

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate straight-line distance between two points."""
        if not all([lat1, lon1, lat2, lon2]):
            return 0.0

        try:
            return geodesic((lat1, lon1), (lat2, lon2)).kilometers
        except Exception:
            return 0.0

    async def _build_route_waypoints(
        self,
        origin_station: Station,
        destination_station: Station,
        path_stations: List[str],
        departure_time: datetime,
        total_travel_minutes: int
    ) -> List[RouteWaypoint]:
        """
        Build route waypoints with proportional timing.

        For a train going Essen → Gelsenkirchen → Münster:
        - Calculate total route distance
        - For each waypoint, estimate arrival based on cumulative distance proportion
        """
        waypoints = []

        # Find the position of destination in the path
        try:
            dest_index = path_stations.index(destination_station.name)
        except ValueError:
            # Destination not in path, return empty waypoints
            return waypoints

        # Build list of stations from origin to destination
        # Path stations only includes stations AFTER origin
        route_stations = path_stations[:dest_index]  # Excludes destination

        if not route_stations:
            # Direct connection, no intermediate stations
            return waypoints

        # Get coordinates for all stations in route
        all_stations = []  # [(name, lat, lon), ...]
        all_stations.append((origin_station.name, origin_station.lat, origin_station.lon))

        for station_name in route_stations:
            station_info = await self.get_station_info(station_name)
            if station_info and station_info.lat != 0.0 and station_info.lon != 0.0:
                all_stations.append((station_name, station_info.lat, station_info.lon))

        all_stations.append((destination_station.name, destination_station.lat, destination_station.lon))

        # Calculate cumulative distances
        cumulative_distances = [0.0]  # Start at origin with 0 distance
        for i in range(len(all_stations) - 1):
            prev_lat, prev_lon = all_stations[i][1], all_stations[i][2]
            curr_lat, curr_lon = all_stations[i + 1][1], all_stations[i + 1][2]
            segment_dist = self._calculate_distance(prev_lat, prev_lon, curr_lat, curr_lon)
            cumulative_distances.append(cumulative_distances[-1] + segment_dist)

        total_distance = cumulative_distances[-1]

        if total_distance <= 0:
            return waypoints

        # Build waypoints for intermediate stations (exclude origin and destination)
        for i in range(1, len(all_stations) - 1):
            name, lat, lon = all_stations[i]
            cum_dist = cumulative_distances[i]

            # Proportional timing: time = (distance_so_far / total_distance) * total_time
            time_ratio = cum_dist / total_distance
            minutes_to_waypoint = int(total_travel_minutes * time_ratio)
            arrival_time = departure_time + timedelta(minutes=minutes_to_waypoint)

            waypoint = RouteWaypoint(
                station_name=name,
                lat=lat,
                lon=lon,
                arrival_time=arrival_time,
                distance_from_origin_km=round(cum_dist, 2)
            )
            waypoints.append(waypoint)

        return waypoints

    # Real-time arrival optimization methods

    def _identify_top_destinations(
        self,
        connections: List[Connection],
        limit: int = None
    ) -> List[Tuple[str, str, int]]:
        """
        Identify top N destination stations by connection count.

        Args:
            connections: List of connections
            limit: Max number of destinations (defaults to config.TOP_DESTINATIONS_COUNT)

        Returns:
            List of (station_eva, station_name, connection_count) tuples, sorted by count desc
        """
        if limit is None:
            limit = config.TOP_DESTINATIONS_COUNT

        # Count connections per destination
        dest_counter = Counter()
        dest_names = {}  # EVA -> name mapping

        for conn in connections:
            dest_counter[conn.destination_id] += 1
            dest_names[conn.destination_id] = conn.destination_name

        # Get top N
        top_dests = dest_counter.most_common(limit)

        return [(eva, dest_names[eva], count) for eva, count in top_dests]

    async def _fetch_destination_plan_data(
        self,
        destination_evas: List[str],
        date_str: str
    ) -> Dict[str, Dict]:
        """
        Fetch plan data for multiple destination stations in parallel.

        Args:
            destination_evas: List of destination EVA numbers
            date_str: Date in YYMMDD format

        Returns:
            Dict mapping EVA -> plan_data (with 'arrivals' and 'departures')
        """
        # Only fetch current and future hours to avoid 404s
        current_hour = datetime.now().hour
        hours_to_fetch = [(current_hour + i) % 24 for i in range(13)]

        semaphore = asyncio.Semaphore(config.MAX_PARALLEL_STATION_FETCHES)

        async def fetch_one(eva: str) -> Tuple[str, Optional[Dict]]:
            """Fetch plan data for one station with rate limiting."""
            async with semaphore:
                # Check cache first
                cached_plan = self.cache_service.load_station_plan(eva, date_str)
                if cached_plan is not None:
                    print(f"  [CACHE HIT] {eva}")
                    return (eva, cached_plan)

                # Fetch from API
                print(f"  [API FETCH] {eva}")
                try:
                    plan_data = await self.api_client.get_full_plan(eva, date_str, hours_to_fetch)
                    # Cache it
                    self.cache_service.save_station_plan(eva, date_str, plan_data)
                    return (eva, plan_data)
                except Exception as e:
                    print(f"  [ERROR] {eva}: {e}")
                    return (eva, None)

        # Fetch all in parallel
        print(f"Fetching plan data for {len(destination_evas)} destinations...")
        results = await asyncio.gather(*[fetch_one(eva) for eva in destination_evas])

        # Build result dict
        return {eva: plan_data for eva, plan_data in results if plan_data is not None}

    def _match_real_arrival_time(
        self,
        connection: Connection,
        destination_plan: Dict
    ) -> Optional[datetime]:
        """
        Match a connection's train to find its real arrival time at destination.

        Args:
            connection: Connection to match
            destination_plan: Plan data for destination station

        Returns:
            Real arrival datetime if matched, None otherwise
        """
        arrivals = destination_plan.get("arrivals", [])

        # Match by train number
        for arrival in arrivals:
            if arrival.get("number") == connection.train_number:
                # Parse arrival time
                time_str = arrival.get("time", "")
                if len(time_str) == 10:
                    try:
                        arrival_dt = datetime.strptime(time_str, "%y%m%d%H%M")

                        # Sanity check: arrival should be after departure
                        time_diff = (arrival_dt - connection.departure_time).total_seconds() / 60

                        # Should be within reasonable range (5 min to 24 hours)
                        if 5 <= time_diff <= 1440:
                            return arrival_dt

                    except ValueError:
                        continue

        return None

    async def _enrich_connections_with_real_times(
        self,
        connections: List[Connection],
        date_str: str
    ) -> List[Connection]:
        """
        Enrich connections with real arrival times from destination station data.

        Args:
            connections: List of connections with estimated times
            date_str: Date string in YYMMDD format

        Returns:
            Updated connections list with real times where available
        """
        if not connections:
            return connections

        print(f"\n=== ENRICHING WITH REAL ARRIVAL TIMES ===")

        # Step 1: Identify top destinations
        top_dests = self._identify_top_destinations(connections)
        print(f"Top {len(top_dests)} destinations by connection count:")
        for eva, name, count in top_dests[:10]:
            print(f"  {name}: {count} connections")

        # Step 2: Fetch plan data for top destinations (parallel)
        dest_evas = [eva for eva, _, _ in top_dests]
        dest_plans = await self._fetch_destination_plan_data(dest_evas, date_str)
        print(f"Successfully fetched plan data for {len(dest_plans)} stations")

        # Step 3: Match real arrival times
        matched_count = 0
        for conn in connections:
            if conn.destination_id in dest_plans:
                real_arrival = self._match_real_arrival_time(conn, dest_plans[conn.destination_id])

                if real_arrival:
                    # Update connection with real time
                    old_arrival = conn.arrival_time
                    conn.arrival_time = real_arrival
                    conn.is_real_time = True

                    # Recalculate travel time and speed
                    conn.travel_time_minutes = int((real_arrival - conn.departure_time).total_seconds() / 60)
                    if conn.travel_time_minutes > 0:
                        conn.aerial_speed_kmh = round((conn.distance_km / conn.travel_time_minutes) * 60, 2)

                    # Rebuild waypoints with new timing
                    conn.route_waypoints = await self._build_route_waypoints(
                        origin_station=Station(
                            id=conn.origin_id,
                            name=conn.origin_name,
                            lat=0, lon=0  # Not needed for this call
                        ),
                        destination_station=Station(
                            id=conn.destination_id,
                            name=conn.destination_name,
                            lat=conn.destination_lat,
                            lon=conn.destination_lon
                        ),
                        path_stations=[], # TODO: Store path in connection
                        departure_time=conn.departure_time,
                        total_travel_minutes=conn.travel_time_minutes
                    )

                    matched_count += 1

        print(f"✓ Matched real arrival times for {matched_count}/{len(connections)} connections")
        print(f"  Real-time: {matched_count}, Estimated: {len(connections) - matched_count}")

        # IMPORTANT: Only return connections with real arrival times
        # No more fake estimates - only accurate data!
        real_time_connections = [conn for conn in connections if conn.is_real_time]
        print(f"  Returning {len(real_time_connections)} connections (real-time only)\n")

        return real_time_connections
