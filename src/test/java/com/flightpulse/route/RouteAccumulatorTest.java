package com.flightpulse.route;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class RouteAccumulatorTest {

    @Test
    void aggregatesDepAndArrDelayIndependently() {
        RouteAccumulator a = RouteAccumulator.forRecord(true, 5.0, 20.0, false, false);
        RouteAccumulator b = RouteAccumulator.forRecord(true, 25.0, 10.0, false, false);
        RouteAccumulator merged = new RouteAccumulator();
        merged.add(a);
        merged.add(b);

        assertEquals(2, merged.totalFlights);
        assertEquals(15.0, merged.meanDepDelay(), 1e-9); // (5+25)/2
        assertEquals(15.0, merged.meanArrDelay(), 1e-9); // (20+10)/2
        assertEquals(0.5, merged.depDelayRate(), 1e-9);  // only the 25 crosses 15
        assertEquals(0.5, merged.arrDelayRate(), 1e-9);  // only the 20 crosses 15
    }

    @Test
    void cancelledAndDivertedExcludedFromDelaySampleButCountedInTotals() {
        RouteAccumulator ok = RouteAccumulator.forRecord(true, 0.0, 0.0, false, false);
        RouteAccumulator cancelled = RouteAccumulator.forRecord(false, null, null, true, false);
        RouteAccumulator diverted = RouteAccumulator.forRecord(false, null, null, false, true);

        RouteAccumulator merged = new RouteAccumulator();
        merged.add(ok);
        merged.add(cancelled);
        merged.add(diverted);

        assertEquals(3, merged.totalFlights);
        assertEquals(1, merged.depDelayCount);
        assertEquals(1, merged.cancelledCount);
        assertEquals(1, merged.divertedCount);
        assertEquals(1.0 / 3.0, merged.cancellationRate(), 1e-9);
        assertEquals(1.0 / 3.0, merged.diversionRate(), 1e-9);
    }
}
