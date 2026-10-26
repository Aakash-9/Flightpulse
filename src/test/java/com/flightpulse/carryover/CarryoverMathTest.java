package com.flightpulse.carryover;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class CarryoverMathTest {

    private static final double TA = 30.0;

    private static double carryover(double ground, double arrDelayA, double depDelayB) {
        double slack = CarryoverMath.slack(ground, TA);
        double exposure = CarryoverMath.potentialExposure(arrDelayA, slack);
        return CarryoverMath.estimatedCarryover(depDelayB, exposure);
    }

    @Test
    void insufficientSlackLeavesExposureEqualToDelayBeyondSlack() {
        // ground 40, turnaround 30 -> slack 10; A 25 late -> exposure 15
        assertEquals(10.0, CarryoverMath.slack(40, TA));
        assertEquals(15.0, CarryoverMath.potentialExposure(25, 10));
    }

    @Test
    void sufficientSlackAbsorbsTheDelayCompletely() {
        // ground 85 -> slack 55; A 25 late is fully absorbed
        assertEquals(0.0, carryover(85, 25, 40));
    }

    @Test
    void carryoverIsCappedByBsActualDepartureDelay() {
        // exposure 15, B left only 5 late -> carryover 5
        assertEquals(5.0, carryover(40, 25, 5));
    }

    @Test
    void carryoverIsCappedByExposureWhenBIsLaterThanExposure() {
        // exposure 15, B left 20 late -> carryover 15 (the other 5 is not attributable to A)
        assertEquals(15.0, carryover(40, 25, 20));
    }

    @Test
    void negativeArrivalDelayCreatesNoExposure() {
        assertEquals(0.0, CarryoverMath.potentialExposure(-10, 10));
        assertEquals(0.0, carryover(40, -10, 30));
    }

    @Test
    void negativeDepartureDelayOfBGivesZeroCarryover() {
        assertEquals(0.0, carryover(40, 25, -3));
    }

    @Test
    void zeroDelaysGiveZero() {
        assertEquals(0.0, carryover(40, 0, 0));
    }

    @Test
    void negativeSlackAddsToExposure() {
        // ground 20, turnaround 30 -> slack -10; A only 5 late -> exposure 15
        assertEquals(-10.0, CarryoverMath.slack(20, TA));
        assertEquals(15.0, CarryoverMath.potentialExposure(5, -10));
    }
}
