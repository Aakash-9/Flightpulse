package com.flightpulse.rotation;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class LinkClassificationTest {

    private static final long MAX_GAP = 90;

    private static FlightLeg leg(String origin, String dest, long depChrono, long arrChrono, String flightNum) {
        FlightLeg l = new FlightLeg();
        l.flDate = "2020-01-01";
        l.carrier = "AA";
        l.flightNum = flightNum;
        l.origin = origin;
        l.dest = dest;
        l.crsDepChronoMin = depChrono;
        l.crsArrChronoMin = arrChrono;
        l.depDelay = 0;
        l.arrDelay = 0;
        return l;
    }

    @Test
    void validConnectionWithinThresholdIsLinked() {
        // A: DFW->EGE arrives at chrono 1000. B: EGE->DFW departs at chrono 1060 (60 min ground time).
        FlightLeg a = leg("DFW", "EGE", 900, 1000, "178");
        FlightLeg b = leg("EGE", "DFW", 1060, 1200, "784");
        LinkClassification c = LinkClassification.classify(a, b, MAX_GAP);
        assertEquals("LINKED", c.status);
        assertEquals(60, c.groundMinutes);
    }

    @Test
    void groundTimeExactlyAtThresholdIsLinked() {
        FlightLeg a = leg("DFW", "EGE", 900, 1000, "178");
        FlightLeg b = leg("EGE", "DFW", 1000 + MAX_GAP, 1200, "784");
        LinkClassification c = LinkClassification.classify(a, b, MAX_GAP);
        assertEquals("LINKED", c.status);
    }

    @Test
    void groundTimeOneMinuteOverThresholdIsGapTooLarge() {
        FlightLeg a = leg("DFW", "EGE", 900, 1000, "178");
        FlightLeg b = leg("EGE", "DFW", 1000 + MAX_GAP + 1, 1200, "784");
        LinkClassification c = LinkClassification.classify(a, b, MAX_GAP);
        assertEquals("GAP_TOO_LARGE", c.status);
    }

    @Test
    void mismatchedRouteIsDiscontinuity() {
        // A lands at EGE, but B departs from somewhere else entirely (MIA) - not a real rotation leg.
        FlightLeg a = leg("DFW", "EGE", 900, 1000, "178");
        FlightLeg b = leg("MIA", "JFK", 1060, 1200, "999");
        LinkClassification c = LinkClassification.classify(a, b, MAX_GAP);
        assertEquals("ROUTE_DISCONTINUITY", c.status);
    }

    @Test
    void bDepartingBeforeAArrivesIsNegativeGroundTime() {
        FlightLeg a = leg("DFW", "EGE", 900, 1000, "178");
        FlightLeg b = leg("EGE", "DFW", 950, 1100, "784"); // departs before A even arrives
        LinkClassification c = LinkClassification.classify(a, b, MAX_GAP);
        assertEquals("NEGATIVE_GROUND_TIME", c.status);
        assertEquals(-50, c.groundMinutes);
    }

    @Test
    void identicalFlightsAtSameChronoAreDuplicateRecord() {
        FlightLeg a = leg("DFW", "EGE", 900, 1000, "178");
        FlightLeg b = leg("DFW", "EGE", 900, 1000, "178");
        LinkClassification c = LinkClassification.classify(a, b, MAX_GAP);
        assertEquals("DUPLICATE_RECORD", c.status);
    }

    @Test
    void differentFlightsSharingSameScheduledDepartureAreAmbiguous() {
        // Same tail number physically cannot operate two different flights
        // departing at the same scheduled instant - flagged, not resolved.
        FlightLeg a = leg("DFW", "EGE", 900, 1000, "178");
        FlightLeg b = leg("DFW", "MIA", 900, 1100, "999");
        LinkClassification c = LinkClassification.classify(a, b, MAX_GAP);
        assertEquals("AMBIGUOUS_CHRONOLOGY", c.status);
    }

    @Test
    void zeroGroundTimeIsStillLinked() {
        FlightLeg a = leg("DFW", "EGE", 900, 1000, "178");
        FlightLeg b = leg("EGE", "DFW", 1000, 1200, "784"); // departs the instant A arrives
        LinkClassification c = LinkClassification.classify(a, b, MAX_GAP);
        assertEquals("LINKED", c.status);
        assertEquals(0, c.groundMinutes);
    }
}
