package com.flightpulse.carryover;

import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;

import java.io.IOException;
import java.util.Locale;

public final class CarryoverReducers {

    private CarryoverReducers() {
    }

    /** Merges partial accumulators for a key; same type in and out. */
    public static class Combiner extends Reducer<Text, CarryoverAccumulator, Text, CarryoverAccumulator> {
        @Override
        protected void reduce(Text key, Iterable<CarryoverAccumulator> values, Context context)
                throws IOException, InterruptedException {
            CarryoverAccumulator m = new CarryoverAccumulator();
            for (CarryoverAccumulator v : values) m.add(v);
            context.write(key, m);
        }
    }

    /** Final reduce: merge, then format the metric row. */
    public static class Finalizer extends Reducer<Text, CarryoverAccumulator, Text, Text> {

        public static final long LOW_SAMPLE_BELOW = 100;

        @Override
        protected void reduce(Text key, Iterable<CarryoverAccumulator> values, Context context)
                throws IOException, InterruptedException {
            CarryoverAccumulator a = new CarryoverAccumulator();
            for (CarryoverAccumulator v : values) a.add(v);

            long nANotLate = a.n - a.nALate15;
            String line = String.format(Locale.US,
                    "%d|%d|%.4f|%.3f|%.3f|%.3f|%.3f|%.4f|%d|%d|%.4f|%.4f|%d",
                    a.n, a.nExposed, ratio(a.nExposed, a.n),
                    ratio(a.sumArrDelayAPos, a.n),
                    ratio(a.sumExposure, a.n),
                    ratio(a.sumCarryover, a.n),
                    ratio(a.sumDepDelayBPos, a.n),
                    ratio(a.sumCarryover, a.sumExposure),
                    a.nALate15, nANotLate,
                    ratio(a.nBLate15GivenALate15, a.nALate15),
                    ratio(a.nBLate15GivenANotLate15, nANotLate),
                    a.n < LOW_SAMPLE_BELOW ? 1 : 0);
            context.write(key, new Text(line));
        }

        private static double ratio(double num, double den) {
            return den == 0 ? 0.0 : num / den;
        }
    }
}
