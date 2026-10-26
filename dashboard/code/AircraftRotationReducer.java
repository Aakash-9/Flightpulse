package com.flightpulse.rotation;

import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;

import java.io.IOException;
import java.util.Locale;

/**
 * Job G - AircraftRotationReducer.
 *
 * Receives every VALID leg for one tail number, already chronologically
 * sorted (secondary sort via TailChronoKey + TailGroupComparator). Walks
 * consecutive pairs (A, B) and classifies each candidate link:
 *
 *   DUPLICATE_RECORD      - A and B are the same flight (identical chrono + route)
 *   AMBIGUOUS_CHRONOLOGY  - A and B share the same scheduled-departure instant
 *                           but are different flights - physically impossible
 *                           for one tail number, flagged not silently resolved
 *   NEGATIVE_GROUND_TIME  - B's scheduled departure is before A's scheduled
 *                           arrival (overlapping/inconsistent schedule)
 *   ROUTE_DISCONTINUITY   - A's destination != B's origin (not a real rotation)
 *   GAP_TOO_LARGE         - ground time exceeds the configured threshold
 *                           (aircraft likely had other activity in between)
 *   LINKED                - passes every check; a valid candidate rotation link
 *
 * IMPORTANT NOTE REPEATED HERE (see AircraftRotationMapper/README): ground
 * time is computed from chronoMin, which is NOT timezone-aware. A flight
 * crossing time zones will show a ground-time gap that is off by the
 * timezone difference between the two airports involved. This is a known,
 * documented limitation, not a silently swallowed bug - see _SCHEMA.txt.
 */
public class AircraftRotationReducer extends Reducer<TailChronoKey, FlightLeg, Text, Text> {

    public static final long DEFAULT_MAX_GAP_MINUTES = 90;
    public static final String MAX_GAP_CONF_KEY = "flightpulse.rotation.maxGapMinutes";

    private long maxGapMinutes;

    @Override
    protected void setup(Context context) {
        maxGapMinutes = context.getConfiguration().getLong(MAX_GAP_CONF_KEY, DEFAULT_MAX_GAP_MINUTES);
    }

    @Override
    protected void reduce(TailChronoKey key, Iterable<FlightLeg> values, Context context)
            throws IOException, InterruptedException {
        FlightLeg prev = null;

        for (FlightLeg current : values) {
            // Reducer framework reuses the Writable instance across iterations;
            // copy out the fields we need before the next iteration overwrites it.
            FlightLeg leg = copy(current);

            if (prev != null) {
                emitLink(context, key.tailNum, prev, leg);
            }
            prev = leg;
        }
    }

    private void emitLink(Context context, String tailNum, FlightLeg a, FlightLeg b)
            throws IOException, InterruptedException {
        LinkClassification c = LinkClassification.classify(a, b, maxGapMinutes);
        context.write(new Text(tailNum), new Text(formatLine(a, b, c.groundMinutes, c.status)));
    }

    private String formatLine(FlightLeg a, FlightLeg b, long groundMin, String status) {
        return String.format(Locale.US, "%s|%s|%s|%s|%d|%.2f|%.2f|%s",
                a.id(), b.id(), a.dest, b.origin, groundMin, a.arrDelay, b.depDelay, status);
    }

    private FlightLeg copy(FlightLeg src) {
        FlightLeg l = new FlightLeg();
        l.flDate = src.flDate;
        l.carrier = src.carrier;
        l.flightNum = src.flightNum;
        l.origin = src.origin;
        l.dest = src.dest;
        l.crsDepChronoMin = src.crsDepChronoMin;
        l.crsArrChronoMin = src.crsArrChronoMin;
        l.depDelay = src.depDelay;
        l.arrDelay = src.arrDelay;
        return l;
    }
}
