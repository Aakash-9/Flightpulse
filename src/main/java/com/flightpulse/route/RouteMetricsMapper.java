package com.flightpulse.route;

import com.flightpulse.util.SilverSchema;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;

import java.io.IOException;

/**
 * Job D - RouteMetricsMapper. Key is "ORIGIN-DEST" (directional - LAX-JFK
 * and JFK-LAX are different routes, which is correct: they're operationally
 * distinct).
 */
public class RouteMetricsMapper extends Mapper<LongWritable, Text, Text, RouteAccumulator> {

    @Override
    protected void map(LongWritable key, Text value, Context context) throws IOException, InterruptedException {
        String line = value.toString();
        if (line.isEmpty()) {
            return;
        }
        String[] f = line.split(SilverSchema.DELIMITER, -1);
        if (f.length != SilverSchema.COLUMN_COUNT) {
            return;
        }

        String status = f[SilverSchema.RECORD_STATUS];
        boolean operated = "VALID".equals(status) || "MISSING_TAIL".equals(status);
        boolean cancelled = "CANCELLED".equals(status);
        boolean diverted = "DIVERTED".equals(status);

        String origin = f[SilverSchema.ORIGIN];
        String dest = f[SilverSchema.DEST];
        if (origin.isEmpty() || dest.isEmpty()) {
            return;
        }

        Double depDelay = SilverSchema.isPresent(f[SilverSchema.DEP_DELAY_MIN])
                ? SilverSchema.parseDoubleOrZero(f[SilverSchema.DEP_DELAY_MIN]) : null;
        Double arrDelay = SilverSchema.isPresent(f[SilverSchema.ARR_DELAY_MIN])
                ? SilverSchema.parseDoubleOrZero(f[SilverSchema.ARR_DELAY_MIN]) : null;

        Text routeKey = new Text(origin + "-" + dest);
        context.write(routeKey, RouteAccumulator.forRecord(operated, depDelay, arrDelay, cancelled, diverted));
    }
}
