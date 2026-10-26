package com.flightpulse.airport;

import com.flightpulse.util.SilverSchema;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;

import java.io.IOException;

/**
 * Job C - AirportMetricsMapper.
 *
 * Reads Silver (no header line in the data itself). Each record contributes
 * to TWO airport keys: its ORIGIN (as a departure) and its DEST (as an
 * arrival). CANCELLED/DIVERTED records have no delay value and are excluded
 * from delay-rate denominators, but still count toward totalDepartures and
 * the cancellation/diversion rate numerators/denominators.
 */
public class AirportMetricsMapper extends Mapper<LongWritable, Text, Text, AirportAccumulator> {

    @Override
    protected void map(LongWritable key, Text value, Context context) throws IOException, InterruptedException {
        String line = value.toString();
        if (line.isEmpty()) {
            return;
        }
        String[] f = line.split(SilverSchema.DELIMITER, -1);
        if (f.length != SilverSchema.COLUMN_COUNT) {
            return; // Silver is already validated; a mismatch here would be a pipeline bug, not data noise.
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

        context.write(new Text(origin), AirportAccumulator.forOrigin(operated, depDelay, cancelled, diverted));
        context.write(new Text(dest), AirportAccumulator.forDest(operated, arrDelay));
    }
}
