package com.flightpulse.rotation;

import org.apache.hadoop.io.WritableComparable;
import org.apache.hadoop.io.WritableUtils;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;

/**
 * Composite secondary-sort key: (tailNum, chronoMin). Natural ordering sorts
 * by tailNum first, then chronologically within a tail number - this IS the
 * secondary sort. TailNumPartitioner and TailGroupComparator both act on
 * tailNum only, so a reducer receives every leg for one aircraft, across the
 * entire 2020-2025 dataset, already in chronological order.
 */
public class TailChronoKey implements WritableComparable<TailChronoKey> {

    public String tailNum;
    public long chronoMin;

    public TailChronoKey() {
    }

    public TailChronoKey(String tailNum, long chronoMin) {
        this.tailNum = tailNum;
        this.chronoMin = chronoMin;
    }

    @Override
    public int compareTo(TailChronoKey o) {
        int c = this.tailNum.compareTo(o.tailNum);
        if (c != 0) {
            return c;
        }
        return Long.compare(this.chronoMin, o.chronoMin);
    }

    @Override
    public void write(DataOutput out) throws IOException {
        WritableUtils.writeString(out, tailNum);
        out.writeLong(chronoMin);
    }

    @Override
    public void readFields(DataInput in) throws IOException {
        tailNum = WritableUtils.readString(in);
        chronoMin = in.readLong();
    }

    @Override
    public int hashCode() {
        return tailNum.hashCode();
    }

    @Override
    public boolean equals(Object obj) {
        if (!(obj instanceof TailChronoKey other)) return false;
        return this.tailNum.equals(other.tailNum) && this.chronoMin == other.chronoMin;
    }
}
