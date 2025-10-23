import openrouteservice
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import math

class HOSCompliantTripSimulator:
    """
    Simulates truck driver trips while adhering to FMCSA Hours of Service regulations
    for property-carrying drivers on 70hr/8day schedule.
    Output format matches frontend TypeScript interfaces.
    """
    
    def __init__(self, ors_api_key: str):
        self.client = openrouteservice.Client(key=ors_api_key)
        
        # HOS Regulations (70hr/8day for property carriers)
        self.MAX_DRIVING_HOURS = 11  # Max driving in a shift
        self.MAX_DUTY_WINDOW = 14  # Max duty window hours
        self.MIN_OFF_DUTY = 10  # Min consecutive hours off duty
        self.BREAK_REQUIRED_AFTER = 8  # 30-min break after 8hrs driving
        self.BREAK_DURATION = 0.5  # 30 minutes in hours
        self.MAX_WEEKLY_HOURS = 70  # 70 hours in 8 days
        
        # Assumptions
        self.FUEL_INTERVAL_MILES = 1000  # Fuel every 1000 miles
        self.FUEL_DURATION = 0.5  # 30 minutes for fueling
        self.PICKUP_DURATION = 1.0  # 1 hour for pickup
        self.DROPOFF_DURATION = 1.0  # 1 hour for dropoff
        self.AVG_SPEED_MPH = 55  # Average highway speed
    
    def get_route(self, start_coords: Tuple[float, float], 
                  end_coords: Tuple[float, float]) -> Dict:
        """
        Get route information from OpenRouteService
        coords format: (longitude, latitude)
        """
        try:
            route = self.client.directions(
                coordinates=[start_coords, end_coords],
                profile='driving-hgv',
                format='geojson',
                units='mi',
                instructions=True,
                elevation=False
            )
            
            segment = route['features'][0]['properties']['segments'][0]
            distance_miles = segment['distance']
            duration_hours = segment['duration'] / 3600
            
            # Extract route coordinates in frontend format {lat, lng}
            coordinates = route['features'][0]['geometry']['coordinates']
            route_coordinates = [
                {'lat': coord[1], 'lng': coord[0]} 
                for coord in coordinates
            ]
            
            return {
                'distance_miles': distance_miles,
                'duration_hours': duration_hours,
                'route_coordinates': route_coordinates
            }
        except Exception as e:
            print(f"Route API error: {e}. Using fallback calculation.")
            distance = self._haversine_distance(start_coords, end_coords)
            # Generate approximate route coordinates
            route_coords = self._interpolate_coordinates(start_coords, end_coords, 20)
            return {
                'distance_miles': distance,
                'duration_hours': distance / self.AVG_SPEED_MPH,
                'route_coordinates': route_coords
            }
    
    def _interpolate_coordinates(self, start: Tuple[float, float], 
                                 end: Tuple[float, float], 
                                 num_points: int) -> List[Dict]:
        """Generate interpolated coordinates between start and end"""
        lon1, lat1 = start
        lon2, lat2 = end
        
        coords = []
        for i in range(num_points + 1):
            t = i / num_points
            lat = lat1 + (lat2 - lat1) * t
            lng = lon1 + (lon2 - lon1) * t
            coords.append({'lat': lat, 'lng': lng})
        
        return coords
    
    def _interpolate_location(self, start: Tuple[float, float], 
                              end: Tuple[float, float], 
                              progress: float) -> Tuple[float, float]:
        """
        Calculate intermediate location between start and end
        progress: 0.0 (start) to 1.0 (end)
        Returns: (longitude, latitude)
        """
        lon1, lat1 = start
        lon2, lat2 = end
        
        # Linear interpolation
        lon = lon1 + (lon2 - lon1) * progress
        lat = lat1 + (lat2 - lat1) * progress
        
        return (lon, lat)
    
    def _haversine_distance(self, coord1: Tuple[float, float], 
                           coord2: Tuple[float, float]) -> float:
        """Calculate distance between two coordinates in miles"""
        lon1, lat1 = coord1
        lon2, lat2 = coord2
        
        R = 3959  # Earth's radius in miles
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def simulate_trip(self, current_location: Tuple[float, float],
                     pickup_location: Tuple[float, float],
                     dropoff_location: Tuple[float, float],
                     current_cycle_hours: float,
                     start_time: datetime = None) -> Dict:
        """
        Simulate complete trip with HOS compliance
        Returns trip data in frontend-compatible format matching TripResponse interface
        """
        if start_time is None:
            start_time = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
        
        # Get route segments
        leg1 = self.get_route(current_location, pickup_location)
        leg2 = self.get_route(pickup_location, dropoff_location)
        
        total_distance = leg1['distance_miles'] + leg2['distance_miles']
        
        # Combine route coordinates
        all_coords = leg1['route_coordinates'] + leg2['route_coordinates']
        
        # Initialize simulation - start from midnight of the first day
        trip_start_date = start_time.date()
        midnight = datetime.combine(trip_start_date, datetime.min.time())
        
        simulation = {
            'trip_start_time': start_time,  # Actual work start time (e.g., 6 AM)
            'current_time': midnight,  # Start from midnight for complete 24-hour log
            'current_duty_hours': 0,
            'current_driving_hours': 0,
            'current_cycle_hours': current_cycle_hours,
            'miles_driven': 0,
            'current_day': 1,
            'events': [],
            'fuel_stops': [],
            'rest_stops': [],
            'break_stops': []
        }
        
        # Add off-duty period from midnight to work start
        if start_time > midnight:
            self._add_event(simulation, 'off_duty', 'Off Duty (Pre-work)', current_location)
            simulation['current_time'] = start_time
        
        # Start trip
        self._add_event(simulation, 'on_duty', 'Trip Start', current_location)
        
        # Leg 1: Current to Pickup
        simulation = self._simulate_leg(
            simulation, 
            leg1['distance_miles'], 
            'to_pickup',
            current_location,      # START of this leg
            pickup_location        # END of this leg
        )
        
        # Pickup activity
        self._add_event(simulation, 'on_duty', 'Pickup - Loading', pickup_location)
        simulation['current_time'] += timedelta(hours=self.PICKUP_DURATION)
        simulation['current_duty_hours'] += self.PICKUP_DURATION
        simulation['current_cycle_hours'] += self.PICKUP_DURATION
        
        # Leg 2: Pickup to Dropoff
        simulation = self._simulate_leg(
            simulation,
            leg2['distance_miles'],
            'to_dropoff',
            pickup_location,       # START of this leg
            dropoff_location       # END of this leg
        )
        
        # Dropoff activity
        self._add_event(simulation, 'on_duty', 'Dropoff - Unloading', dropoff_location)
        simulation['current_time'] += timedelta(hours=self.DROPOFF_DURATION)
        simulation['current_duty_hours'] += self.DROPOFF_DURATION
        simulation['current_cycle_hours'] += self.DROPOFF_DURATION
        
        # End of trip
        self._add_event(simulation, 'off_duty', 'Trip Complete', dropoff_location)
        
        # Generate daily logs
        daily_logs = self._generate_daily_logs(simulation['events'], midnight)
        
        # Calculate total days
        total_days = len(daily_logs)
        
        return {
            'route': {
                'distance_miles': round(total_distance, 1),
                'duration_hours': round(total_distance / self.AVG_SPEED_MPH, 1),
                'route_coordinates': all_coords,
                'segments': []
            },
            'stops': {
                'pickup': {
                    'lat': pickup_location[1],
                    'lng': pickup_location[0],
                    'name': 'Pickup Location',
                    'duration': self.PICKUP_DURATION
                },
                'dropoff': {
                    'lat': dropoff_location[1],
                    'lng': dropoff_location[0],
                    'name': 'Dropoff Location',
                    'duration': self.DROPOFF_DURATION
                },
                'fuel_stops': simulation['fuel_stops'],
                'rest_stops': simulation['rest_stops'],
                'break_stops': simulation['break_stops']
            },
            'timeline': {
                'start_time': start_time.strftime('%H:%M'),
                'estimated_completion': simulation['current_time'].strftime('%H:%M'),
                'total_days': total_days
            },
            'hos_summary': {
                'remaining_70hr_cycle': self.MAX_WEEKLY_HOURS - simulation['current_cycle_hours'],
                'used_70hr_cycle': simulation['current_cycle_hours'],
                'driving_time_used': round(simulation['current_driving_hours'], 1),
                'on_duty_time_used': round(simulation['current_duty_hours'], 1)
            },
            'logs': daily_logs
        }
    
    def _simulate_leg(self, simulation: Dict, distance: float, 
                     leg_type: str, start_location: Tuple[float, float],
                     destination: Tuple[float, float]) -> Dict:
        """
        Simulate a leg of the journey with HOS compliance
        
        Args:
            simulation: Current simulation state
            distance: Total distance of this leg in miles
            leg_type: Type of leg (e.g., 'to_pickup', 'to_dropoff')
            start_location: Starting coordinates (longitude, latitude)
            destination: Destination coordinates (longitude, latitude)
        """
        remaining_distance = distance
        distance_covered_this_leg = 0  # Track progress on THIS specific leg
        last_fuel_miles = simulation['miles_driven']
        
        while remaining_distance > 0:
            # Check if 10-hour rest needed
            if simulation['current_duty_hours'] >= self.MAX_DUTY_WINDOW:
                # Calculate actual rest location based on current position
                progress = distance_covered_this_leg / distance if distance > 0 else 0
                rest_location = self._interpolate_location(start_location, destination, progress)
                simulation = self._take_rest(simulation, self.MIN_OFF_DUTY, 
                                            'sleeper_berth', rest_location)
            
            # Check if 30-min break needed after 8 hours driving
            if simulation['current_driving_hours'] >= self.BREAK_REQUIRED_AFTER:
                progress = distance_covered_this_leg / distance if distance > 0 else 0
                break_location = self._interpolate_location(start_location, destination, progress)
                simulation = self._take_break(simulation, break_location)
            
            # Calculate available driving time
            available_duty_time = self.MAX_DUTY_WINDOW - simulation['current_duty_hours']
            available_drive_time = min(
                self.MAX_DRIVING_HOURS - simulation['current_driving_hours'],
                available_duty_time,
                self.BREAK_REQUIRED_AFTER - (simulation['current_driving_hours'] % self.BREAK_REQUIRED_AFTER)
            )
            
            # Calculate distance we can drive
            can_drive_miles = available_drive_time * self.AVG_SPEED_MPH
            drive_miles = min(can_drive_miles, remaining_distance)
            
            # Check if we need fuel before this segment
            miles_since_fuel = simulation['miles_driven'] - last_fuel_miles
            if miles_since_fuel + drive_miles >= self.FUEL_INTERVAL_MILES:
                # Need to fuel during this segment
                drive_to_fuel = self.FUEL_INTERVAL_MILES - miles_since_fuel
                drive_hours = drive_to_fuel / self.AVG_SPEED_MPH
                
                # Drive to fuel stop
                self._add_event(simulation, 'driving', f'Driving ({leg_type})', 
                              f"En route {leg_type}")
                simulation['current_time'] += timedelta(hours=drive_hours)
                simulation['current_driving_hours'] += drive_hours
                simulation['current_duty_hours'] += drive_hours
                simulation['current_cycle_hours'] += drive_hours
                simulation['miles_driven'] += drive_to_fuel
                distance_covered_this_leg += drive_to_fuel
                remaining_distance -= drive_to_fuel
                
                # Calculate actual fuel stop location
                progress = distance_covered_this_leg / distance if distance > 0 else 0
                fuel_location = self._interpolate_location(start_location, destination, progress)
                
                # Fuel stop at calculated location
                self._add_fuel_stop(simulation, fuel_location)
                last_fuel_miles = simulation['miles_driven']
                
                continue
            
            # Normal drive segment
            drive_hours = drive_miles / self.AVG_SPEED_MPH
            
            self._add_event(simulation, 'driving', f'Driving ({leg_type})', 
                          f"En route {leg_type}")
            simulation['current_time'] += timedelta(hours=drive_hours)
            simulation['current_driving_hours'] += drive_hours
            simulation['current_duty_hours'] += drive_hours
            simulation['current_cycle_hours'] += drive_hours
            simulation['miles_driven'] += drive_miles
            distance_covered_this_leg += drive_miles
            remaining_distance -= drive_miles
        
        return simulation
    
    def _add_fuel_stop(self, simulation: Dict, location: Tuple[float, float]):
        """Add a fuel stop at the actual calculated location"""
        self._add_event(simulation, 'on_duty', 'Fuel Stop', location)
        
        fuel_stop = {
            'lat': location[1],  # latitude
            'lng': location[0],  # longitude
            'name': 'Fuel Stop',
            'distance': round(simulation['miles_driven'], 0),
            'duration': self.FUEL_DURATION
        }
        simulation['fuel_stops'].append(fuel_stop)
        
        simulation['current_time'] += timedelta(hours=self.FUEL_DURATION)
        simulation['current_duty_hours'] += self.FUEL_DURATION
        simulation['current_cycle_hours'] += self.FUEL_DURATION
    
    def _take_break(self, simulation: Dict, location: Tuple[float, float]) -> Dict:
        """Take required 30-minute break at the actual calculated location"""
        self._add_event(simulation, 'on_duty', '30-min Break', location)
        
        break_stop = {
            'lat': location[1],  # latitude
            'lng': location[0],  # longitude
            'name': '30-Minute Break',
            'time': simulation['current_time'].strftime('%H:%M'),
            'duration': self.BREAK_DURATION,
            'type': '30-min break'
        }
        simulation['break_stops'].append(break_stop)
        
        simulation['current_time'] += timedelta(hours=self.BREAK_DURATION)
        simulation['current_duty_hours'] += self.BREAK_DURATION
        simulation['current_cycle_hours'] += self.BREAK_DURATION
        simulation['current_driving_hours'] = 0  # Reset 8-hour driving clock
        
        return simulation
    
    def _take_rest(self, simulation: Dict, duration: float, 
                   rest_type: str, location: Tuple[float, float]) -> Dict:
        """Take required 10-hour rest at the actual calculated location"""
        self._add_event(simulation, rest_type, '10-hour Rest', location)
        
        rest_stop = {
            'lat': location[1],  # latitude
            'lng': location[0],  # longitude
            'name': '10-Hour Rest',
            'time': simulation['current_time'].strftime('%H:%M'),
            'duration': duration,
            'day': self._get_day_number(simulation['current_time'], 
                                       simulation.get('trip_start_time'))
        }
        simulation['rest_stops'].append(rest_stop)
        
        simulation['current_time'] += timedelta(hours=duration)
        simulation['current_duty_hours'] = 0
        simulation['current_driving_hours'] = 0
        
        return simulation
    
    def _get_day_number(self, current_time: datetime, trip_start_time: datetime) -> int:
        """Calculate which day of the trip we're on based on calendar days"""
        if trip_start_time is None:
            return 1
        start_date = trip_start_time.date()
        current_date = current_time.date()
        return (current_date - start_date).days + 1
    
    def _add_event(self, simulation: Dict, status: str, 
                   description: str, location):
        """Add an event to the simulation"""
        # Handle location - could be string or tuple
        if isinstance(location, tuple):
            location_name = description
        else:
            location_name = description if isinstance(location, str) else "Location"
        
        # Calculate day number based on calendar day
        day = self._get_day_number(simulation['current_time'], 
                                   simulation.get('trip_start_time'))
        
        simulation['events'].append({
            'time': simulation['current_time'],
            'status': status,
            'description': description,
            'location': location_name,
            'day': day
        })
    
    def _generate_daily_logs(self, events: List[Dict], trip_start_midnight: datetime) -> List[Dict]:
        """Generate daily log sheets from events matching LogSheetData interface"""
        daily_logs = {}
        
        # Group events by calendar day
        for i, event in enumerate(events):
            event_date = event['time'].date()
            day = event['day']
            
            if day not in daily_logs:
                daily_logs[day] = {
                    'date': event_date.strftime('%m/%d/%Y'),
                    'day': day,
                    'driverName': 'John Doe',
                    'carrierName': 'ELD Pro Transport',
                    'vehicleNumber': 'TRK-101',
                    'totalMiles': 0,
                    'dutyStatusChanges': [],
                    'remarks': [],
                    'totals': {
                        'offDuty': 0,
                        'sleeperBerth': 0,
                        'driving': 0,
                        'onDuty': 0
                    }
                }
            
            # Add duty status change
            time_str = event['time'].strftime('%H:%M')
            
            duty_change = {
                'time': time_str,
                'status': event['status'],
                'location': event['description']
            }
            
            daily_logs[day]['dutyStatusChanges'].append(duty_change)
            daily_logs[day]['remarks'].append(f"{time_str} - {event['description']}")
            
            # Calculate duration for totals
            if i < len(events) - 1:
                next_event = events[i + 1]
                duration_seconds = (next_event['time'] - event['time']).total_seconds()
                duration = duration_seconds / 3600
                
                # If next event is on same day, add to totals
                if next_event['day'] == day:
                    if event['status'] == 'off_duty':
                        daily_logs[day]['totals']['offDuty'] += duration
                    elif event['status'] == 'sleeper_berth':
                        daily_logs[day]['totals']['sleeperBerth'] += duration
                    elif event['status'] == 'driving':
                        daily_logs[day]['totals']['driving'] += duration
                        # Estimate miles for this driving segment
                        miles = duration * self.AVG_SPEED_MPH
                        daily_logs[day]['totalMiles'] += int(miles)
                    elif event['status'] == 'on_duty':
                        daily_logs[day]['totals']['onDuty'] += duration
                else:
                    # Event spans midnight - split the time between days
                    day_end = datetime.combine(event['time'].date(), datetime.max.time())
                    duration_today = (day_end - event['time']).total_seconds() / 3600
                    duration_tomorrow = duration - duration_today
                    
                    # Add to current day
                    if event['status'] == 'off_duty':
                        daily_logs[day]['totals']['offDuty'] += duration_today
                    elif event['status'] == 'sleeper_berth':
                        daily_logs[day]['totals']['sleeperBerth'] += duration_today
                    elif event['status'] == 'driving':
                        daily_logs[day]['totals']['driving'] += duration_today
                        miles = duration_today * self.AVG_SPEED_MPH
                        daily_logs[day]['totalMiles'] += int(miles)
                    elif event['status'] == 'on_duty':
                        daily_logs[day]['totals']['onDuty'] += duration_today
                    
                    # Create next day's log if doesn't exist
                    next_day = next_event['day']
                    if next_day not in daily_logs:
                        next_date = next_event['time'].date()
                        daily_logs[next_day] = {
                            'date': next_date.strftime('%m/%d/%Y'),
                            'day': next_day,
                            'driverName': 'John Doe',
                            'carrierName': 'ELD Pro Transport',
                            'vehicleNumber': 'TRK-101',
                            'totalMiles': 0,
                            'dutyStatusChanges': [],
                            'remarks': [],
                            'totals': {
                                'offDuty': 0,
                                'sleeperBerth': 0,
                                'driving': 0,
                                'onDuty': 0
                            }
                        }
                    
                    # Add midnight continuation
                    daily_logs[next_day]['dutyStatusChanges'].insert(0, {
                        'time': '00:00',
                        'status': event['status'],
                        'location': f"{event['description']} (continued)"
                    })
                    
                    # Add to next day totals
                    if event['status'] == 'off_duty':
                        daily_logs[next_day]['totals']['offDuty'] += duration_tomorrow
                    elif event['status'] == 'sleeper_berth':
                        daily_logs[next_day]['totals']['sleeperBerth'] += duration_tomorrow
                    elif event['status'] == 'driving':
                        daily_logs[next_day]['totals']['driving'] += duration_tomorrow
                        miles = duration_tomorrow * self.AVG_SPEED_MPH
                        daily_logs[next_day]['totalMiles'] += int(miles)
                    elif event['status'] == 'on_duty':
                        daily_logs[next_day]['totals']['onDuty'] += duration_tomorrow
        
        # Round totals
        for day in daily_logs:
            for key in daily_logs[day]['totals']:
                daily_logs[day]['totals'][key] = round(daily_logs[day]['totals'][key], 1)
        
        return list(daily_logs.values())