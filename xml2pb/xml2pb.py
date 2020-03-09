import pendulum
import time
import logging
from google.transit import gtfs_realtime_pb2
from config import TZ
from .gtfsSQL import gtfs2sql


def inservice(vehicle):
    ''' Returns true if the vehicle is considered in servive '''
    return vehicle.attrib['op-status'] not in ['none', 'out-of-service']


def makeLocationsFromVehicleXML(locationElTree):
    '''
    Converts the vehicle locations xml tree from vehiclelocation to a dictionary
    keyed by vehicle id (the name tag in the xml). This looks up the trip id based
    on the XML's tripid, which is based on the time of the first departure of a particular
    route. For example tripid 1150 corresponds to the trip whose first departure
    is at 11:50:00. Combined with route, direction, and day, this is enough to
    unambiguously determine the trip
    '''

    today = pendulum.today(TZ).format('dddd').lower()

    vehicles = {}
    # time is formated like: 2020-03-09 11:18
    xmlTimeStamp = locationElTree.find('report-generated').text
    timeStamp = pendulum.parse(xmlTimeStamp, tz=TZ).int_timestamp

    for vehicle in filter(inservice, locationElTree.iter('vehicle')):
        routeid = vehicle.find('routeid').text
        # route 99 is a Deadhead route. It appears to be used for vehicles
        # moving to the garage or otherwise not in service
        if routeid == '99':
            continue
        name = vehicle.find('name').text
        tripid = vehicle.find('tripid').text
        # laststop = vehicle.find('laststop').text
        direction = vehicle.find('direction').text
        speed = float(vehicle.find('speed').text)
        position = {
            'latitude': float(vehicle.find('latitude').text),
            'longitude': float(vehicle.find('longitude').text),
            'bearing': float(vehicle.find('heading').text),
            'speed': speed * 0.44704  # mph to meters/second
        }

        tripGuess = gtfs2sql.getTripFromLocationData(tripid, routeid, direction, today)
        if (tripGuess is None):
            logging.debug(f"Couldn't determine trip id from {tripid}, {routeid}, {direction}, {today}")
            continue
        tripId = tripGuess['trip_id']

        vehicles[name] = {
            "timestamp": timeStamp,
            "position": position,
            "trip": {"trip_id": tripId}
        }

    return vehicles


def makeTripDelaysFromXML(realTimeElTree):
    '''
    Converts the XML tree from stopdepartures into an dictionary keyed by trip_id
    The object will only have a single event per id, and will choose the one
    with the lowest stop sequence, which should be the earliest reported stop
    on the trip.
    '''
    trip_delays = {}

    for stop in realTimeElTree.iter('stop'):
        stop_id = stop.find('id').text

        for dep in stop.findall('departure'):
            sdt = dep.find('sdt').text
            dev = dep.find('dev').text
            direction = dep.find('dir').text
            route = dep.find('route')
            route_id = route.find('id').text

            if (sdt == "Done" or dev == '0'):
                continue

            # getTripFromDepartureData makes a guess about the trip id and stop
            # sequence based the information in the XML

            today = pendulum.today(TZ).format('dddd').lower()

            t = gtfs2sql.getTripFromDepartureData(
                stop_id,
                route_id,
                sdt + ":00",
                direction,
                today
            )

            if t is None:
                continue

            trip_id = t['trip_id']
            stop_sequence = t['stop_sequence']

            if trip_id not in trip_delays or trip_delays[trip_id]['stop_sequence'] > stop_sequence:
                trip_delays[trip_id] = {
                    'dev': int(dev),
                    'stop_sequence': stop_sequence,
                }

    return trip_delays


def makeProtoBuffer(trips, locations):
    '''
    Create a protobuffer object from the trips object.
    Trips is expected to be a dictionary keyed to trip_id strings.
    The values are dictionaries with `stop_sequence` and `dev` items.
    '''
    feed = gtfs_realtime_pb2.FeedMessage()

    # Set Header
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.incrementality = 0
    feed.header.timestamp = int(time.time())

    # Create an trip update entity for each trip
    for trip_id, trip in trips.items():
        entity = gtfs_realtime_pb2.FeedEntity()
        entity.id = trip_id

        entity.trip_update.trip.trip_id = trip_id

        stop_time_update = entity.trip_update.StopTimeUpdate()
        stop_time_update.stop_sequence = trip['stop_sequence']
        stop_time_update.arrival.delay = trip['dev']

        entity.trip_update.stop_time_update.append(stop_time_update)
        feed.entity.append(entity)
    # Create vehicle location for each vehicle location
    for vehicle_id, info in locations.items():
        entity = gtfs_realtime_pb2.FeedEntity()
        entity.id = vehicle_id
        entity.vehicle.timestamp = info['timestamp']
        entity.vehicle.trip.trip_id = info['trip']['trip_id']
        entity.vehicle.vehicle.id = vehicle_id
        entity.vehicle.position.latitude = info['position']['latitude']
        entity.vehicle.position.longitude = info['position']['longitude']
        entity.vehicle.position.bearing = info['position']['bearing']
        entity.vehicle.position.speed = info['position']['speed']
        feed.entity.append(entity)
    return feed
