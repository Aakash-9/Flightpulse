package com.flightpulse.temporal;

import com.flightpulse.route.RouteAccumulator;
import com.flightpulse.util.SilverSchema;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;

import java.io.IOException;
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;

/**
 * Job E - TemporalMetricsMapper.
 *
 * Emits the SAME record's delay/cancellation/diversion contribution under
 * four independent time-dimension keys (year, year-month, weekday,
 * scheduled-departure hour), reusing RouteAccumulator's aggregation math -
 * the computation is identical ("how disrupted was this bucket"), only the
 * bucketing key differs from RouteMetricsMapper.
 *
 * Scheduled-departure hour comes from CRS_DEP_MIN, which is a DERIVED field
 * (actual - delay; see NormalizedFlight) - it is absent for cancelled/
 * diverted flights and for any record where that derivation failed, so the
 * HOUR dimension's sample size is smaller than YEAR/MONTH/WEEKDAY's. That is
 * documented in the output schema, not hidden.
 */
public class TemporalMetricsMapper extends Mapper<LongWritable, Text, Text, RouteAccumulator> {

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

        LocalDate flDate;
        try {
            flDate = LocalDate.parse(f[SilverSchema.FL_DATE]);
        } catch (DateTimeParseException e) {
            return; // Silver's FL_DATE is already validated at normalize time; defensive only.
        }

        Double depDelay = SilverSchema.isPresent(f[SilverSchema.DEP_DELAY_MIN])
                ? SilverSchema.parseDoubleOrZero(f[SilverSchema.DEP_DELAY_MIN]) : null;
        Double arrDelay = SilverSchema.isPresent(f[SilverSchema.ARR_DELAY_MIN])
                ? SilverSchema.parseDoubleOrZero(f[SilverSchema.ARR_DELAY_MIN]) : null;

        RouteAccumulator contribution = RouteAccumulator.forRecord(operated, depDelay, arrDelay, cancelled, diverted);

        context.write(new Text("YEAR|" + flDate.getYear()), contribution);
        context.write(new Text("MONTH|" + String.format("%04d-%02d", flDate.getYear(), flDate.getMonthValue())), contribution);

        DayOfWeek dow = flDate.getDayOfWeek();
        context.write(new Text("WEEKDAY|" + String.format("%d-%s", dow.getValue(), dow.name())), contribution);

        if (SilverSchema.isPresent(f[SilverSchema.CRS_DEP_MIN])) {
            int crsDepMin = (int) SilverSchema.parseDoubleOrZero(f[SilverSchema.CRS_DEP_MIN]);
            int hour = Math.floorDiv(crsDepMin, 60);
            if (hour >= 0 && hour <= 23) {
                context.write(new Text(String.format("HOUR|%02d", hour)), contribution);
                // 7x24 heatmap cell: weekday and scheduled-departure hour together.
                context.write(new Text(String.format("WEEKDAYHOUR|%d-%s|%02d", dow.getValue(), dow.name(), hour)), contribution);
            }
        }
    }
}
