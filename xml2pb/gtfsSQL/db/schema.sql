PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS agency;
CREATE TABLE agency (
	agency_id TEXT NULL,
	agency_name TEXT NOT NULL,
	agency_url TEXT NOT NULL,
	agency_timezone TEXT NOT NULL,
	agency_lang TEXT NULL,
	agency_phone TEXT NULL
);

DROP TABLE IF EXISTS stops;
CREATE TABLE stops (
	stop_id TEXT NOT NULL PRIMARY KEY,
	stop_code TEXT NULL,
	stop_name TEXT NOT NULL,
   stop_desc TEXT NULL,
	stop_lat DOUBLE NOT NULL,
	stop_lon DOUBLE NOT NULL,
   stop_bt_id TEXT NULL,
	stop_url TEXT NULL,
   location_type TEXT NULL,
   parent_station TEXT NULL
);

CREATE INDEX stops_stop_id on stops(stop_id);

DROP TABLE IF EXISTS routes;
CREATE TABLE routes (
	route_id TEXT NOT NULL PRIMARY KEY,
	agency_id TEXT NULL,
	route_short_name TEXT NULL,
	route_long_name TEXT NULL,
	route_type INTEGER NOT NULL,
	route_url TEXT NULL,
	route_color CHAR(6) NULL,
	route_text_color CHAR(6) NULL
);

DROP TABLE IF EXISTS calendar;
CREATE TABLE calendar (
	service_id TEXT NOT NULL PRIMARY KEY,
	monday BOOLEAN NOT NULL,
	tuesday BOOLEAN NOT NULL,
	wednesday BOOLEAN NOT NULL,
	thursday BOOLEAN NOT NULL,
	friday BOOLEAN NOT NULL,
	saturday BOOLEAN NOT NULL,
	sunday BOOLEAN NOT NULL,
	start_date DATE NOT NULL,
	end_date DATE NOT NULL
);

DROP TABLE IF EXISTS calendar_dates;
CREATE TABLE calendar_dates (
	service_id TEXT NOT NULL,
	`date` DATE NOT NULL,
	exception_type INTEGER NOT NULL,
	
	FOREIGN KEY(service_id) REFERENCES calendar(service_id) ON DELETE CASCADE
);

DROP TABLE IF EXISTS shapes;
CREATE TABLE shapes (
	shape_id TEXT NOT NULL,
	shape_pt_lat DOUBLE NOT NULL,
	shape_pt_lon DOUBLE NOT NULL,
	shape_pt_sequence INTEGER NOT NULL,
	
	PRIMARY KEY(shape_id, shape_pt_sequence)
);

DROP TABLE IF EXISTS trips;
CREATE TABLE trips (
	route_id TEXT NOT NULL,
	service_id TEXT NOT NULL,
	trip_id TEXT NOT NULL PRIMARY KEY,
	trip_headsign TEXT NULL,
	direction_id INTEGER NULL,
	shape_id TEXT NULL,
	wheelchair_accessible INTEGER NULL,
	bikes_allowed INTEGER NULL,

	FOREIGN KEY(route_id) REFERENCES routes(route_id) ON DELETE CASCADE,
	FOREIGN KEY(service_id) REFERENCES calendar(service_id) ON DELETE CASCADE
);

DROP TABLE IF EXISTS stop_times;
CREATE TABLE stop_times (
	trip_id TEXT NOT NULL,
	arrival_time INT NOT NULL,
	departure_time INT NOT NULL,
	stop_id TEXT NOT NULL,
	stop_sequence INTEGER NOT NULL,
	stop_headsign TEXT NULL,
	pickup_type INTEGER NULL,
	drop_off_type INTEGER NULL,
	
	PRIMARY KEY(trip_id, stop_sequence),
	
	FOREIGN KEY(trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
	FOREIGN KEY(stop_id) REFERENCES stops(stop_id) ON DELETE CASCADE
);

CREATE INDEX trips_trip_id on stop_times(trip_id);
CREATE INDEX stop_time on stop_times(departure_time);
CREATE INDEX trip_id ON stop_times(trip_id);
CREATE INDEX stop_id ON stop_times(stop_id);

DROP TABLE IF EXISTS fare_attributes;
CREATE TABLE fare_attributes (
	fare_id TEXT NOT NULL PRIMARY KEY,
	price DECIMAL(3, 2) NOT NULL,
	currency_type TEXT NOT NULL,
	payment_method INTEGER NOT NULL,
	transfers INTEGER NULL
);

DROP TABLE IF EXISTS feed_info;
CREATE TABLE feed_info (
	feed_publisher_name TEXT NOT NULL,
	feed_publisher_url TEXT NOT NULL,
	feed_lang TEXT NOT NULL,
	feed_version TEXT NULL
);
