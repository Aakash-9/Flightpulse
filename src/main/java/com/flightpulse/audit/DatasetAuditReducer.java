package com.flightpulse.audit;

import org.apache.hadoop.io.IntWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;

import java.io.IOException;

/**
 * Sums per-month record counts. Also used as the Combiner (sum is
 * associative/commutative), which meaningfully cuts shuffle volume since
 * every valid record otherwise emits a (yearMonth, 1) pair.
 */
public class DatasetAuditReducer extends Reducer<Text, IntWritable, Text, IntWritable> {

    @Override
    protected void reduce(Text key, Iterable<IntWritable> values, Context context)
            throws IOException, InterruptedException {
        int sum = 0;
        for (IntWritable v : values) {
            sum += v.get();
        }
        context.write(key, new IntWritable(sum));
    }
}
