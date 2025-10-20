"""
Simplified service for fetching and processing train network data.
Works with the DB Timetables API /plan endpoint.
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple
from collections import Counter
from geopy.distance import geodesic

from core.db_api_client import DBAPIClient, STATIONS_BY_NAME, STATIONS_BY_EVA, get_all_related_evas
from core.models import (
    Station, Connection, NetworkData, RouteWaypoint, MultiHopRoute,
    ConnectionLeg, TransferInfo, classify_train_type, is_deutschland_ticket_valid
)
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
        max_routes_per_destination: int = None,
        show_only_hubs_and_endpoints: Optional[bool] = None,
        deutschland_ticket_only: bool = False,
        train_categories: Optional[List[str]] = None
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

        # Fetch departures from origin - including ALL related platforms/sections
        print(f"\n=== FETCHING DEPARTURES FROM {station_name} ===")

        # Get all related EVAs for the origin station (handles fragmented stations)
        origin_evas = get_all_related_evas(origin_station.id)
        if len(origin_evas) > 1:
            print(f"Origin station has {len(origin_evas)} related platforms/sections:")
            for eva in origin_evas:
                station_info = STATIONS_BY_EVA.get(eva, {})
                print(f"  - {eva}: {station_info.get('name', 'Unknown')}")

        # Fetch departures from ALL origin platforms
        all_departures = []
        for eva in origin_evas:
            try:
                eva_departures = await self.api_client.get_departures(eva)
                all_departures.extend(eva_departures)
                if len(origin_evas) > 1:
                    station_info = STATIONS_BY_EVA.get(eva, {})
                    print(f"  Fetched {len(eva_departures)} departures from {station_info.get('name', eva)}")
            except Exception as e:
                print(f"  Error fetching from {eva}: {e}")

        # Deduplicate: same train might appear in multiple platform feeds
        seen = set()
        departures = []
        for dep in all_departures:
            # Use train number + time + destination as unique key
            key = (dep.get('number'), dep.get('time'), dep.get('destination'))
            if key not in seen:
                seen.add(key)
                departures.append(dep)

        if len(all_departures) > len(departures):
            print(f"Deduplicated: {len(all_departures)} → {len(departures)} unique departures")
        else:
            print(f"Total departures from all platforms: {len(departures)}")

        # EARLY FILTERING: Filter departures by train type BEFORE extracting destinations
        # This prevents us from fetching data for stations we won't use anyway
        print(f"\n=== EARLY FILTERING: Train Type ===")
        if deutschland_ticket_only:
            print(f"  Deutschland-Ticket filter: ON")
        if train_categories:
            print(f"  Train categories: {train_categories}")

        departures = self._filter_departures_by_train_type(
            departures=departures,
            deutschland_ticket_only=deutschland_ticket_only,
            train_categories=train_categories
        )
        print(f"After train type filtering: {len(departures)} departures kept")

        # Determine if we should use hub/endpoint filtering
        if show_only_hubs_and_endpoints is None:
            show_only_hubs_and_endpoints = config.DEFAULT_SHOW_ONLY_HUBS_AND_ENDPOINTS

        # TWO-SWEEP TOPOLOGY ANALYSIS (if hub/endpoint filtering enabled)
        neighbor_graph = None  # Will be populated if filtering is enabled
        if show_only_hubs_and_endpoints:
            # Extract stations that appear in origin's departures (for final filtering)
            origin_connected_stations = self._extract_stations_from_departures(departures)
            print(f"\nOrigin-connected stations: {len(origin_connected_stations)} (from departure paths)")

            # FIRST SWEEP: Build initial neighbor graph from origin departures
            print(f"\n=== FIRST SWEEP: Building neighbor graph ===")
            print(f"Analyzing {len(departures)} departure paths...")
            neighbor_graph = self._build_neighbor_graph_from_departures(departures)

            print(f"Built neighbor graph: {len(neighbor_graph)} stations")

            hubs, endpoints = self._identify_hubs_and_endpoints(neighbor_graph)
            print(f"  Hubs (3+ neighbors): {len(hubs)} stations")
            print(f"  Endpoints (1 neighbor): {len(endpoints)} stations")

            # Count pass-through stations for logging
            pass_through = len(neighbor_graph) - len(hubs) - len(endpoints)
            print(f"  Pass-through (2 neighbors): {pass_through} stations")

            # SECOND SWEEP: Enhance graph by fetching from hubs and endpoints
            print(f"\n=== SECOND SWEEP: Enhancing graph ===")
            second_sweep_stations = hubs + endpoints

            neighbor_graph = await self._enhance_graph_with_second_sweep(
                neighbor_graph=neighbor_graph,
                stations_to_sweep=second_sweep_stations,
                deutschland_ticket_only=deutschland_ticket_only,
                train_categories=train_categories,
                date_str=datetime.now().strftime("%y%m%d")
            )

            # Recount after enhancement
            print(f"\nEnhanced neighbor graph: {len(neighbor_graph)} stations")
            hubs_after, endpoints_after = self._identify_hubs_and_endpoints(neighbor_graph)
            print(f"  Hubs (3+ neighbors): {len(hubs_after)} stations (↑{len(hubs_after) - len(hubs)})")
            print(f"  Endpoints (1 neighbor): {len(endpoints_after)} stations (↑{len(endpoints_after) - len(endpoints)})")

            # FINAL FILTER: Only keep hubs and endpoints that are connected to origin
            print(f"\n=== FINAL FILTER: Hubs + Endpoints (origin-connected only) ===")
            all_destination_evas, filter_stats = self._filter_graph_to_hubs_and_endpoints(
                neighbor_graph,
                origin_connected_stations=origin_connected_stations
            )
            print(f"Destinations to fetch: {len(all_destination_evas)} stations")
            print(f"  (Filtered to only stations reachable from {station_name})")
            print(f"\nFiltering breakdown:")
            print(f"  Total in graph: {filter_stats['total']}")
            print(f"  Pass-through (2 neighbors): {filter_stats['pass_through']} (excluded)")
            print(f"  Not origin-connected: {filter_stats['not_connected']} (excluded)")
            print(f"  Kept (hubs + endpoints, origin-connected): {len(all_destination_evas)}")

            # Safety check: if we filtered everything out, fall back to all destinations
            if len(all_destination_evas) == 0:
                print(f"⚠️ Warning: Filter too aggressive, falling back to all destinations")
                all_destination_evas = self._extract_all_destinations(departures)
        else:
            # Original behavior: extract all destinations
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
            max_connections,
            neighbor_graph=neighbor_graph  # Pass for debugging stats
        )

        print(f"\n✅ Created {len(connections)} connections (100% real data, no estimates!)\n")

        # Note: Filtering now happens BEFORE fetching data (early filtering)
        # This improves performance by not fetching data we don't need

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

        # Analyze station neighbors and mark hubs/endpoints
        self._analyze_station_neighbors(origin_station, connections)

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

        IMPORTANT: Handles station fragmentation by fetching all related EVAs
        (e.g., Berlin Hbf, Berlin Hbf (S-Bahn), Berlin Hbf (tief) all share arrivals)
        """
        print(f"\n=== FETCHING PLANS FOR {len(destination_evas)} DESTINATIONS ===")

        # Expand to include all related EVAs (handles station fragmentation)
        eva_to_related = {}  # Maps each EVA to all its related EVAs
        all_evas_to_fetch = set()

        for eva in destination_evas:
            related = get_all_related_evas(eva)
            eva_to_related[eva] = related
            all_evas_to_fetch.update(related)

        print(f"Expanded to {len(all_evas_to_fetch)} EVAs (including related platforms/sections)")

        # Only fetch current and future hours to avoid 404s for past data
        current_hour = datetime.now().hour
        # Fetch from current hour through next 12 hours (wrapping to next day if needed)
        hours_to_fetch = [(current_hour + i) % 24 for i in range(13)]
        print(f"Fetching hours: {hours_to_fetch}")

        # Limit parallelism to avoid overwhelming the API
        semaphore = asyncio.Semaphore(config.MAX_PARALLEL_STATION_FETCHES)

        # Track cache performance
        cache_hits = 0
        api_fetches = 0

        async def fetch_one(eva: str) -> Tuple[str, Optional[Dict], str]:
            """Fetch plan data for one station with rate limiting."""
            nonlocal cache_hits, api_fetches

            async with semaphore:
                # Check cache first
                cached_plan = self.cache_service.load_station_plan(eva, date_str)
                if cached_plan is not None:
                    cache_hits += 1
                    return (eva, cached_plan, "CACHED")

                # Fetch from API - only fetch current and future hours
                try:
                    plan_data = await self.api_client.get_full_plan(eva, date_str, hours_to_fetch)
                    # Cache it
                    self.cache_service.save_station_plan(eva, date_str, plan_data)
                    api_fetches += 1
                    return (eva, plan_data, "API")
                except Exception as e:
                    # Get station name for error logging
                    station_info = STATIONS_BY_EVA.get(eva, {})
                    station_name = station_info.get("name", eva)
                    print(f"  ERROR: {eva} ({station_name}): {e}")
                    return (eva, None, "ERROR")

        # Fetch all related EVAs in parallel
        results = await asyncio.gather(*[fetch_one(eva) for eva in all_evas_to_fetch])

        # Build fetched plans dict (EVA -> plan data)
        fetched_plans = {eva: plan for eva, plan, status in results if plan is not None}

        # Map each original destination EVA to aggregated plan from all related EVAs
        destination_plans = {}
        aggregation_debug_samples = []  # Track some examples for verification

        for original_eva, related_evas in eva_to_related.items():
            # Aggregate arrivals and departures from all related EVAs
            combined_arrivals = []
            combined_departures = []
            per_eva_counts = []  # For debugging aggregation

            for related_eva in related_evas:
                if related_eva in fetched_plans:
                    plan = fetched_plans[related_eva]
                    arrivals_count = len(plan.get("arrivals", []))
                    departures_count = len(plan.get("departures", []))
                    combined_arrivals.extend(plan.get("arrivals", []))
                    combined_departures.extend(plan.get("departures", []))

                    if arrivals_count > 0 or departures_count > 0:
                        station_info = STATIONS_BY_EVA.get(related_eva, {})
                        per_eva_counts.append((station_info.get("name", related_eva), arrivals_count, departures_count))

            # Store combined plan under original EVA
            if combined_arrivals or combined_departures:
                destination_plans[original_eva] = {
                    "arrivals": combined_arrivals,
                    "departures": combined_departures
                }

                # Debug: track aggregation for stations with multiple platforms
                if len(related_evas) > 1 and len(per_eva_counts) > 1:
                    main_station_info = STATIONS_BY_EVA.get(original_eva, {})
                    main_name = main_station_info.get("name", original_eva)
                    aggregation_debug_samples.append((main_name, len(combined_arrivals), per_eva_counts))

        # Calculate stats
        errors = sum(1 for _, plan, status in results if status == "ERROR")

        print(f"\nDestination plans cache performance:")
        print(f"  Cache hits: {cache_hits}")
        print(f"  API fetches: {api_fetches}")
        print(f"  Errors: {errors}")
        print(f"  Successfully loaded plans for {len(destination_plans)}/{len(destination_evas)} destinations")
        print(f"  (Aggregated from {len(fetched_plans)} platform/section EVAs)")

        # Show aggregation examples to verify it's working
        if aggregation_debug_samples:
            print(f"\n✓ Verified arrival aggregation for {len(aggregation_debug_samples)} multi-platform stations:")
            for station_name, total_arrivals, per_eva in aggregation_debug_samples[:5]:
                print(f"  {station_name}: {total_arrivals} total arrivals from {len(per_eva)} platforms")
                for name, arr_count, dep_count in per_eva:
                    print(f"    - {name}: {arr_count} arrivals, {dep_count} departures")
            if len(aggregation_debug_samples) > 5:
                print(f"  ... and {len(aggregation_debug_samples) - 5} more multi-platform stations")
        print()

        return destination_plans

    async def _build_connections_from_real_data(
        self,
        origin_station: Station,
        departures: List[Dict],
        destination_plans: Dict[str, Dict],
        max_connections: Optional[int] = None,
        neighbor_graph: Optional[Dict[str, Set[str]]] = None
    ) -> List[Connection]:
        """
        Build connections ONLY when we have real arrival data.
        No fake estimates - if we don't have the destination's arrival data, we skip it.

        Args:
            neighbor_graph: Optional graph for debugging stats (shows neighbor counts)
        """
        print("=== BUILDING CONNECTIONS FROM REAL DATA ===")
        connections = []
        seen_pairs: Set[tuple] = set()  # Track (train_number, destination_eva)

        # Debug stats
        missing_plan_count = 0
        missing_arrival_count = 0
        successful_match_count = 0

        # Track specific problematic destinations
        missing_plan_destinations = Counter()  # dest_name -> count
        missing_arrival_destinations = Counter()  # dest_name -> count

        # Track neighbor counts for missing destinations (for analysis)
        missing_plan_neighbor_counts = Counter()  # neighbor_count -> count
        missing_arrival_neighbor_counts = Counter()  # neighbor_count -> count

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
                    missing_plan_count += 1
                    missing_plan_destinations[dest_name] += 1

                    # Track neighbor count for analysis
                    if neighbor_graph and dest_eva in neighbor_graph:
                        neighbor_count = len(neighbor_graph[dest_eva])
                        missing_plan_neighbor_counts[neighbor_count] += 1
                    else:
                        missing_plan_neighbor_counts["unknown"] += 1

                    continue

                # Try to find matching arrival in destination's plan
                arrival_time = self._find_arrival_time(
                    destination_plans[dest_eva],
                    train_number,
                    departure_datetime,
                    debug_station=dest_name,  # Enable debugging for specific stations
                    train_type=train_type  # For S-Bahn specific debugging
                )

                # If no real arrival time found, SKIP this connection
                if not arrival_time:
                    missing_arrival_count += 1
                    missing_arrival_destinations[dest_name] += 1

                    # Track neighbor count for analysis
                    if neighbor_graph and dest_eva in neighbor_graph:
                        neighbor_count = len(neighbor_graph[dest_eva])
                        missing_arrival_neighbor_counts[neighbor_count] += 1
                    else:
                        missing_arrival_neighbor_counts["unknown"] += 1

                    continue

                successful_match_count += 1

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

        # Print debugging summary
        print(f"\n=== CONNECTION MATCHING STATISTICS ===")
        print(f"  Successful matches: {successful_match_count}")
        print(f"  Missing destination plans: {missing_plan_count}")
        print(f"  Missing arrival times: {missing_arrival_count}")
        print(f"  Total connections created: {len(connections)}")

        if missing_plan_count > 0 or missing_arrival_count > 0:
            print(f"\n💡 Missing connections could be due to:")

            if missing_plan_count > 0:
                print(f"  • Destinations not in fetch list ({missing_plan_count} occurrences)")

                # Show neighbor count distribution
                if neighbor_graph and missing_plan_neighbor_counts:
                    print(f"\n    Neighbor count distribution (missing plans):")
                    sorted_counts = sorted(missing_plan_neighbor_counts.items(),
                                         key=lambda x: x[0] if isinstance(x[0], int) else 999)
                    for neighbor_count, occurrence_count in sorted_counts:
                        if neighbor_count == 2:
                            print(f"      {neighbor_count} neighbors (pass-through): {occurrence_count} stations ⬅️  FILTERED OUT")
                        elif neighbor_count == "unknown":
                            print(f"      Unknown: {occurrence_count} stations (not in graph)")
                        else:
                            print(f"      {neighbor_count} neighbors: {occurrence_count} stations")

                top_missing_plans = missing_plan_destinations.most_common(10)
                if top_missing_plans:
                    print(f"\n    Top destinations missing plans:")
                    for dest_name, count in top_missing_plans:
                        print(f"      - {dest_name}: {count}x")

            if missing_arrival_count > 0:
                print(f"\n  • Train arrivals outside time window ({missing_arrival_count} occurrences)")

                # Show neighbor count distribution
                if neighbor_graph and missing_arrival_neighbor_counts:
                    print(f"\n    Neighbor count distribution (missing arrivals):")
                    sorted_counts = sorted(missing_arrival_neighbor_counts.items(),
                                         key=lambda x: x[0] if isinstance(x[0], int) else 999)
                    for neighbor_count, occurrence_count in sorted_counts:
                        if neighbor_count == 2:
                            print(f"      {neighbor_count} neighbors (pass-through): {occurrence_count} occurrences ⬅️  But why fetched?")
                        elif neighbor_count == "unknown":
                            print(f"      Unknown: {occurrence_count} occurrences (not in graph)")
                        else:
                            print(f"      {neighbor_count} neighbors: {occurrence_count} occurrences")

                top_missing_arrivals = missing_arrival_destinations.most_common(10)
                if top_missing_arrivals:
                    print(f"\n    Top destinations with missing arrivals:")
                    for dest_name, count in top_missing_arrivals:
                        print(f"      - {dest_name}: {count}x")

                print(f"\n    ℹ️  Common causes:")
                print(f"       - Train arrives outside fetched time window (current + 13 hours)")
                print(f"       - Train number changes mid-route (e.g., S-Bahn line renumbering)")
                print(f"       - Station fragmentation we didn't catch")

        return connections

    def _find_arrival_time(
        self,
        destination_plan: Dict,
        train_number: str,
        departure_time: datetime,
        debug_station: str = None,
        train_type: str = None
    ) -> Optional[datetime]:
        """Find the arrival time for a specific train at the destination station."""
        arrivals = destination_plan.get("arrivals", [])

        # Debug mode for specific stations of interest OR S-Bahn at major stations
        is_sbahn = train_type and train_type.upper() == 'S'
        is_major_station = debug_station and any(name in debug_station.lower() for name in
                                              ['friedrichstraße', 'ostkreuz', 'westkreuz', 'alexanderplatz'])
        enable_debug = (debug_station and any(name in debug_station.lower() for name in
                                              ['berlin', 'bologna', 'münchen', 'muenchen', 'arnhem']))

        # Extra verbose for S-Bahn at problem stations
        enable_sbahn_debug = is_sbahn and is_major_station

        if enable_debug:
            print(f"    🔍 Looking for train {train_type} {train_number} at {debug_station}")
            print(f"       Departing at: {departure_time.strftime('%Y-%m-%d %H:%M')}")
            print(f"       Checking {len(arrivals)} arrivals (aggregated from all related platforms/sections)")

        if enable_sbahn_debug and not enable_debug:
            print(f"    🚆 S-Bahn debug: Looking for S {train_number} at {debug_station}")
            print(f"       Departure time: {departure_time.strftime('%H:%M')}, checking {len(arrivals)} arrivals")

        for arrival in arrivals:
            if arrival.get("number") == train_number:
                # Parse arrival time
                time_str = arrival.get("time", "")
                if len(time_str) == 10:
                    try:
                        arrival_dt = datetime.strptime(time_str, "%y%m%d%H%M")

                        # Sanity check: arrival should be after departure
                        time_diff = (arrival_dt - departure_time).total_seconds() / 60

                        # Should be within reasonable range (1 min to 24 hours)
                        # Note: S-Bahn stations can be 1-2 minutes apart!
                        if 1 <= time_diff <= 1440:
                            if enable_debug:
                                print(f"       ✓ Found match! Arrives at: {arrival_dt.strftime('%Y-%m-%d %H:%M')} (travel: {int(time_diff)}min)")
                            return arrival_dt
                        elif enable_debug:
                            print(f"       ✗ Time diff out of range: {int(time_diff)}min")

                    except ValueError as e:
                        if enable_debug:
                            print(f"       ✗ Failed to parse time: {time_str}")
                        continue

        if enable_debug:
            print(f"       ✗ No matching arrival found")
            if len(arrivals) > 0:
                sample = arrivals[:3]
                print(f"       Sample of available trains:")
                for arr in sample:
                    print(f"         - {arr.get('type', '?')} {arr.get('number', '?')} at {arr.get('time', '?')}")

        # S-Bahn specific debugging - show what S-Bahn trains ARE arriving
        if enable_sbahn_debug:
            # Find S-Bahn arrivals around the expected time
            expected_time_range = 30  # minutes
            sbahn_arrivals = []
            for arr in arrivals:
                if arr.get('type', '').upper() == 'S':
                    time_str = arr.get('time', '')
                    if len(time_str) == 10:
                        try:
                            arr_time = datetime.strptime(time_str, "%y%m%d%H%M")
                            time_diff = (arr_time - departure_time).total_seconds() / 60
                            if -5 <= time_diff <= expected_time_range:
                                sbahn_arrivals.append((arr.get('number'), arr_time, time_diff))
                        except:
                            pass

            if sbahn_arrivals:
                print(f"       ⚠️  S-Bahn MISMATCH: Looking for S {train_number}, but found these S-Bahn arrivals:")
                for num, arr_time, diff in sbahn_arrivals[:5]:
                    print(f"         - S {num} arriving at {arr_time.strftime('%H:%M')} (+{int(diff)}min)")
            else:
                print(f"       ⚠️  NO S-Bahn arrivals found within {expected_time_range} minutes of departure")

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

    def _analyze_station_neighbors(self, origin_station: Station, connections: List[Connection]) -> None:
        """
        Analyze connections to determine station neighbor count and mark hubs/endpoints.

        A station is considered:
        - A HUB if it has 3 or more unique destination neighbors
        - An ENDPOINT if it has exactly 1 unique destination neighbor

        Args:
            origin_station: The origin station to analyze
            connections: List of connections from this station
        """
        # Count unique destination stations
        unique_destinations = set()
        for conn in connections:
            unique_destinations.add(conn.destination_id)

        neighbor_count = len(unique_destinations)

        # Update origin station metadata
        origin_station.neighbor_count = neighbor_count
        origin_station.is_hub = neighbor_count >= config.HUB_STATION_MIN_NEIGHBORS
        origin_station.is_endpoint = neighbor_count == 1

        print(f"\n=== STATION ANALYSIS ===")
        print(f"Station: {origin_station.name}")
        print(f"Unique Neighbors: {neighbor_count}")
        print(f"Is Hub: {origin_station.is_hub}")
        print(f"Is Endpoint: {origin_station.is_endpoint}\n")

    def _build_neighbor_graph_from_departures(
        self,
        departures: List[Dict],
        debug: bool = False
    ) -> Dict[str, Set[str]]:
        """
        Build neighbor graph from departure path_stations using immediate neighbor logic.

        For path ["A", "B", "C", "D"]:
        - A neighbors: {B}
        - B neighbors: {A, C}
        - C neighbors: {B, D}
        - D neighbors: {C}

        Args:
            departures: List of departure dictionaries from API
            debug: Enable detailed debugging output

        Returns:
            Dict mapping EVA number to set of neighbor EVA numbers
        """
        neighbor_graph: Dict[str, Set[str]] = {}
        unresolved_stations = Counter()  # Track stations we can't resolve

        for departure in departures:
            path_stations = departure.get("path_stations", [])
            if len(path_stations) < 2:
                continue

            train_type = departure.get("type", "")
            train_number = departure.get("number", "")

            # Build immediate neighbor relationships
            for i in range(len(path_stations) - 1):
                station_a_name = path_stations[i]
                station_b_name = path_stations[i + 1]

                # Resolve to EVA numbers
                station_a_info = STATIONS_BY_NAME.get(station_a_name.lower())
                station_b_info = STATIONS_BY_NAME.get(station_b_name.lower())

                # Debug: Track unresolved stations
                if not station_a_info:
                    unresolved_stations[station_a_name] += 1
                    if debug:
                        print(f"  ⚠️  Cannot resolve: '{station_a_name}' ({train_type} {train_number})")
                if not station_b_info:
                    unresolved_stations[station_b_name] += 1
                    if debug:
                        print(f"  ⚠️  Cannot resolve: '{station_b_name}' ({train_type} {train_number})")

                if not station_a_info or not station_b_info:
                    continue

                eva_a = station_a_info.get("eva")
                eva_b = station_b_info.get("eva")

                if not eva_a or not eva_b:
                    if debug:
                        print(f"  ⚠️  Missing EVA: '{station_a_name}' or '{station_b_name}'")
                    continue

                # Add bidirectional neighbor relationship
                if eva_a not in neighbor_graph:
                    neighbor_graph[eva_a] = set()
                if eva_b not in neighbor_graph:
                    neighbor_graph[eva_b] = set()

                neighbor_graph[eva_a].add(eva_b)
                neighbor_graph[eva_b].add(eva_a)

        # Report unresolved stations
        if unresolved_stations:
            print(f"\n⚠️  UNRESOLVED STATIONS: {len(unresolved_stations)} unique station names couldn't be matched")
            top_unresolved = unresolved_stations.most_common(10)
            for station_name, count in top_unresolved:
                print(f"  '{station_name}': {count} occurrences")
            if len(unresolved_stations) > 10:
                print(f"  ... and {len(unresolved_stations) - 10} more")

        return neighbor_graph

    def _identify_hubs_and_endpoints(
        self,
        neighbor_graph: Dict[str, Set[str]]
    ) -> Tuple[List[str], List[str]]:
        """
        Identify hubs (3+ neighbors) and endpoints (1 neighbor) from graph.

        Args:
            neighbor_graph: Dict mapping EVA to set of neighbor EVAs

        Returns:
            Tuple of (hub_evas, endpoint_evas)
        """
        hubs = []
        endpoints = []

        for eva, neighbors in neighbor_graph.items():
            neighbor_count = len(neighbors)

            if neighbor_count >= 3:
                hubs.append(eva)
            elif neighbor_count == 1:
                endpoints.append(eva)
            # Skip stations with exactly 2 neighbors (pass-through)

        return hubs, endpoints

    async def _enhance_graph_with_second_sweep(
        self,
        neighbor_graph: Dict[str, Set[str]],
        stations_to_sweep: List[str],
        deutschland_ticket_only: bool,
        train_categories: Optional[List[str]],
        date_str: str
    ) -> Dict[str, Set[str]]:
        """
        Enhance neighbor graph by fetching departures from hubs and endpoints.

        Second sweep reveals connections we couldn't see from origin alone.

        Args:
            neighbor_graph: Initial graph from first sweep
            stations_to_sweep: List of EVA numbers to fetch (hubs + endpoints)
            deutschland_ticket_only: Apply Deutschland-Ticket filter
            train_categories: Apply train category filter
            date_str: Date for caching

        Returns:
            Enhanced neighbor graph
        """
        total = len(stations_to_sweep)
        print(f"Fetching departures for {total} stations (hubs + endpoints)...")

        cache_hits = 0
        api_fetches = 0

        for idx, station_eva in enumerate(stations_to_sweep, 1):
            try:
                # Fetch from all related EVAs (handles fragmented stations)
                related_evas = get_all_related_evas(station_eva)
                all_station_departures = []

                for eva in related_evas:
                    # Check cache first!
                    cached_plan = self.cache_service.load_station_plan(eva, date_str)

                    if cached_plan is not None:
                        # Extract departures from cached plan
                        eva_departures = cached_plan.get("departures", [])
                        all_station_departures.extend(eva_departures)
                        cache_hits += 1
                        cache_status = "CACHED"
                    else:
                        # Cache miss - fetch from API
                        eva_departures = await self.api_client.get_departures(eva)
                        all_station_departures.extend(eva_departures)

                        # Cache the departures for future use
                        plan_data = {
                            "departures": eva_departures,
                            "arrivals": []  # Don't have arrivals from get_departures
                        }
                        self.cache_service.save_station_plan(eva, date_str, plan_data)

                        api_fetches += 1
                        cache_status = "API"

                # Deduplicate
                seen = set()
                station_departures = []
                for dep in all_station_departures:
                    key = (dep.get('number'), dep.get('time'), dep.get('destination'))
                    if key not in seen:
                        seen.add(key)
                        station_departures.append(dep)

                # Apply same train type filters as first sweep
                filtered_departures = self._filter_departures_by_train_type(
                    departures=station_departures,
                    deutschland_ticket_only=deutschland_ticket_only,
                    train_categories=train_categories
                )

                # Get station name for logging
                station_info = STATIONS_BY_EVA.get(station_eva, {})
                station_name = station_info.get("name", station_eva)

                platforms_note = f" (from {len(related_evas)} platforms)" if len(related_evas) > 1 else ""
                print(f"  [{idx}/{total}] {station_name}{platforms_note}: "
                      f"{len(station_departures)} departures → {len(filtered_departures)} after filter")

                # Build graph from these departures
                enhanced_graph = self._build_neighbor_graph_from_departures(filtered_departures)

                # Merge into main graph
                for eva, neighbors in enhanced_graph.items():
                    if eva not in neighbor_graph:
                        neighbor_graph[eva] = set()
                    neighbor_graph[eva].update(neighbors)

            except Exception as e:
                station_info = STATIONS_BY_EVA.get(station_eva, {})
                station_name = station_info.get("name", station_eva)
                print(f"  [{idx}/{total}] {station_eva} ({station_name}): ERROR - {e}")
                continue

        print(f"\nSecond sweep cache performance: {cache_hits} hits, {api_fetches} API calls")
        return neighbor_graph

    def _extract_stations_from_departures(
        self,
        departures: List[Dict]
    ) -> Set[str]:
        """
        Extract all unique station EVAs that appear in departure path_stations.

        Args:
            departures: List of departure dictionaries

        Returns:
            Set of EVA numbers that appear in at least one departure path
        """
        stations_in_paths = set()

        for departure in departures:
            path_stations = departure.get("path_stations", [])
            for station_name in path_stations:
                station_info = STATIONS_BY_NAME.get(station_name.lower())
                if station_info and station_info.get("eva"):
                    stations_in_paths.add(station_info["eva"])

        return stations_in_paths

    def _filter_graph_to_hubs_and_endpoints(
        self,
        neighbor_graph: Dict[str, Set[str]],
        origin_connected_stations: Optional[Set[str]] = None
    ) -> Tuple[List[str], Dict[str, int]]:
        """
        Filter graph to only hubs (3+ neighbors) and endpoints (1 neighbor).

        Optionally filter to only stations connected to origin (appear in origin's departure paths).

        Args:
            neighbor_graph: Complete neighbor graph
            origin_connected_stations: Set of stations that appear in origin's departure paths

        Returns:
            Tuple of (filtered_evas, stats_dict)
        """
        filtered = []
        stats = {
            'total': len(neighbor_graph),
            'pass_through': 0,
            'not_connected': 0,
            'hubs_kept': 0,
            'endpoints_kept': 0
        }

        for eva, neighbors in neighbor_graph.items():
            neighbor_count = len(neighbors)

            # Must be hub or endpoint
            if neighbor_count != 1 and neighbor_count < 3:
                stats['pass_through'] += 1
                continue  # Skip pass-through stations (2 neighbors)

            # If we have origin-connected filter, only include those stations
            if origin_connected_stations is not None:
                if eva not in origin_connected_stations:
                    stats['not_connected'] += 1
                    continue  # Skip stations not connected to origin

            filtered.append(eva)

            if neighbor_count == 1:
                stats['endpoints_kept'] += 1
            elif neighbor_count >= 3:
                stats['hubs_kept'] += 1

        return filtered, stats

    def _filter_departures_by_train_type(
        self,
        departures: List[Dict],
        deutschland_ticket_only: bool = False,
        train_categories: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Filter departures by train type BEFORE extracting destinations.
        This is a critical performance optimization - we avoid fetching data for trains we won't use.

        Args:
            departures: List of departure dictionaries from API
            deutschland_ticket_only: Only include trains valid for Deutschland-Ticket
            train_categories: Filter by train categories (e.g., ["regional", "intercity"])

        Returns:
            Filtered list of departures
        """
        if not deutschland_ticket_only and not train_categories:
            return departures  # No filtering needed

        filtered = []
        rejected_types = Counter()  # Track which train types were rejected

        for departure in departures:
            train_type = departure.get("type", "")
            if not train_type:
                continue

            rejected = False

            # Check Deutschland-Ticket validity
            if deutschland_ticket_only:
                if not is_deutschland_ticket_valid(train_type):
                    rejected_types[train_type] += 1
                    rejected = True

            # Check train category
            if not rejected and train_categories:
                category = classify_train_type(train_type)
                if category not in train_categories:
                    rejected_types[train_type] += 1
                    rejected = True

            if not rejected:
                filtered.append(departure)

        # Debug output: show rejected train types
        if rejected_types:
            rejected_list = [f"{train_type} ({count})" for train_type, count in rejected_types.most_common()]
            print(f"  Rejected train types: {', '.join(rejected_list)}")

        print(f"  Train type filter: {len(filtered)}/{len(departures)} departures kept")
        return filtered

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

                        # Should be within reasonable range (1 min to 24 hours)
                        # Note: S-Bahn stations can be 1-2 minutes apart!
                        if 1 <= time_diff <= 1440:
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
