package com.flightpulse.airport;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class AirportAccumulatorTest {

    @Test
    void meanAndRateComputedCorrectlyAcrossMergedPartials() {
        // Simulates what a combiner then reducer would merge: three operated
        // departures with delays 0, 10, 30 (one >=15 => rate 1/3), plus one
        // cancelled flight (counts toward totalDepartures and cancellationRate).
        AirportAccumulator a = AirportAccumulator.forOrigin(true, 0.0, false, false);
        AirportAccumulator b = AirportAccumulator.forOrigin(true, 10.0, false, false);
        AirportAccumulator c = AirportAccumulator.forOrigin(true, 30.0, false, false);
        AirportAccumulator cancelled = AirportAccumulator.forOrigin(false, null, true, false);

        AirportAccumulator merged = new AirportAccumulator();
        merged.add(a);
        merged.add(b);
        merged.add(c);
        merged.add(cancelled);

        assertEquals(4, merged.totalDepartures);
        assertEquals(3, merged.depDelayCount); // cancelled flight excluded from delay sample
        assertEquals(1, merged.cancelledAsOrigin);
        assertEquals((0.0 + 10.0 + 30.0) / 3.0, merged.meanDepDelay(), 1e-9);
        assertEquals(1.0 / 3.0, merged.depDelayRate(), 1e-9); // only the 30-min delay crosses 15
        assertEquals(0.25, merged.cancellationRate(), 1e-9); // 1 of 4 total departures
    }

    @Test
    void emptyAccumulatorHasZeroRatesNotDivideByZeroCrash() {
        AirportAccumulator a = new AirportAccumulator();
        assertEquals(0.0, a.meanDepDelay());
        assertEquals(0.0, a.depDelayRate());
        assertEquals(0.0, a.cancellationRate());
        assertEquals(0.0, a.stdDevDepDelay());
    }

    @Test
    void stdDevIsZeroWhenAllValuesIdentical() {
        AirportAccumulator a = AirportAccumulator.forOrigin(true, 10.0, false, false);
        AirportAccumulator b = AirportAccumulator.forOrigin(true, 10.0, false, false);
        AirportAccumulator merged = new AirportAccumulator();
        merged.add(a);
        merged.add(b);
        assertEquals(0.0, merged.stdDevDepDelay(), 1e-9);
    }
}
