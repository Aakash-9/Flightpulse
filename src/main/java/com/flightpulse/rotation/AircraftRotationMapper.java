package com.flightpulse.rotation;

import com.flightpulse.util.SilverSchema;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;

import java.io.IOException;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;

/**
 * Job G - AircraftRotationMapper.
 *
 * Only RECORD_STATUS=VALID legs with a resolvable CRS_DEP_MIN and
 * CRS_ARR_MIN are candidates for rotation chaining - cancelled/diverted
 * flights have no real time data, and MISSING_TAIL records have no key to
 * chain on by definition.
 *
 * chronoMin is an absolute ordinal (epochDay*1440 + minutesSinceMidnight)
 * built from FL_DATE plus the derived day offset, NOT a timezone-aware
 * instant - this dataset has no airport timezone reference (see README).
 * It is internally consistent for ordering one aircraft's own legs
 * chronologically across the whole 2020-2025 span, which is what secondary
 * sort needs; it is NOT a claim that ground-time gaps computed from it are
 * correct to the minute across a timezone-crossing connection. That
 * limitation is carried forward into CarryoverAnalysisJob's documentation,
 * not hidden.
 */
public class AircraftRotationMapper extends Mapper<LongWritable, Text, TailChronoKey, FlightLeg> {

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
        if (!"VALID".equals(f[SilverSchema.RECORD_STATUS])) {
            return;
        }

        String tailNum = f[SilverSchema.TAIL_NUM];
        if (tailNum.isEmpty()) {
            return;
        }
        if (!SilverSchema.isPresent(f[SilverSchema.CRS_DEP_MIN]) || !SilverSchema.isPresent(f[SilverSchema.CRS_ARR_MIN])) {
            return;
        }

        LocalDate flDate;
        try {
            flDate = LocalDate.parse(f[SilverSchema.FL_DATE]);
        } catch (DateTimeParseException e) {
            return;
        }

        long epochDay = flDate.toEpochDay();
        int depDayOffset = (int) SilverSchema.parseDoubleOrZero(f[SilverSchema.CRS_DEP_DAY_OFFSET]);
        int arrDayOffset = (int) SilverSchema.parseDoubleOrZero(f[SilverSchema.CRS_ARR_DAY_OFFSET]);
        long crsDepMin = (long) SilverSchema.parseDoubleOrZero(f[SilverSchema.CRS_DEP_MIN]);
        long crsArrMin = (long) SilverSchema.parseDoubleOrZero(f[SilverSchema.CRS_ARR_MIN]);

        long crsDepChrono = (epochDay + depDayOffset) * 1440L + crsDepMin;
        long crsArrChrono = (epochDay + arrDayOffset) * 1440L + crsArrMin;

        FlightLeg leg = new FlightLeg();
        leg.flDate = f[SilverSchema.FL_DATE];
        leg.carrier = f[SilverSchema.OP_UNIQUE_CARRIER];
        leg.flightNum = f[SilverSchema.OP_CARRIER_FL_NUM];
        leg.origin = f[SilverSchema.ORIGIN];
        leg.dest = f[SilverSchema.DEST];
        leg.crsDepChronoMin = crsDepChrono;
        leg.crsArrChronoMin = crsArrChrono;
        leg.depDelay = SilverSchema.parseDoubleOrZero(f[SilverSchema.DEP_DELAY_MIN]);
        leg.arrDelay = SilverSchema.parseDoubleOrZero(f[SilverSchema.ARR_DELAY_MIN]);

        context.write(new TailChronoKey(tailNum, crsDepChrono), leg);
    }
}
