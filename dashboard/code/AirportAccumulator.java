package com.flightpulse.airport;

import org.apache.hadoop.io.Writable;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;

/**
 * Per-airport running aggregate. Associative/commutative under add(), so
 * this doubles as the Combiner's merge operation as well as the Reducer's.
 *
 * Denominators matter here (see AirportMetricsJob docs): totalDepartures/
 * totalArrivals count ALL flights touching this airport in that role,
 * regardless of status, so rates computed from the *DelayCount fields
 * (which only include operated flights with real delay data) are divided
 * by the right denominator, not accidentally diluted or inflated by
 * cancelled/diverted flights that have no delay value at all.
 */
public class AirportAccumulator implements Writable {

    public long totalDepartures;
    public long totalArrivals;

    public double depDelaySum;
    public double depDelaySumSq;
    public long depDelayCount;
    public long depDelay15PlusCount;

    public double arrDelaySum;
    public double arrDelaySumSq;
    public long arrDelayCount;
    public long arrDelay15PlusCount;

    public long cancelledAsOrigin;
    public long divertedAsOrigin;

    public static AirportAccumulator forOrigin(boolean operated, Double depDelay,
                                                boolean cancelled, boolean diverted) {
        AirportAccumulator a = new AirportAccumulator();
        a.totalDepartures = 1;
        if (operated && depDelay != null) {
            a.depDelaySum = depDelay;
            a.depDelaySumSq = depDelay * depDelay;
            a.depDelayCount = 1;
            a.depDelay15PlusCount = depDelay >= 15.0 ? 1 : 0;
        }
        a.cancelledAsOrigin = cancelled ? 1 : 0;
        a.divertedAsOrigin = diverted ? 1 : 0;
        return a;
    }

    public static AirportAccumulator forDest(boolean operated, Double arrDelay) {
        AirportAccumulator a = new AirportAccumulator();
        a.totalArrivals = 1;
        if (operated && arrDelay != null) {
            a.arrDelaySum = arrDelay;
            a.arrDelaySumSq = arrDelay * arrDelay;
            a.arrDelayCount = 1;
            a.arrDelay15PlusCount = arrDelay >= 15.0 ? 1 : 0;
        }
        return a;
    }

    public void add(AirportAccumulator o) {
        totalDepartures += o.totalDepartures;
        totalArrivals += o.totalArrivals;
        depDelaySum += o.depDelaySum;
        depDelaySumSq += o.depDelaySumSq;
        depDelayCount += o.depDelayCount;
        depDelay15PlusCount += o.depDelay15PlusCount;
        arrDelaySum += o.arrDelaySum;
        arrDelaySumSq += o.arrDelaySumSq;
        arrDelayCount += o.arrDelayCount;
        arrDelay15PlusCount += o.arrDelay15PlusCount;
        cancelledAsOrigin += o.cancelledAsOrigin;
        divertedAsOrigin += o.divertedAsOrigin;
    }

    public double meanDepDelay() {
        return depDelayCount == 0 ? 0.0 : depDelaySum / depDelayCount;
    }

    public double meanArrDelay() {
        return arrDelayCount == 0 ? 0.0 : arrDelaySum / arrDelayCount;
    }

    public double stdDevDepDelay() {
        if (depDelayCount == 0) return 0.0;
        double mean = meanDepDelay();
        double variance = (depDelaySumSq / depDelayCount) - (mean * mean);
        return Math.sqrt(Math.max(0.0, variance));
    }

    public double stdDevArrDelay() {
        if (arrDelayCount == 0) return 0.0;
        double mean = meanArrDelay();
        double variance = (arrDelaySumSq / arrDelayCount) - (mean * mean);
        return Math.sqrt(Math.max(0.0, variance));
    }

    public double depDelayRate() {
        return depDelayCount == 0 ? 0.0 : (double) depDelay15PlusCount / depDelayCount;
    }

    public double arrDelayRate() {
        return arrDelayCount == 0 ? 0.0 : (double) arrDelay15PlusCount / arrDelayCount;
    }

    public double cancellationRate() {
        return totalDepartures == 0 ? 0.0 : (double) cancelledAsOrigin / totalDepartures;
    }

    public double diversionRate() {
        return totalDepartures == 0 ? 0.0 : (double) divertedAsOrigin / totalDepartures;
    }

    @Override
    public void write(DataOutput out) throws IOException {
        out.writeLong(totalDepartures);
        out.writeLong(totalArrivals);
        out.writeDouble(depDelaySum);
        out.writeDouble(depDelaySumSq);
        out.writeLong(depDelayCount);
        out.writeLong(depDelay15PlusCount);
        out.writeDouble(arrDelaySum);
        out.writeDouble(arrDelaySumSq);
        out.writeLong(arrDelayCount);
        out.writeLong(arrDelay15PlusCount);
        out.writeLong(cancelledAsOrigin);
        out.writeLong(divertedAsOrigin);
    }

    @Override
    public void readFields(DataInput in) throws IOException {
        totalDepartures = in.readLong();
        totalArrivals = in.readLong();
        depDelaySum = in.readDouble();
        depDelaySumSq = in.readDouble();
        depDelayCount = in.readLong();
        depDelay15PlusCount = in.readLong();
        arrDelaySum = in.readDouble();
        arrDelaySumSq = in.readDouble();
        arrDelayCount = in.readLong();
        arrDelay15PlusCount = in.readLong();
        cancelledAsOrigin = in.readLong();
        divertedAsOrigin = in.readLong();
    }
}
