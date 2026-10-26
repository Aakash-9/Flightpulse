package com.flightpulse.normalize;

import com.flightpulse.util.CsvLineParser;
import com.flightpulse.util.FlightSchema;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.NullWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;
import org.apache.hadoop.mapreduce.lib.output.MultipleOutputs;

import java.io.IOException;

/**
 * Job B - NormalizeFlightsJob mapper.
 *
 * Map-only (see driver: numReduceTasks=0) since normalization is a per-record
 * transform with no aggregation. Every row that parses with the right column
 * count is written to Silver (classified VALID/CANCELLED/DIVERTED/
 * MISSING_TAIL); every row that doesn't is preserved verbatim in quarantine
 * rather than dropped.
 */
public class NormalizeFlightsMapper extends Mapper<LongWritable, Text, NullWritable, Text> {

    private MultipleOutputs<NullWritable, Text> multipleOutputs;
    private static final NullWritable NULL_KEY = NullWritable.get();

    @Override
    protected void setup(Context context) {
        multipleOutputs = new MultipleOutputs<>(context);
    }

    @Override
    protected void map(LongWritable key, Text value, Context context) throws IOException, InterruptedException {
        String line = value.toString();
        if (line.isEmpty()) {
            return;
        }
        if (key.get() == 0) {
            context.getCounter(NormalizeCounters.HEADER_ROWS).increment(1);
            return;
        }

        context.getCounter(NormalizeCounters.TOTAL_LINES).increment(1);

        String[] fields = CsvLineParser.parse(line);
        if (fields == null || fields.length != FlightSchema.COLUMN_COUNT) {
            String reason = fields == null ? "CSV parse failure" : "wrong column count: " + fields.length;
            context.getCounter(NormalizeCounters.INVALID_QUARANTINED).increment(1);
            multipleOutputs.write("quarantine", NULL_KEY, new Text(line + " || REASON=" + reason));
            return;
        }

        NormalizedFlight normalized = NormalizedFlight.classify(fields);
        switch (normalized.status) {
            case VALID -> context.getCounter(NormalizeCounters.VALID).increment(1);
            case CANCELLED -> context.getCounter(NormalizeCounters.CANCELLED).increment(1);
            case DIVERTED -> context.getCounter(NormalizeCounters.DIVERTED).increment(1);
            case MISSING_TAIL -> context.getCounter(NormalizeCounters.MISSING_TAIL).increment(1);
            case INVALID -> {
                context.getCounter(NormalizeCounters.INVALID_QUARANTINED).increment(1);
                multipleOutputs.write("quarantine", NULL_KEY, new Text(normalized.toSilverLine()));
                return;
            }
        }
        multipleOutputs.write("silver", NULL_KEY, new Text(normalized.toSilverLine()));
    }

    @Override
    protected void cleanup(Context context) throws IOException, InterruptedException {
        multipleOutputs.close();
    }
}
