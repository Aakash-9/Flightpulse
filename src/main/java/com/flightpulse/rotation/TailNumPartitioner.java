package com.flightpulse.rotation;

import org.apache.hadoop.mapreduce.Partitioner;

/**
 * Partitions on tailNum ONLY (ignoring chronoMin), so every leg for a given
 * aircraft is guaranteed to land in the same reducer regardless of how many
 * reducers are configured.
 */
public class TailNumPartitioner extends Partitioner<TailChronoKey, FlightLeg> {

    @Override
    public int getPartition(TailChronoKey key, FlightLeg value, int numPartitions) {
        return (key.tailNum.hashCode() & Integer.MAX_VALUE) % numPartitions;
    }
}
