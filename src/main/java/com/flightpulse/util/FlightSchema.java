package com.flightpulse.util;

/**
 * Column layout of the BTS Reporting Carrier On-Time Performance CSVs as
 * actually shipped in this dataset (verified against 2020-2025 headers,
 * identical across all 66 monthly files). Not the full official BTS field
 * list - this package omits CRS_DEP_TIME / CRS_ARR_TIME / CRS_ELAPSED_TIME.
 */
public final class FlightSchema {

    public static final String[] COLUMNS = {
        "FL_DATE", "OP_UNIQUE_CARRIER", "TAIL_NUM", "OP_CARRIER_FL_NUM",
        "ORIGIN", "ORIGIN_CITY_NAME", "DEST", "DEST_CITY_NAME",
        "DEP_TIME", "DEP_DELAY", "TAXI_OUT", "WHEELS_OFF", "WHEELS_ON",
        "TAXI_IN", "ARR_TIME", "ARR_DELAY",
        "CANCELLED", "CANCELLATION_CODE", "DIVERTED",
        "AIR_TIME", "DISTANCE",
        "CARRIER_DELAY", "WEATHER_DELAY", "NAS_DELAY", "SECURITY_DELAY", "LATE_AIRCRAFT_DELAY"
    };

    public static final int COLUMN_COUNT = COLUMNS.length;

    public static final String HEADER_LINE = String.join(",", COLUMNS);

    public static final int FL_DATE = 0;
    public static final int OP_UNIQUE_CARRIER = 1;
    public static final int TAIL_NUM = 2;
    public static final int OP_CARRIER_FL_NUM = 3;
    public static final int ORIGIN = 4;
    public static final int ORIGIN_CITY_NAME = 5;
    public static final int DEST = 6;
    public static final int DEST_CITY_NAME = 7;
    public static final int DEP_TIME = 8;
    public static final int DEP_DELAY = 9;
    public static final int TAXI_OUT = 10;
    public static final int WHEELS_OFF = 11;
    public static final int WHEELS_ON = 12;
    public static final int TAXI_IN = 13;
    public static final int ARR_TIME = 14;
    public static final int ARR_DELAY = 15;
    public static final int CANCELLED = 16;
    public static final int CANCELLATION_CODE = 17;
    public static final int DIVERTED = 18;
    public static final int AIR_TIME = 19;
    public static final int DISTANCE = 20;
    public static final int CARRIER_DELAY = 21;
    public static final int WEATHER_DELAY = 22;
    public static final int NAS_DELAY = 23;
    public static final int SECURITY_DELAY = 24;
    public static final int LATE_AIRCRAFT_DELAY = 25;

    private FlightSchema() {
    }
}
