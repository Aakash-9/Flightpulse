package com.flightpulse.carryover;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

/**
 * Job H mapper. Reads AircraftRotationJob output lines
 *   TAIL \t legA|legB|aDest|bOrigin|groundMin|aArrDelay|bDepDelay|STATUS
 * and evaluates every (maxGap, minTurnaround) parameter combination in one
 * pass, using in-mapper combining (accumulators held in arrays and flushed in
 * cleanup()) so the shuffle carries a few thousand records, not one per link.
 *
 * A link is eligible for a given maxGap when STATUS is LINKED or GAP_TOO_LARGE
 * (GAP_TOO_LARGE is only assigned to route-continuous, non-negative links, so
 * it can be re-admitted when a larger maxGap than the rotation run's is being
 * tested) and groundMin <= maxGap.
 */
public class CarryoverMapper extends Mapper<LongWritable, Text, Text, CarryoverAccumulator> {

    public static final String GAPS_KEY = "flightpulse.carryover.gaps";
    public static final String TURNAROUNDS_KEY = "flightpulse.carryover.turnarounds";

    static final String[] SLACK_BUCKETS = {"<0", "0-14", "15-29", "30-59", "60+"};
    static final String[] ARR_BUCKETS = {"<=0", "1-14", "15-44", "45-89", "90+"};
    static final int FIRST_YEAR = 2020;
    static final int YEARS = 6;

    private long[] gaps;
    private double[] turnarounds;
    private int combos;

    private CarryoverAccumulator[] all;
    private CarryoverAccumulator[][] bySlack;
    private CarryoverAccumulator[][] byArr;
    private CarryoverAccumulator[][] byYear;
    private Map<String, CarryoverAccumulator>[] byAirport;
    private Map<String, CarryoverAccumulator>[] byCarrier;

    @Override
    @SuppressWarnings("unchecked")
    protected void setup(Context context) {
        Configuration conf = context.getConfiguration();
        String[] g = conf.get(GAPS_KEY, "60,90,120").split(",");
        String[] t = conf.get(TURNAROUNDS_KEY, "20,30,45").split(",");
        gaps = new long[g.length];
        turnarounds = new double[t.length];
        for (int i = 0; i < g.length; i++) gaps[i] = Long.parseLong(g[i].trim());
        for (int i = 0; i < t.length; i++) turnarounds[i] = Double.parseDouble(t[i].trim());
        combos = gaps.length * turnarounds.length;

        all = new CarryoverAccumulator[combos];
        bySlack = new CarryoverAccumulator[combos][SLACK_BUCKETS.length];
        byArr = new CarryoverAccumulator[combos][ARR_BUCKETS.length];
        byYear = new CarryoverAccumulator[combos][YEARS];
        byAirport = new Map[combos];
        byCarrier = new Map[combos];
        for (int c = 0; c < combos; c++) {
            all[c] = new CarryoverAccumulator();
            for (int i = 0; i < SLACK_BUCKETS.length; i++) bySlack[c][i] = new CarryoverAccumulator();
            for (int i = 0; i < ARR_BUCKETS.length; i++) byArr[c][i] = new CarryoverAccumulator();
            for (int i = 0; i < YEARS; i++) byYear[c][i] = new CarryoverAccumulator();
            byAirport[c] = new HashMap<>();
            byCarrier[c] = new HashMap<>();
        }
    }

