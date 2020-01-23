# The URL hosting the muni stopdepartures XML file
XML_URL = "http://bustracker.muni.org/InfoPoint/XML/stopdepartures.xml"

# The url where the GTFS zip file is available:
GTFS_URL = "http://gtfs.muni.org/People_Mover_2019.12.17.gtfs.zip"

# Where to save the protobuffer file
OUTPUT_FILE = "people_mover.pb"

# The delay between requests for the XML file
DELAY = 20  # seconds

# Path to the directory hosting the uncompressed GTFS files
GTFS_PATH = "downloads/People_Mover.gtfs"
