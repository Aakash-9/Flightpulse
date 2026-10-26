package com.flightpulse.airport;

import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;

import java.io.IOException;
import java.util.Locale;

/**
 * Final reduce: merges all partial accumulators for an airport (same
 * associative add() as the combiner) and formats the result row. Output is
 * pipe-delimited; see AirportMetricsJob for the header this corresponds to.
 *
 * Rates and raw counts are both included deliberately - a rate alone
 * invites exactly the mistake the project brief warns against (treating a
 * high-volume airport as "most disrupted" from a rate computed on a tiny
 * sample, or vice versa hiding a low sample size behind a rate).
 */
public class AirportMetricsReducer extends Reducer<Text, AirportAccumulator, Text, Text> {

    @Override
    protected void reduce(Text key, Iterable<AirportAccumulator> values, Context context)
            throws IOException, InterruptedException {
        AirportAccumulator a = new AirportAccumulator();
        for (AirportAccumulator v : values) {
            a.add(v);
        }

        String line = String.format(Locale.US,
                "%d|%d|%d|%d|%.4f|%.4f|%.2f|%.2f|%.2f|%.2f|%.4f|%.4f|%d|%d",
                a.totalDepartures, a.totalArrivals,
                a.depDelayCount, a.arrDelayCount,
                a.depDelayRate(), a.arrDelayRate(),
                a.meanDepDelay(), a.meanArrDelay(),
                a.stdDevDepDelay(), a.stdDevArrDelay(),
                a.cancellationRate(), a.diversionRate(),
                a.cancelledAsOrigin, a.divertedAsOrigin);

        context.write(key, new Text(line));
    }
}
