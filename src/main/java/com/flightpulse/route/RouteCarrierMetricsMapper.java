package com.flightpulse.route;

import com.flightpulse.util.SilverSchema;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;

import java.io.IOException;

/**
 * Per route x airline metrics, overall and by scheduled-departure time band.
 *
 * Keys:
 *   RC|ORIGIN-DEST|CARRIER            all flights (incl. cancelled/diverted)
 *   RCB|ORIGIN-DEST|CARRIER|BAND      operated flights with a derivable
 *                                     scheduled departure only
 *
 * Cancelled/diverted flights have no actual times, so no derivable scheduled
 * time, so they cannot be placed in a band: cancellation/diversion rates in
 * RCB rows are therefore not meaningful and must not be displayed. RC rows
 * carry the honest cancellation/diversion rates.
 *
 * Bands (scheduled local departure hour): MORNING 05-11, AFTERNOON 12-16,
 * EVENING 17-21, NIGHT 22-04.
 */
public class RouteCarrierMetricsMapper extends Mapper<LongWritable, Text, Text, RouteAccumulator> {

    @Override
    protected void map(LongWritable key, Text value, Context context) throws IOException, InterruptedException {
        String line = value.toString();
        if (line.isEmpty()) return;
        String[] f = line.split(SilverSchema.DELIMITER, -1);
        if (f.length != SilverSchema.COLUMN_COUNT) return;

        String status = f[SilverSchema.RECORD_STATUS];
        boolean operated = "VALID".equals(status) || "MISSING_TAIL".equals(status);
        boolean cancelled = "CANCELLED".equals(status);
        boolean diverted = "DIVERTED".equals(status);

        String origin = f[SilverSchema.ORIGIN];
        String dest = f[SilverSchema.DEST];
        String carrier = f[SilverSchema.OP_UNIQUE_CARRIER];
        if (origin.isEmpty() || dest.isEmpty() || carrier.isEmpty()) return;

        Double depDelay = SilverSchema.isPresent(f[SilverSchema.DEP_DELAY_MIN])
                ? SilverSchema.parseDoubleOrZero(f[SilverSchema.DEP_DELAY_MIN]) : null;
        Double arrDelay = SilverSchema.isPresent(f[SilverSchema.ARR_DELAY_MIN])
                ? SilverSchema.parseDoubleOrZero(f[SilverSchema.ARR_DELAY_MIN]) : null;

        RouteAccumulator contribution = RouteAccumulator.forRecord(operated, depDelay, arrDelay, cancelled, diverted);
        String rc = origin + "-" + dest + "|" + carrier;
        context.write(new Text("RC|" + rc), contribution);

        if (operated && SilverSchema.isPresent(f[SilverSchema.CRS_DEP_MIN])) {
            int hour = Math.floorDiv((int) SilverSchema.parseDoubleOrZero(f[SilverSchema.CRS_DEP_MIN]), 60);
            if (hour >= 0 && hour <= 23) {
                context.write(new Text("RCB|" + rc + "|" + band(hour)), contribution);
            }
        }
    }

    static String band(int hour) {
        if (hour >= 5 && hour <= 11) return "MORNING";
        if (hour >= 12 && hour <= 16) return "AFTERNOON";
        if (hour >= 17 && hour <= 21) return "EVENING";
        return "NIGHT";
    }
}
