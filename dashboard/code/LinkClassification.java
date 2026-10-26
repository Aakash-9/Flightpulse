package com.flightpulse.rotation;

/**
 * Pure classification logic for a candidate (legA, legB) rotation link,
 * extracted out of AircraftRotationReducer so it's directly unit-testable
 * without a MapReduce test harness.
 */
public final class LinkClassification {

    public final String status;
    public final long groundMinutes;

    private LinkClassification(String status, long groundMinutes) {
        this.status = status;
        this.groundMinutes = groundMinutes;
    }

    public static LinkClassification classify(FlightLeg a, FlightLeg b, long maxGapMinutes) {
        if (a.crsDepChronoMin == b.crsDepChronoMin) {
            boolean identical = a.origin.equals(b.origin) && a.dest.equals(b.dest)
                    && a.flightNum.equals(b.flightNum) && a.crsArrChronoMin == b.crsArrChronoMin;
            return new LinkClassification(identical ? "DUPLICATE_RECORD" : "AMBIGUOUS_CHRONOLOGY", 0);
        }

        long groundMin = b.crsDepChronoMin - a.crsArrChronoMin;
        if (groundMin < 0) {
            return new LinkClassification("NEGATIVE_GROUND_TIME", groundMin);
        }
        if (!a.dest.equals(b.origin)) {
            return new LinkClassification("ROUTE_DISCONTINUITY", groundMin);
        }
        if (groundMin > maxGapMinutes) {
            return new LinkClassification("GAP_TOO_LARGE", groundMin);
        }
        return new LinkClassification("LINKED", groundMin);
    }
}
