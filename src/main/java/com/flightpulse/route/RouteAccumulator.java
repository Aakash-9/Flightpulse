package com.flightpulse.route;

import org.apache.hadoop.io.Writable;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;

/**
 * Per-route (ORIGIN-DEST pair) running aggregate. Associative/commutative
 * under add() - usable as both combiner and reducer merge op, same pattern
 * as AirportAccumulator.
 */
public class RouteAccumulator implements Writable {

    public long totalFlights;

    public double depDelaySum;
    public double depDelaySumSq;
    public long depDelayCount;
    public long depDelay15PlusCount;

    public double arrDelaySum;
    public double arrDelaySumSq;
    public long arrDelayCount;
    public long arrDelay15PlusCount;

    public long cancelledCount;
    public long divertedCount;

    public static RouteAccumulator forRecord(boolean operated, Double depDelay, Double arrDelay,
                                              boolean cancelled, boolean diverted) {
        RouteAccumulator r = new RouteAccumulator();
        r.totalFlights = 1;
        if (operated) {
            if (depDelay != null) {
                r.depDelaySum = depDelay;
                r.depDelaySumSq = depDelay * depDelay;
                r.depDelayCount = 1;
                r.depDelay15PlusCount = depDelay >= 15.0 ? 1 : 0;
            }
            if (arrDelay != null) {
                r.arrDelaySum = arrDelay;
                r.arrDelaySumSq = arrDelay * arrDelay;
                r.arrDelayCount = 1;
                r.arrDelay15PlusCount = arrDelay >= 15.0 ? 1 : 0;
            }
        }
        r.cancelledCount = cancelled ? 1 : 0;
        r.divertedCount = diverted ? 1 : 0;
        return r;
    }

    public void add(RouteAccumulator o) {
        totalFlights += o.totalFlights;
        depDelaySum += o.depDelaySum;
        depDelaySumSq += o.depDelaySumSq;
        depDelayCount += o.depDelayCount;
        depDelay15PlusCount += o.depDelay15PlusCount;
        arrDelaySum += o.arrDelaySum;
        arrDelaySumSq += o.arrDelaySumSq;
        arrDelayCount += o.arrDelayCount;
        arrDelay15PlusCount += o.arrDelay15PlusCount;
        cancelledCount += o.cancelledCount;
        divertedCount += o.divertedCount;
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
        return Math.sqrt(Math.max(0.0, (depDelaySumSq / depDelayCount) - mean * mean));
    }

    public double stdDevArrDelay() {
        if (arrDelayCount == 0) return 0.0;
        double mean = meanArrDelay();
        return Math.sqrt(Math.max(0.0, (arrDelaySumSq / arrDelayCount) - mean * mean));
    }

    public double depDelayRate() {
        return depDelayCount == 0 ? 0.0 : (double) depDelay15PlusCount / depDelayCount;
    }

    public double arrDelayRate() {
        return arrDelayCount == 0 ? 0.0 : (double) arrDelay15PlusCount / arrDelayCount;
    }

    public double cancellationRate() {
        return totalFlights == 0 ? 0.0 : (double) cancelledCount / totalFlights;
    }

    public double diversionRate() {
        return totalFlights == 0 ? 0.0 : (double) divertedCount / totalFlights;
    }

    @Override
    public void write(DataOutput out) throws IOException {
        out.writeLong(totalFlights);
        out.writeDouble(depDelaySum);
        out.writeDouble(depDelaySumSq);
        out.writeLong(depDelayCount);
        out.writeLong(depDelay15PlusCount);
        out.writeDouble(arrDelaySum);
        out.writeDouble(arrDelaySumSq);
        out.writeLong(arrDelayCount);
        out.writeLong(arrDelay15PlusCount);
        out.writeLong(cancelledCount);
        out.writeLong(divertedCount);
    }

    @Override
    public void readFields(DataInput in) throws IOException {
        totalFlights = in.readLong();
        depDelaySum = in.readDouble();
        depDelaySumSq = in.readDouble();
        depDelayCount = in.readLong();
        depDelay15PlusCount = in.readLong();
        arrDelaySum = in.readDouble();
        arrDelaySumSq = in.readDouble();
        arrDelayCount = in.readLong();
        arrDelay15PlusCount = in.readLong();
        cancelledCount = in.readLong();
        divertedCount = in.readLong();
    }
}