    @Override
    protected void map(LongWritable key, Text value, Context context) {
        String line = value.toString();
        int tab = line.indexOf('\t');
        if (tab < 0) return;
        String[] f = line.substring(tab + 1).split("\\|", -1);
        if (f.length != 8) return;

        String status = f[7];
        if (!"LINKED".equals(status) && !"GAP_TOO_LARGE".equals(status)) return;

        long ground;
        double arrDelayA;
        double depDelayB;
        try {
            ground = Long.parseLong(f[4]);
            arrDelayA = Double.parseDouble(f[5]);
            depDelayB = Double.parseDouble(f[6]);
        } catch (NumberFormatException e) {
            context.getCounter("Carryover", "UNPARSEABLE_LINK").increment(1);
            return;
        }

        String aDest = f[2];
        // leg A id looks like "2024-07-12 YX4735 LGA-BNA": the airline code is the first 2 characters of the 2nd token
        String[] legParts = f[0].split(" ");
        String carrier = legParts.length > 1 && legParts[1].length() >= 2 ? legParts[1].substring(0, 2) : "??";
        int year = -1;
        if (f[0].length() >= 4) {
            try {
                year = Integer.parseInt(f[0].substring(0, 4)) - FIRST_YEAR;
            } catch (NumberFormatException ignored) {
                // leave year bucket out; link still counts in ALL/slack/arrival buckets
            }
        }
        int arrBkt = arrBucket(arrDelayA);

        for (int gi = 0; gi < gaps.length; gi++) {
            if (ground > gaps[gi]) continue;
            for (int ti = 0; ti < turnarounds.length; ti++) {
                int c = gi * turnarounds.length + ti;
                double slack = CarryoverMath.slack(ground, turnarounds[ti]);
                double exposure = CarryoverMath.potentialExposure(arrDelayA, slack);
                double carry = CarryoverMath.estimatedCarryover(depDelayB, exposure);

                all[c].addLink(arrDelayA, depDelayB, exposure, carry);
                bySlack[c][slackBucket(slack)].addLink(arrDelayA, depDelayB, exposure, carry);
                byArr[c][arrBkt].addLink(arrDelayA, depDelayB, exposure, carry);
                if (year >= 0 && year < YEARS) {
                    byYear[c][year].addLink(arrDelayA, depDelayB, exposure, carry);
                }
                byAirport[c].computeIfAbsent(aDest, k -> new CarryoverAccumulator())
                        .addLink(arrDelayA, depDelayB, exposure, carry);
                byCarrier[c].computeIfAbsent(carrier, k -> new CarryoverAccumulator())
                        .addLink(arrDelayA, depDelayB, exposure, carry);
            }
        }
    }

    @Override
    protected void cleanup(Context context) throws IOException, InterruptedException {
        for (int gi = 0; gi < gaps.length; gi++) {
            for (int ti = 0; ti < turnarounds.length; ti++) {
                int c = gi * turnarounds.length + ti;
                String p = "G" + gaps[gi] + "_T" + (long) turnarounds[ti] + "|";
                emit(context, p + "ALL", all[c]);
                for (int i = 0; i < SLACK_BUCKETS.length; i++) emit(context, p + "SLACK|" + SLACK_BUCKETS[i], bySlack[c][i]);
                for (int i = 0; i < ARR_BUCKETS.length; i++) emit(context, p + "ARRDELAY_A|" + ARR_BUCKETS[i], byArr[c][i]);
                for (int i = 0; i < YEARS; i++) emit(context, p + "YEAR|" + (FIRST_YEAR + i), byYear[c][i]);
                for (Map.Entry<String, CarryoverAccumulator> e : byAirport[c].entrySet()) {
                    emit(context, p + "AIRPORT|" + e.getKey(), e.getValue());
                }
                for (Map.Entry<String, CarryoverAccumulator> e : byCarrier[c].entrySet()) {
                    emit(context, p + "CARRIER|" + e.getKey(), e.getValue());
                }
            }
        }
    }

    private static void emit(Context context, String key, CarryoverAccumulator a) throws IOException, InterruptedException {
        if (a.n > 0) context.write(new Text(key), a);
    }

    static int slackBucket(double slack) {
        if (slack < 0) return 0;
        if (slack < 15) return 1;
        if (slack < 30) return 2;
        if (slack < 60) return 3;
        return 4;
    }

    static int arrBucket(double arrDelay) {
        if (arrDelay <= 0) return 0;
        if (arrDelay < 15) return 1;
        if (arrDelay < 45) return 2;
        if (arrDelay < 90) return 3;
        return 4;
    }
}
