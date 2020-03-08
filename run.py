import os
import logging
import argparse
import xml.etree.ElementTree as ET
import urllib.request
from google.transit import gtfs_realtime_pb2
from gtfsSQL import gtfs2sql
import time
import pendulum
from config import XML_DEPARTURES_URL, XML_VEHICLES_URL, OUTPUT_FILE, DELAY, GTFS_URL, GTFS_PATH, TZ
from getGTFS import getNewGTFS
from atomicwrites import atomic_write
from concurrent import futures 

# === Get logging level if set ===#
parser = argparse.ArgumentParser(description="Starts the realtime protobuffer generator")
parser.add_argument("--log", help="set the logging level")

args = parser.parse_args()

if args.log:
    LOG_LEVEL = getattr(logging, args.log.upper(), None)
    if not isinstance(LOG_LEVEL, int):
        raise ValueError('Invalid log level: %s' % args.log)
else:
    LOG_LEVEL = getattr(logging, 'INFO', None)

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p'
)

logging.info("Starting Protobuf Writer")


def requestStopXML(xml_url):
    ''' Grab the XML, parse it into an Element Tree and return the root'''
    with urllib.request.urlopen(xml_url) as response:
        xml = response.read()
        logging.debug(f"Downloaded xml: {xml_url}")
        return ET.fromstring(xml)

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

    for vehicle in filter(inservice, locationElTree.iter('vehicle')):
        routeid = vehicle.find('routeid').text
        # route 99 is a Deadhead route. It appears to be used for vehicles
        # moving to the garage or otherwise not in service
        if routeid == '99':
            continue
        name = vehicle.find('name').text
        tripid = vehicle.find('tripid').text
        laststop = vehicle.find('laststop').text
        direction = vehicle.find('direction').text
        speed = float(vehicle.find('speed').text)
        position = {
            'latitude': float(vehicle.find('latitude').text),
            'longitude': float(vehicle.find('longitude').text),
            'bearing': float(vehicle.find('heading').text),
            'speed': speed * 0.44704 # mph to meters/second
        }
          
        tripGuess = gtfs2sql.getTripFromLocationData(tripid, routeid, direction, today)
        if (tripGuess is None):
            logging.debug(f"Couldn't determine trip id from {tripid}, {routeid}, {direction}, {today}")
            continue 
        tripId = tripGuess['trip_id']
        
        vehicles[name] = {
            "position": position,
            "trip": {"trip_id":tripId}
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
        entity.vehicle.trip.trip_id = info['trip']['trip_id']
        entity.vehicle.vehicle.id = vehicle_id
        entity.vehicle.position.latitude = info['position']['latitude']
        entity.vehicle.position.longitude = info['position']['longitude']
        entity.vehicle.position.bearing = info['position']['bearing']
        entity.vehicle.position.speed = info['position']['speed']
        feed.entity.append(entity)
    return feed


def run():
    with futures.ThreadPoolExecutor(2) as executor:
      res = executor.map(requestStopXML, [XML_DEPARTURES_URL, XML_VEHICLES_URL])

    try:
        realtime_data, position_data =  list(res)
    except (urllib.error.URLError, ConnectionError) as request_error:
        logging.error(request_error)
        return
    except ET.ParseError as xml_error:
        logging.error(xml_error)
        return

    trips = makeTripDelaysFromXML(realtime_data)
    locations = makeLocationsFromVehicleXML(position_data)

    pb = makeProtoBuffer(trips, locations)

    try:
        with atomic_write(OUTPUT_FILE, overwrite=True, mode='wb') as pb_file:
            pb_file.write(pb.SerializeToString())
    except OSError as os_error:
        logging.error(os_error)
        return
    os.chmod(OUTPUT_FILE, 644)

    logging.debug("Wrote Realtime Protobuffer file")


if __name__ == "__main__":
    #getNewGTFS(GTFS_URL, GTFS_PATH)
    gtfs2sql.initializeGTFS()

    while True:
        run()
        time.sleep(DELAY)
