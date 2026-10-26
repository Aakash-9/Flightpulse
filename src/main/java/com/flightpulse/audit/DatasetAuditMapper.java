package com.flightpulse.audit;

import com.flightpulse.util.CsvLineParser;
import com.flightpulse.util.FlightSchema;
import org.apache.hadoop.io.IntWritable;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;
import org.apache.hadoop.mapreduce.lib.input.FileSplit;

import java.io.IOException;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Job A - DatasetAuditJob mapper.
 *
 * Reads raw Bronze CSV lines, validates structure, and emits
 * (yearMonth -> 1) so the reducer can produce a per-month record count
 * (used for the source manifest / reconciliation against HDFS listings).
 * Data-quality findings are tracked via Hadoop Counters, not per-record
 * output, since this job's job is auditing, not transforming.
 */
public class DatasetAuditMapper extends Mapper<LongWritable, Text, Text, IntWritable> {

    private static final Pattern FILENAME_PATTERN = Pattern.compile("flights_(\\d{4})_(\\d{2})\\.csv$");
    private static final IntWritable ONE = new IntWritable(1);

    private Text yearMonthKey;

    @Override
    protected void setup(Context context) {
        String path = ((FileSplit) context.getInputSplit()).getPath().getName();
        Matcher m = FILENAME_PATTERN.matcher(path);
        String yearMonth = m.find() ? m.group(1) + "-" + m.group(2) : "UNKNOWN";
        yearMonthKey = new Text(yearMonth);
    }

    @Override
    protected void map(LongWritable key, Text value, Context context) throws IOException, InterruptedException {
        String line = value.toString();
        if (line.isEmpty()) {
            return;
        }

        // The header line is always at byte offset 0 of its file - each monthly
        // file here is a single InputSplit (well under the 128MB block size),
        // so this reliably identifies it without string-matching every line.
        if (key.get() == 0) {
            context.getCounter(AuditCounters.HEADER_ROWS).increment(1);
            if (!line.equals(FlightSchema.HEADER_LINE)) {
                context.getCounter(AuditCounters.SCHEMA_MISMATCH).increment(1);
            }
            return;
        }

        context.getCounter(AuditCounters.TOTAL_LINES).increment(1);

        String[] fields = CsvLineParser.parse(line);
        if (fields == null) {
            context.getCounter(AuditCounters.MALFORMED_ROWS).increment(1);
            return;
        }
        if (fields.length != FlightSchema.COLUMN_COUNT) {
            context.getCounter(AuditCounters.WRONG_COLUMN_COUNT).increment(1);
            return;
        }

        context.getCounter(AuditCounters.VALID_RECORDS).increment(1);

        if (isBlank(fields[FlightSchema.TAIL_NUM])) {
            context.getCounter(AuditCounters.MISSING_TAIL_NUM).increment(1);
        }

        boolean cancelled = "1.00".equals(fields[FlightSchema.CANCELLED]);
        boolean diverted = "1.00".equals(fields[FlightSchema.DIVERTED]);
        if (cancelled) {
            context.getCounter(AuditCounters.CANCELLED_RECORDS).increment(1);
        }
        if (diverted) {
            context.getCounter(AuditCounters.DIVERTED_RECORDS).increment(1);
        }

        // Cancelled/diverted flights legitimately have blank actual-time fields;
        // only flag it as unexpected when neither applies.
        if (!cancelled && !diverted) {
            if (isBlank(fields[FlightSchema.DEP_TIME])) {
                context.getCounter(AuditCounters.MISSING_DEP_TIME_UNEXPECTED).increment(1);
            }
            if (isBlank(fields[FlightSchema.ARR_TIME])) {
                context.getCounter(AuditCounters.MISSING_ARR_TIME_UNEXPECTED).increment(1);
            }
        }

        context.write(yearMonthKey, ONE);
    }

    private static boolean isBlank(String s) {
        return s == null || s.isEmpty();
    }
}
