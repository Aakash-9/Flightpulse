package com.flightpulse.util;

/**
 * Column layout of the Silver layer as written by NormalizedFlight
 * (com.flightpulse.normalize). Kept here, not in the normalize package, so
 * downstream analytical jobs (airport/route/temporal/rotation/carryover)
 * can depend on util without depending on normalize.
 *
 * Must be kept in sync with NormalizedFlight.SILVER_HEADER.
 */
public final class SilverSchema {

    public static final String DELIMITER = "\\|";

    public static final int FL_DATE = 0;
    public static final int OP_UNIQUE_CARRIER = 1;
    public static final int TAIL_NUM = 2;
    public static final int OP_CARRIER_FL_NUM = 3;
    public static final int ORIGIN = 4;
    public static final int DEST = 5;
    public static final int CRS_DEP_DAY_OFFSET = 6;
    public static final int CRS_DEP_MIN = 7;
    public static final int DEP_MIN = 8;
    public static final int DEP_DELAY_MIN = 9;
    public static final int TAXI_OUT_MIN = 10;
    public static final int WHEELS_OFF_MIN = 11;
    public static final int WHEELS_ON_MIN = 12;
    public static final int TAXI_IN_MIN = 13;
    public static final int CRS_ARR_DAY_OFFSET = 14;
    public static final int CRS_ARR_MIN = 15;
    public static final int ARR_MIN = 16;
    public static final int ARR_DELAY_MIN = 17;
    public static final int CANCELLED = 18;
    public static final int CANCELLATION_CODE = 19;
    public static final int DIVERTED = 20;
    public static final int AIR_TIME_MIN = 21;
    public static final int DISTANCE_MI = 22;
    public static final int CARRIER_DELAY_MIN = 23;
    public static final int WEATHER_DELAY_MIN = 24;
    public static final int NAS_DELAY_MIN = 25;
    public static final int SECURITY_DELAY_MIN = 26;
    public static final int LATE_AIRCRAFT_DELAY_MIN = 27;
    public static final int RECORD_STATUS = 28;

    public static final int COLUMN_COUNT = 29;

    /** FAA's standard "delayed" threshold, used for delay-rate counters. */
    public static final double DELAY_THRESHOLD_MIN = 15.0;

    private SilverSchema() {
    }

    public static double parseDoubleOrZero(String s) {
        if (s == null || s.isEmpty()) {
            return 0.0;
        }
        try {
            return Double.parseDouble(s);
        } catch (NumberFormatException e) {
            return 0.0;
        }
    }

    public static boolean isPresent(String s) {
        return s != null && !s.isEmpty();
    }
}
