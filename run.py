import os
import logging
import argparse
import xml.etree.ElementTree as ET
import urllib.request
from google.transit import gtfs_realtime_pb2
from gtfsSQL import gtfs2sql
import time
import pendulum
from config import XML_URL, OUTPUT_FILE, DELAY, GTFS_URL, GTFS_PATH, TZ
from getGTFS import getNewGTFS
from atomicwrites import atomic_write

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
        return ET.fromstring(xml)


def makeTripDelaysFromXML(realTimeElTree):
    '''
    Converts the XML tree from stopdepartures into an object keyed by trip_id
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

            # getTripFromXMLData makes a guess about the trip id and stop
            # sequence based the information in the XML

            today = pendulum.today(TZ).format('dddd').lower()

            t = gtfs2sql.getTripFromXMLData(
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


def makeProtoBuffer(trips):
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

    # Create an entity for each trip
    for trip_id, trip in trips.items():
        entity = gtfs_realtime_pb2.FeedEntity()
        entity.id = trip_id

        entity.trip_update.trip.trip_id = trip_id

        stop_time_update = entity.trip_update.StopTimeUpdate()
        stop_time_update.stop_sequence = trip['stop_sequence']
        stop_time_update.arrival.delay = trip['dev']

        entity.trip_update.stop_time_update.append(stop_time_update)
        feed.entity.append(entity)

    return feed


def run():
    try:
        realtime_data = requestStopXML(XML_URL)
    except (urllib.error.URLError, ConnectionError) as request_error:
        logging.error(request_error)
        return
    except ET.ParseError as xml_error:
        logging.error(xml_error)
        return

    trips = makeTripDelaysFromXML(realtime_data)
    pb = makeProtoBuffer(trips)

    try:
        with atomic_write(OUTPUT_FILE, overwrite=True, mode='wb') as pb_file:
            pb_file.write(pb.SerializeToString())
    except OSError as os_error:
        logging.error(os_error)
        return
    os.chmod(OUTPUT_FILE, 644)

    logging.debug("Wrote Realtime Protobuffer file")


if __name__ == "__main__":
    getNewGTFS(GTFS_URL, GTFS_PATH)
    gtfs2sql.initializeGTFS()

    while True:
        run()
        time.sleep(DELAY)
