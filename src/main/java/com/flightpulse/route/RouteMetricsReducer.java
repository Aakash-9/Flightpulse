package com.flightpulse.route;

import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;

import java.io.IOException;
import java.util.Locale;

/**
 * Final reduce. Flags (does not drop) routes below MIN_SAMPLE_SIZE so a
 * later ranking step can exclude them, per the brief's "minimum-sample-size
 * rules for rankings" requirement - the route still appears in the output,
 * just marked unreliable for ranking purposes.
 */
public class RouteMetricsReducer extends Reducer<Text, RouteAccumulator, Text, Text> {

    public static final long MIN_SAMPLE_SIZE = 30;

    @Override
    protected void reduce(Text key, Iterable<RouteAccumulator> values, Context context)
            throws IOException, InterruptedException {
        RouteAccumulator r = new RouteAccumulator();
        for (RouteAccumulator v : values) {
            r.add(v);
        }

        boolean lowSample = r.totalFlights < MIN_SAMPLE_SIZE;

        String line = String.format(Locale.US,
                "%d|%d|%d|%.4f|%.4f|%.2f|%.2f|%.2f|%.2f|%.4f|%.4f|%d|%d|%d",
                r.totalFlights, r.depDelayCount, r.arrDelayCount,
                r.depDelayRate(), r.arrDelayRate(),
                r.meanDepDelay(), r.meanArrDelay(),
                r.stdDevDepDelay(), r.stdDevArrDelay(),
                r.cancellationRate(), r.diversionRate(),
                r.cancelledCount, r.divertedCount,
                lowSample ? 1 : 0);

        context.write(key, new Text(line));
    }
}
