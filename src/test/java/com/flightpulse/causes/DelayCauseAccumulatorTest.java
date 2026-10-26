package com.flightpulse.causes;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class DelayCauseAccumulatorTest {

    private static Double[] causes(Double c, Double w, Double n, Double s, Double l) {
        return new Double[]{c, w, n, s, l};
    }

    private static final Double[] NONE = causes(null, null, null, null, null);

    @Test
    void reportedCausesThatAddUpAreCountedWithoutMismatch() {
        DelayCauseAccumulator a = new DelayCauseAccumulator();
        a.addFlight(true, false, false, "", 20.0, 35.0, causes(10.0, 0.0, 5.0, 0.0, 20.0));
        assertEquals(1, a.nDelayed15);
        assertEquals(1, a.nCauseReported);
        assertEquals(0, a.nMismatch);
        assertEquals(0, a.nUnreported);
        assertEquals(35.0, a.totalCauseMinutes(), 1e-9);
        assertEquals(1, a.causeFlights[0]);   // carrier > 0
        assertEquals(0, a.causeFlights[1]);   // weather == 0 does not count as a flight with that cause
        assertEquals(1, a.causeFlights[4]);
    }

    @Test
    void flightUnder15MinutesIsOperatedButNotDelayedAndNotUnreported() {
        DelayCauseAccumulator a = new DelayCauseAccumulator();
        a.addFlight(true, false, false, "", 5.0, 10.0, NONE);
        assertEquals(1, a.nOperated);
        assertEquals(0, a.nDelayed15);
        assertEquals(0, a.nUnreported);
    }

    @Test
    void delayedFlightWithAllCausesBlankIsUnreportedNotZero() {
        DelayCauseAccumulator a = new DelayCauseAccumulator();
        a.addFlight(true, false, false, "", 30.0, 40.0, NONE);
        assertEquals(1, a.nDelayed15);
        assertEquals(1, a.nUnreported);
        assertEquals(0, a.nCauseReported);
        assertEquals(0.0, a.totalCauseMinutes(), 1e-9);
    }

    @Test
    void causesThatDoNotSumToArrivalDelayAreFlaggedAsMismatch() {
        DelayCauseAccumulator a = new DelayCauseAccumulator();
        a.addFlight(true, false, false, "", 30.0, 40.0, causes(10.0, 0.0, 10.0, 0.0, 0.0));
        assertEquals(1, a.nCauseReported);
        assertEquals(1, a.nMismatch);
    }

    @Test
    void withinOneMinuteToleranceIsNotAMismatch() {
        DelayCauseAccumulator a = new DelayCauseAccumulator();
        a.addFlight(true, false, false, "", 30.0, 40.0, causes(40.0, 0.0, 0.0, 0.0, 0.0));
        a.addFlight(true, false, false, "", 30.0, 40.0, causes(39.5, 0.0, 0.0, 0.0, 0.0));
        assertEquals(0, a.nMismatch);
    }

    @Test
    void cancelledFlightCountsByCodeAndStaysOutOfDelayStats() {
        DelayCauseAccumulator a = new DelayCauseAccumulator();
        a.addFlight(false, true, false, "B", null, null, NONE);
        a.addFlight(false, true, false, "A", null, null, NONE);
        a.addFlight(false, false, true, "", null, null, NONE);
        assertEquals(3, a.nTotal);
        assertEquals(2, a.nCancelled);
        assertEquals(1, a.nDiverted);
        assertEquals(1, a.cancelByCode[0]);
        assertEquals(1, a.cancelByCode[1]);
        assertEquals(0, a.nOperated);
    }

    @Test
    void mergeIsAdditive() {
        DelayCauseAccumulator a = new DelayCauseAccumulator();
        DelayCauseAccumulator b = new DelayCauseAccumulator();
        a.addFlight(true, false, false, "", 20.0, 35.0, causes(10.0, 0.0, 5.0, 0.0, 20.0));
        b.addFlight(true, false, false, "", 0.0, 20.0, causes(0.0, 20.0, 0.0, 0.0, 0.0));
        DelayCauseAccumulator m = new DelayCauseAccumulator();
        m.add(a);
        m.add(b);
        assertEquals(2, m.nDelayed15);
        assertEquals(55.0, m.totalCauseMinutes(), 1e-9);
        assertEquals(20.0, m.causeMinutes[1], 1e-9);
    }
}
