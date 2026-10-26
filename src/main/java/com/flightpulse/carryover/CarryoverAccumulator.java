package com.flightpulse.carryover;

import org.apache.hadoop.io.Writable;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;

/**
 * Additive aggregate over candidate rotation links. add() is associative and
 * commutative, so it serves as in-mapper combiner, Combiner and Reducer merge.
 */
public class CarryoverAccumulator implements Writable {

    public long n;
    public long nExposed;            // links with PotentialExposure > 0
    public double sumArrDelayAPos;   // sum of max(0, arrDelay(A))
    public double sumExposure;
    public double sumCarryover;
    public double sumDepDelayBPos;   // sum of max(0, depDelay(B))
    public long nALate15;            // A arrived >= 15 min late
    public long nBLate15;            // B departed >= 15 min late
    public long nBLate15GivenALate15;
    public long nBLate15GivenANotLate15;

    public void addLink(double arrDelayA, double depDelayB, double exposure, double carryover) {
        n++;
        if (exposure > 0) nExposed++;
        sumArrDelayAPos += Math.max(0.0, arrDelayA);
        sumExposure += exposure;
        sumCarryover += carryover;
        sumDepDelayBPos += Math.max(0.0, depDelayB);
        boolean aLate = arrDelayA >= 15.0;
        boolean bLate = depDelayB >= 15.0;
        if (aLate) nALate15++;
        if (bLate) nBLate15++;
        if (aLate && bLate) nBLate15GivenALate15++;
        if (!aLate && bLate) nBLate15GivenANotLate15++;
    }

    public void add(CarryoverAccumulator o) {
        n += o.n;
        nExposed += o.nExposed;
        sumArrDelayAPos += o.sumArrDelayAPos;
        sumExposure += o.sumExposure;
        sumCarryover += o.sumCarryover;
        sumDepDelayBPos += o.sumDepDelayBPos;
        nALate15 += o.nALate15;
        nBLate15 += o.nBLate15;
        nBLate15GivenALate15 += o.nBLate15GivenALate15;
        nBLate15GivenANotLate15 += o.nBLate15GivenANotLate15;
    }

    @Override
    public void write(DataOutput out) throws IOException {
        out.writeLong(n);
        out.writeLong(nExposed);
        out.writeDouble(sumArrDelayAPos);
        out.writeDouble(sumExposure);
        out.writeDouble(sumCarryover);
        out.writeDouble(sumDepDelayBPos);
        out.writeLong(nALate15);
        out.writeLong(nBLate15);
        out.writeLong(nBLate15GivenALate15);
        out.writeLong(nBLate15GivenANotLate15);
    }

    @Override
    public void readFields(DataInput in) throws IOException {
        n = in.readLong();
        nExposed = in.readLong();
        sumArrDelayAPos = in.readDouble();
        sumExposure = in.readDouble();
        sumCarryover = in.readDouble();
        sumDepDelayBPos = in.readDouble();
        nALate15 = in.readLong();
        nBLate15 = in.readLong();
        nBLate15GivenALate15 = in.readLong();
        nBLate15GivenANotLate15 = in.readLong();
    }
}
