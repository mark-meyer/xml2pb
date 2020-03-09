''' GTFS File syncing
This script will download the GTFS file from the GTFS_PATH url in the config.
Once downloaded it will unpack the GTFS into config.GTFS_PATH and then read the
GTFS files into SQLite.

This file can also be imported as a module and contains the function:

getNewGTFS(gtfs_url, destination) — performs the download (without importing into
SQLlite and unzips the GTFS into destination)
'''

from io import BytesIO
import urllib.request
import zipfile
import logging
from xml2pb.gtfsSQL import gtfs2sql
from config import GTFS_URL, GTFS_PATH


def getNewGTFS(gtfs_url, destination):
    ''' Download GTFS from gtfs_url and unpack into destination'''

    logging.debug("Downloading GTFS")

    try:
        with urllib.request.urlopen(gtfs_url) as response:
            zipData = response.read()
    except urllib.error.URLError as request_error:
        logging.error(request_error)
        return
    try:
        zipFile = zipfile.ZipFile(BytesIO(zipData))
        zipFile.extractall(path=destination)
    except zipfile.error as zip_err:
        logging.error(zip_err)
        return


if __name__ == "__main__":
    getNewGTFS(GTFS_URL, GTFS_PATH)
    gtfs2sql.initializeGTFS()
