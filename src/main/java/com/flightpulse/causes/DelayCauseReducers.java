package com.flightpulse.causes;

import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;

import java.io.IOException;
import java.util.Locale;

public final class DelayCauseReducers {

    private DelayCauseReducers() {
    }

    public static final String HEADER = String.join("|",
            "KEY(dimension|value)",
            "N_FLIGHTS_SCHEDULED", "N_OPERATED", "N_CANCELLED", "N_DIVERTED",
            "CANCELLATION_RATE", "DIVERSION_RATE",
            "N_DELAYED_15PLUS", "DELAYED_15PLUS_RATE_OF_OPERATED",
            "MEAN_ARR_DELAY_MIN", "MEAN_DEP_DELAY_MIN", "MEAN_ENROUTE_GAIN_MIN",
            "N_CAUSE_REPORTED", "N_CAUSE_NOT_REPORTED", "N_CAUSE_SUM_MISMATCH",
            "CANCEL_CODE_A_CARRIER", "CANCEL_CODE_B_WEATHER", "CANCEL_CODE_C_NAS", "CANCEL_CODE_D_SECURITY",
            "MIN_CARRIER", "MIN_WEATHER", "MIN_NAS", "MIN_SECURITY", "MIN_LATE_AIRCRAFT",
            "SHARE_CARRIER", "SHARE_WEATHER", "SHARE_NAS", "SHARE_SECURITY", "SHARE_LATE_AIRCRAFT",
            "FLIGHTS_CARRIER", "FLIGHTS_WEATHER", "FLIGHTS_NAS", "FLIGHTS_SECURITY", "FLIGHTS_LATE_AIRCRAFT");

    public static class Combiner extends Reducer<Text, DelayCauseAccumulator, Text, DelayCauseAccumulator> {
        @Override
        protected void reduce(Text key, Iterable<DelayCauseAccumulator> values, Context context)
                throws IOException, InterruptedException {
            DelayCauseAccumulator m = new DelayCauseAccumulator();
            for (DelayCauseAccumulator v : values) m.add(v);
            context.write(key, m);
        }
    }

    public static class Finalizer extends Reducer<Text, DelayCauseAccumulator, Text, Text> {
        @Override
        protected void reduce(Text key, Iterable<DelayCauseAccumulator> values, Context context)
                throws IOException, InterruptedException {
            DelayCauseAccumulator a = new DelayCauseAccumulator();
            for (DelayCauseAccumulator v : values) a.add(v);
            context.write(key, new Text(format(a)));
        }
    }

    static String format(DelayCauseAccumulator a) {
        double meanArr = ratio(a.sumArrDelay, a.nOperated);
        double meanDep = ratio(a.sumDepDelay, a.nOperated);
        double total = a.totalCauseMinutes();
        StringBuilder sb = new StringBuilder();
        sb.append(String.format(Locale.US, "%d|%d|%d|%d|%.4f|%.4f|%d|%.4f|%.3f|%.3f|%.3f|%d|%d|%d",
                a.nTotal, a.nOperated, a.nCancelled, a.nDiverted,
                ratio(a.nCancelled, a.nTotal), ratio(a.nDiverted, a.nTotal),
                a.nDelayed15, ratio(a.nDelayed15, a.nOperated),
                meanArr, meanDep, meanDep - meanArr,
                a.nCauseReported, a.nUnreported, a.nMismatch));
        for (int i = 0; i < 4; i++) sb.append('|').append(a.cancelByCode[i]);
        for (int i = 0; i < 5; i++) sb.append(String.format(Locale.US, "|%.0f", a.causeMinutes[i]));
        for (int i = 0; i < 5; i++) sb.append(String.format(Locale.US, "|%.4f", ratio(a.causeMinutes[i], total)));
        for (int i = 0; i < 5; i++) sb.append('|').append(a.causeFlights[i]);
        return sb.toString();
    }

    private static double ratio(double num, double den) {
        return den == 0 ? 0.0 : num / den;
    }
}
