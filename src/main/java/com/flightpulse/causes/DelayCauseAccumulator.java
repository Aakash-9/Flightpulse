package com.flightpulse.causes;

import org.apache.hadoop.io.Writable;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;

/**
 * Additive aggregate for delay-cause analysis (and carrier/airport reliability
 * splits). add() is associative/commutative: used for in-mapper combining,
 * the Combiner and the final Reducer.
 *
 * BTS semantics this class respects: the five cause fields (carrier, weather,
 * NAS, security, late-arriving aircraft) are only populated when a flight
 * arrives 15+ minutes late, in minutes, and they are what the carrier
 * reported, not an independent diagnosis. Blank is therefore "not reported",
 * never zero.
 */
public class DelayCauseAccumulator implements Writable {

    public static final String[] CAUSES = {"CARRIER", "WEATHER", "NAS", "SECURITY", "LATE_AIRCRAFT"};
    public static final double LATE_THRESHOLD_MIN = 15.0;
    public static final double RECONCILE_TOLERANCE_MIN = 1.0;

    public long nTotal;
    public long nCancelled;
    public long nDiverted;
    public long[] cancelByCode = new long[4];   // A carrier, B weather, C NAS, D security

    public long nOperated;
    public double sumDepDelay;
    public double sumArrDelay;
    public long nDelayed15;
    public long nCauseReported;
    public long nUnreported;
    public long nMismatch;
    public double[] causeMinutes = new double[5];
    public long[] causeFlights = new long[5];

    /**
     * @param causes five entries in CAUSES order; null entry = blank in source
     */
    public void addFlight(boolean operated, boolean cancelled, boolean diverted, String cancelCode,
                          Double depDelay, Double arrDelay, Double[] causes) {
        nTotal++;
        if (cancelled) {
            nCancelled++;
            int idx = "ABCD".indexOf(cancelCode == null || cancelCode.isEmpty() ? '?' : cancelCode.charAt(0));
            if (idx >= 0) cancelByCode[idx]++;
        }
        if (diverted) nDiverted++;
        if (!operated || depDelay == null || arrDelay == null) return;

        nOperated++;
        sumDepDelay += depDelay;
        sumArrDelay += arrDelay;
        if (arrDelay < LATE_THRESHOLD_MIN) return;

        nDelayed15++;
        double sum = 0;
        boolean any = false;
        for (int i = 0; i < 5; i++) {
            if (causes[i] != null) {
                any = true;
                sum += causes[i];
                causeMinutes[i] += causes[i];
                if (causes[i] > 0) causeFlights[i]++;
            }
        }
        if (!any) {
            nUnreported++;
            return;
        }
        nCauseReported++;
        if (Math.abs(sum - arrDelay) > RECONCILE_TOLERANCE_MIN) nMismatch++;
    }

    public void add(DelayCauseAccumulator o) {
        nTotal += o.nTotal;
        nCancelled += o.nCancelled;
        nDiverted += o.nDiverted;
        nOperated += o.nOperated;
        sumDepDelay += o.sumDepDelay;
        sumArrDelay += o.sumArrDelay;
        nDelayed15 += o.nDelayed15;
        nCauseReported += o.nCauseReported;
        nUnreported += o.nUnreported;
        nMismatch += o.nMismatch;
        for (int i = 0; i < 4; i++) cancelByCode[i] += o.cancelByCode[i];
        for (int i = 0; i < 5; i++) {
            causeMinutes[i] += o.causeMinutes[i];
            causeFlights[i] += o.causeFlights[i];
        }
    }

    public double totalCauseMinutes() {
        double t = 0;
        for (double m : causeMinutes) t += m;
        return t;
    }

    @Override
    public void write(DataOutput out) throws IOException {
        out.writeLong(nTotal);
        out.writeLong(nCancelled);
        out.writeLong(nDiverted);
        out.writeLong(nOperated);
        out.writeDouble(sumDepDelay);
        out.writeDouble(sumArrDelay);
        out.writeLong(nDelayed15);
        out.writeLong(nCauseReported);
        out.writeLong(nUnreported);
        out.writeLong(nMismatch);
        for (int i = 0; i < 4; i++) out.writeLong(cancelByCode[i]);
        for (int i = 0; i < 5; i++) {
            out.writeDouble(causeMinutes[i]);
            out.writeLong(causeFlights[i]);
        }
    }

    @Override
    public void readFields(DataInput in) throws IOException {
        nTotal = in.readLong();
        nCancelled = in.readLong();
        nDiverted = in.readLong();
        nOperated = in.readLong();
        sumDepDelay = in.readDouble();
        sumArrDelay = in.readDouble();
        nDelayed15 = in.readLong();
        nCauseReported = in.readLong();
        nUnreported = in.readLong();
        nMismatch = in.readLong();
        for (int i = 0; i < 4; i++) cancelByCode[i] = in.readLong();
        for (int i = 0; i < 5; i++) {
            causeMinutes[i] = in.readDouble();
            causeFlights[i] = in.readLong();
        }
    }
}
