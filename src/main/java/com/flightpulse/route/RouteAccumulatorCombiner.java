package com.flightpulse.route;

import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;

import java.io.IOException;

public class RouteAccumulatorCombiner extends Reducer<Text, RouteAccumulator, Text, RouteAccumulator> {

    @Override
    protected void reduce(Text key, Iterable<RouteAccumulator> values, Context context)
            throws IOException, InterruptedException {
        RouteAccumulator merged = new RouteAccumulator();
        for (RouteAccumulator v : values) {
            merged.add(v);
        }
        context.write(key, merged);
    }
}
