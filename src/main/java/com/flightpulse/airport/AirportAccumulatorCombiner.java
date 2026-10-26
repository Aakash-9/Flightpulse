package com.flightpulse.airport;

import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;

import java.io.IOException;

/**
 * Merges partial AirportAccumulators for the same airport before shuffle.
 * Safe as a combiner: add() is associative and commutative, and combining
 * never changes the final result, only how much gets shuffled.
 */
public class AirportAccumulatorCombiner extends Reducer<Text, AirportAccumulator, Text, AirportAccumulator> {

    @Override
    protected void reduce(Text key, Iterable<AirportAccumulator> values, Context context)
            throws IOException, InterruptedException {
        AirportAccumulator merged = new AirportAccumulator();
        for (AirportAccumulator v : values) {
            merged.add(v);
        }
        context.write(key, merged);
    }
}
