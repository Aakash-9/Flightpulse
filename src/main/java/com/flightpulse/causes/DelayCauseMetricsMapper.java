package com.flightpulse.causes;

import com.flightpulse.util.SilverSchema;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

/**
 * Job F mapper with in-mapper combining. Each Silver record contributes to
 * ALL, YEAR, MONTHOFYEAR (seasonality, 01-12), CARRIER and ORIGIN-airport
 * buckets. Only a few hundred distinct keys exist, so the per-mapper map is
 * tiny and the shuffle carries only the flushed partial aggregates.
 */
public class DelayCauseMetricsMapper extends Mapper<LongWritable, Text, Text, DelayCauseAccumulator> {

    private final Map<String, DelayCauseAccumulator> acc = new HashMap<>();

    @Override
    protected void map(LongWritable key, Text value, Context context) {
        String line = value.toString();
        if (line.isEmpty()) return;
        String[] f = line.split(SilverSchema.DELIMITER, -1);
        if (f.length != SilverSchema.COLUMN_COUNT) return;

        String status = f[SilverSchema.RECORD_STATUS];
        boolean operated = "VALID".equals(status) || "MISSING_TAIL".equals(status);
        boolean cancelled = "CANCELLED".equals(status);
        boolean diverted = "DIVERTED".equals(status);

        Double dep = number(f[SilverSchema.DEP_DELAY_MIN]);
        Double arr = number(f[SilverSchema.ARR_DELAY_MIN]);
        Double[] causes = {
                number(f[SilverSchema.CARRIER_DELAY_MIN]),
                number(f[SilverSchema.WEATHER_DELAY_MIN]),
                number(f[SilverSchema.NAS_DELAY_MIN]),
                number(f[SilverSchema.SECURITY_DELAY_MIN]),
                number(f[SilverSchema.LATE_AIRCRAFT_DELAY_MIN])
        };

        String date = f[SilverSchema.FL_DATE];
        if (date.length() < 7) return;

        String year = date.substring(0, 4);
        String carrier = f[SilverSchema.OP_UNIQUE_CARRIER];
        String origin = f[SilverSchema.ORIGIN];
        String dest = f[SilverSchema.DEST];
        String[] keys = {
                "ALL",
                "YEAR|" + year,
                "MONTHOFYEAR|" + date.substring(5, 7),
                "CARRIER|" + carrier,
                "ORIGIN|" + origin,
                // Added for the city / route / airline explorers and the question-answering page:
                "DEST|" + dest,                           // what happens to flights arriving at a city
                "ROUTE|" + origin + "-" + dest,           // why a given route runs late
                "ORIGINYEAR|" + origin + "|" + year,      // a city, year by year
                "CARRIERYEAR|" + carrier + "|" + year,    // an airline, year by year
                "CARRIERORIGIN|" + carrier + "|" + origin // an airline at a given city
        };
        for (String k : keys) {
            acc.computeIfAbsent(k, x -> new DelayCauseAccumulator())
                    .addFlight(operated, cancelled, diverted, f[SilverSchema.CANCELLATION_CODE], dep, arr, causes);
        }
    }

    @Override
    protected void cleanup(Context context) throws IOException, InterruptedException {
        for (Map.Entry<String, DelayCauseAccumulator> e : acc.entrySet()) {
            context.write(new Text(e.getKey()), e.getValue());
        }
    }

    private static Double number(String s) {
        if (!SilverSchema.isPresent(s)) return null;
        try {
            return Double.parseDouble(s);
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
