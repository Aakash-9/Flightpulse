package com.flightpulse.normalize;

import com.flightpulse.util.FlightSchema;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class NormalizedFlightTest {

    /** Builds a syntactically complete row (FlightSchema.COLUMN_COUNT fields), then overrides a few. */
    private static String[] baseRow() {
        String[] f = new String[FlightSchema.COLUMN_COUNT];
        f[FlightSchema.FL_DATE] = "1/1/2020 12:00:00 AM";
        f[FlightSchema.OP_UNIQUE_CARRIER] = "9E";
        f[FlightSchema.TAIL_NUM] = "N131EV";
        f[FlightSchema.OP_CARRIER_FL_NUM] = "4867";
        f[FlightSchema.ORIGIN] = "DSM";
        f[FlightSchema.ORIGIN_CITY_NAME] = "Des Moines, IA";
        f[FlightSchema.DEST] = "MSP";
        f[FlightSchema.DEST_CITY_NAME] = "Minneapolis, MN";
        f[FlightSchema.DEP_TIME] = "1347";
        f[FlightSchema.DEP_DELAY] = "32.00";
        f[FlightSchema.TAXI_OUT] = "12.00";
        f[FlightSchema.WHEELS_OFF] = "1359";
        f[FlightSchema.WHEELS_ON] = "1441";
        f[FlightSchema.TAXI_IN] = "4.00";
        f[FlightSchema.ARR_TIME] = "1445";
        f[FlightSchema.ARR_DELAY] = "6.00";
        f[FlightSchema.CANCELLED] = "0.00";
        f[FlightSchema.CANCELLATION_CODE] = "";
        f[FlightSchema.DIVERTED] = "0.00";
        f[FlightSchema.AIR_TIME] = "42.00";
        f[FlightSchema.DISTANCE] = "232.00";
        f[FlightSchema.CARRIER_DELAY] = "";
        f[FlightSchema.WEATHER_DELAY] = "";
        f[FlightSchema.NAS_DELAY] = "";
        f[FlightSchema.SECURITY_DELAY] = "";
        f[FlightSchema.LATE_AIRCRAFT_DELAY] = "";
        return f;
    }

    @Test
    void classifiesOrdinaryFlightAsValid() {
        NormalizedFlight nf = NormalizedFlight.classify(baseRow());
        assertEquals(RecordStatus.VALID, nf.status);
        assertTrue(nf.toSilverLine().startsWith("2020-01-01|9E|N131EV|4867|DSM|MSP|"));
        assertTrue(nf.toSilverLine().endsWith("VALID"));
    }

    @Test
    void classifiesCancelledFlight() {
        String[] f = baseRow();
        f[FlightSchema.CANCELLED] = "1.00";
        f[FlightSchema.CANCELLATION_CODE] = "B";
        f[FlightSchema.DEP_TIME] = "";
        f[FlightSchema.ARR_TIME] = "";
        f[FlightSchema.DEP_DELAY] = "";
        f[FlightSchema.ARR_DELAY] = "";
        NormalizedFlight nf = NormalizedFlight.classify(f);
        assertEquals(RecordStatus.CANCELLED, nf.status);
        assertTrue(nf.toSilverLine().contains("|1|B|0|"));
    }

    @Test
    void classifiesDivertedFlight() {
        String[] f = baseRow();
        f[FlightSchema.DIVERTED] = "1.00";
        NormalizedFlight nf = NormalizedFlight.classify(f);
        assertEquals(RecordStatus.DIVERTED, nf.status);
    }

    @Test
    void classifiesMissingTailAsMissingTailNotInvalid() {
        String[] f = baseRow();
        f[FlightSchema.TAIL_NUM] = "";
        NormalizedFlight nf = NormalizedFlight.classify(f);
        assertEquals(RecordStatus.MISSING_TAIL, nf.status);
    }

    @Test
    void unparseableDateIsInvalid() {
        String[] f = baseRow();
        f[FlightSchema.FL_DATE] = "not-a-date";
        NormalizedFlight nf = NormalizedFlight.classify(f);
        assertEquals(RecordStatus.INVALID, nf.status);
        assertTrue(nf.toSilverLine().contains("REASON=unparseable FL_DATE"));
    }

    @Test
    void derivesScheduledDepartureFromActualMinusDelay() {
        // DEP_TIME=1347 (827 min), DEP_DELAY=32 -> CRS_DEP should be 795 min (13:15), day offset 0
        NormalizedFlight nf = NormalizedFlight.classify(baseRow());
        String[] parts = nf.toSilverLine().split("\\|", -1);
        assertEquals("0", parts[6]);   // CRS_DEP_DAY_OFFSET
        assertEquals("795", parts[7]); // CRS_DEP_MIN
    }
}
