package com.flightpulse.rotation;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class TailChronoKeyTest {

    @Test
    void sortsByTailNumFirstThenChronologically() {
        List<TailChronoKey> keys = new ArrayList<>(List.of(
                new TailChronoKey("N200AA", 500),
                new TailChronoKey("N100AA", 300),
                new TailChronoKey("N100AA", 100),
                new TailChronoKey("N100AA", 200)
        ));
        Collections.sort(keys);

        assertEquals("N100AA", keys.get(0).tailNum);
        assertEquals(100, keys.get(0).chronoMin);
        assertEquals("N100AA", keys.get(1).tailNum);
        assertEquals(200, keys.get(1).chronoMin);
        assertEquals("N100AA", keys.get(2).tailNum);
        assertEquals(300, keys.get(2).chronoMin);
        assertEquals("N200AA", keys.get(3).tailNum); // different tail sorts after, regardless of its smaller chronoMin
    }

    @Test
    void tiedChronoMinWithinSameTailIsStableUnderCompareTo() {
        TailChronoKey a = new TailChronoKey("N100AA", 500);
        TailChronoKey b = new TailChronoKey("N100AA", 500);
        assertEquals(0, a.compareTo(b));
        assertEquals(a, b);
    }

    @Test
    void groupComparatorIgnoresChronoMinAndGroupsByTailOnly() {
        TailGroupComparatorAccessor cmp = new TailGroupComparatorAccessor();
        TailChronoKey a = new TailChronoKey("N100AA", 100);
        TailChronoKey b = new TailChronoKey("N100AA", 99999);
        TailChronoKey c = new TailChronoKey("N200AA", 100);

        assertEquals(0, cmp.compare(a, b), "same tail, different chrono -> same group");
        assertNotEquals(0, cmp.compare(a, c), "different tail -> different group");
    }

    @Test
    void partitionerSendsSameTailToSamePartitionRegardlessOfChrono() {
        TailNumPartitioner p = new TailNumPartitioner();
        int numPartitions = 7;
        TailChronoKey a = new TailChronoKey("N100AA", 1);
        TailChronoKey b = new TailChronoKey("N100AA", 999999);
        assertEquals(p.getPartition(a, null, numPartitions), p.getPartition(b, null, numPartitions));
    }

    /** Exposes the protected compare() method for the test above. */
    private static class TailGroupComparatorAccessor extends TailGroupComparator {
        public int compare(TailChronoKey a, TailChronoKey b) {
            return super.compare(a, b);
        }
    }
}
