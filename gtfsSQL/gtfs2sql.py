import sqlite3
import csv
from config import GTFS_PATH
import os
import logging

logger = logging.getLogger("__name__")

SCHEMA_DEFINITIONS = os.path.join(os.path.dirname(__file__), 'db/schema.sql')
DB_FILE = os.path.join(os.path.dirname(__file__), 'db/gtfs_db')

GTFS_TABLES = [
    'stop_times',
    'trips',
    'agency',
    'calendar_dates',
    'calendar',
    'fare_attributes',
    'feed_info',
    'routes',
    'shapes',
    'stops',
]


def createTables():
    '''Read schema and creates tables and indexes. This drops exising tables/indexes'''
    con = sqlite3.connect(DB_FILE)
    with open(SCHEMA_DEFINITIONS) as f:
        sql = f.read()
        con.executescript(sql)
    con.close()


def importGTFS():
    '''Imports the gtfs files into the DB'''
    with sqlite3.connect(DB_FILE) as con:
        for table in GTFS_TABLES:
            logger.debug(f"importing {table}")
            importFile(f'{GTFS_PATH}/{table}.txt', table, con)
        con.commit()


def importFile(path, table, con):
    '''Reads a single GTFS file at `path` and inserts it into `table`'''
    with open(path) as f:
        dr = csv.DictReader(f, skipinitialspace=True)
        placeholders = ','.join(':' + f.strip() for f in dr.fieldnames)
        con.executemany(f'INSERT into {table} VALUES ({placeholders})', dr)


def initializeGTFS():
    createTables()
    importGTFS()


# These strings are in the headsign field of trips
# Trips also has a direction_id which in the spec is either 0 or 1
# The XML provides 'I', 'O', 'L': 'I' and 'O' generally correspond to 1 and 0, but 'L'
# can be either.

directionLookup = {
    'I': "Inbound",
    'O': "Outbound",
    'L': "Loop"
}


def getTripFromXMLData(bt_id, route_id, sdt, direction, day):
    '''Finds the (hopefully) uniques trip given the information we have in the XML'''

    with sqlite3.connect(DB_FILE) as con:
        con.row_factory = sqlite3.Row
        c = con.cursor()
        c.execute(f'''
            SELECT trips.trip_id, stop_times.stop_sequence
            FROM trips
            JOIN stop_times ON stop_times.trip_id = trips.trip_id
            JOIN stops ON stops.stop_id=stop_times.stop_id
            JOIN routes ON routes.route_id = trips.route_id
            JOIN calendar ON calendar.service_id = trips.service_id
            WHERE routes.route_short_name=?
            AND trips.trip_headsign=?
            AND stop_times.departure_time = ?
            AND stops.stop_bt_id = ?
            AND calendar.{day}
        ''', (route_id, directionLookup[direction], sdt, bt_id))
        res = c.fetchone()
        if res:
            d = dict(res)
        else:
            d = None

    return d


if __name__ == "__main__":
    initializeGTFS()
