package com.flightpulse.rotation;

import org.apache.hadoop.io.WritableComparable;
import org.apache.hadoop.io.WritableComparator;

/**
 * Groups reduce() calls by tailNum only, NOT the full (tailNum, chronoMin)
 * key. Without this, every distinct chronoMin would start a new reduce()
 * call (one leg at a time) instead of handing the reducer the aircraft's
 * whole chronologically-sorted history in a single call - this comparator
 * is what makes it a secondary sort rather than just a sort.
 */
public class TailGroupComparator extends WritableComparator {

    protected TailGroupComparator() {
        super(TailChronoKey.class, true);
    }

    @Override
    public int compare(WritableComparable a, WritableComparable b) {
        TailChronoKey k1 = (TailChronoKey) a;
        TailChronoKey k2 = (TailChronoKey) b;
        return k1.tailNum.compareTo(k2.tailNum);
    }
}
