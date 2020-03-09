import os
import logging
import time
import argparse
import urllib.request
import xml.etree.ElementTree as ET
from xml2pb.gtfsSQL import gtfs2sql
from xml2pb import getNewGTFS, makeLocationsFromVehicleXML, makeTripDelaysFromXML, makeProtoBuffer
from config import XML_DEPARTURES_URL, XML_VEHICLES_URL, OUTPUT_FILE, DELAY, GTFS_URL, GTFS_PATH
from atomicwrites import atomic_write
from concurrent import futures

# === Get logging level if set and setup logging ===#
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
    ''' Request the XML, parse it into an Element Tree and return the root'''
    with urllib.request.urlopen(xml_url) as response:
        xml = response.read()
        logging.debug(f"Downloaded xml: {xml_url}")
        return ET.fromstring(xml)


def run():
    # Get and parse XML files in two threads
    with futures.ThreadPoolExecutor(2) as executor:
        res = executor.map(requestStopXML, [XML_DEPARTURES_URL, XML_VEHICLES_URL])

    try:
        realtime_data, position_data = list(res)
    except (urllib.error.URLError, ConnectionError) as request_error:
        logging.error(request_error)
        return
    except ET.ParseError as xml_error:
        logging.error(xml_error)
        return

    # Make data structures from xml
    trips = makeTripDelaysFromXML(realtime_data)
    locations = makeLocationsFromVehicleXML(position_data)

    # Create Protobuffer
    pb = makeProtoBuffer(trips, locations)

    # Write protobuffer to file
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
    gtfs2sql.initializeGTFS(GTFS_PATH)

    while True:
        run()
        time.sleep(DELAY)
