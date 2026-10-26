package com.flightpulse.route;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.FSDataOutputStream;
import org.apache.hadoop.fs.FileSystem;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
import org.apache.hadoop.mapreduce.lib.output.FileOutputFormat;
import org.apache.hadoop.util.Tool;
import org.apache.hadoop.util.ToolRunner;

import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.time.Duration;
import java.time.Instant;
import java.time.format.DateTimeFormatter;

/**
 * Route x airline reliability, overall and by time-of-day band (feeds the
 * "plan my trip" view). Reuses RouteAccumulator / combiner / reducer: the
 * aggregation is identical, only the key differs.
 *
 * Usage: hadoop jar flightpulse.jar com.flightpulse.route.RouteCarrierMetricsJob <silver input> <output>
 */
public class RouteCarrierMetricsJob implements Tool {

    private Configuration conf;

    @Override
    public void setConf(Configuration conf) {
        this.conf = conf;
    }

    @Override
    public Configuration getConf() {
        return conf;
    }

    @Override
    public int run(String[] args) throws Exception {
        if (args.length != 2) {
            System.err.println("Usage: RouteCarrierMetricsJob <silver input path> <output path>");
            return 2;
        }
        String inputPath = args[0];
        String outputPath = args[1];

        FileSystem fs = FileSystem.get(getConf());
        if (fs.exists(new Path(outputPath))) {
            System.err.println("Output path already exists, refusing to overwrite: " + outputPath);
            return 1;
        }

        Job job = Job.getInstance(getConf(), "FlightPulse - RouteCarrierMetricsJob");
        job.setJarByClass(RouteCarrierMetricsJob.class);
        job.getConfiguration().setBoolean(FileInputFormat.INPUT_DIR_RECURSIVE, true);

        job.setMapperClass(RouteCarrierMetricsMapper.class);
        job.setCombinerClass(RouteAccumulatorCombiner.class);
        job.setReducerClass(RouteMetricsReducer.class);

        job.setMapOutputKeyClass(Text.class);
        job.setMapOutputValueClass(RouteAccumulator.class);
        job.setOutputKeyClass(Text.class);
        job.setOutputValueClass(Text.class);

        FileInputFormat.addInputPath(job, new Path(inputPath));
        FileOutputFormat.setOutputPath(job, new Path(outputPath));

        Instant start = Instant.now();
        boolean success = job.waitForCompletion(true);
        Instant end = Instant.now();

        if (success) writeSchemaDoc(fs, outputPath);
        writeReport(inputPath, outputPath, start, end, success, job);
        return success ? 0 : 1;
    }

    private void writeSchemaDoc(FileSystem fs, String outputPath) throws IOException {
        try (FSDataOutputStream out = fs.create(new Path(outputPath, "_SCHEMA.txt"))) {
            StringBuilder sb = new StringBuilder();
            sb.append("FlightPulse RouteCarrierMetricsJob output (pipe-delimited)\n");
            sb.append("Keys: RC|ORIGIN-DEST|CARRIER   and   RCB|ORIGIN-DEST|CARRIER|BAND\n");
            sb.append("Value: ").append(RouteMetricsJob.HEADER.substring(RouteMetricsJob.HEADER.indexOf('|') + 1)).append('\n');
            sb.append("\nNotes:\n");
            sb.append("- BAND by scheduled local departure hour: MORNING 05-11, AFTERNOON 12-16, EVENING 17-21, NIGHT 22-04.\n");
            sb.append("- RCB rows cover flights that actually flew with a derivable scheduled time. Cancelled/diverted flights\n");
            sb.append("  have no times, so CANCELLATION_RATE/DIVERSION_RATE in RCB rows are NOT meaningful; use RC rows.\n");
            sb.append("- LOW_SAMPLE_FLAG=1 when TOTAL_FLIGHTS < ").append(RouteMetricsReducer.MIN_SAMPLE_SIZE)
                    .append(" (row kept, but do not rank on it).\n");
            out.write(sb.toString().getBytes(StandardCharsets.UTF_8));
        }
    }

    private void writeReport(String inputPath, String outputPath, Instant start, Instant end,
                              boolean success, Job job) throws IOException {
        StringBuilder sb = new StringBuilder();
        sb.append("FlightPulse RouteCarrierMetricsJob run report\n");
        sb.append("================================================\n");
        sb.append("Input path:   ").append(inputPath).append('\n');
        sb.append("Output path:  ").append(outputPath).append('\n');
        sb.append("Started:      ").append(DateTimeFormatter.ISO_INSTANT.format(start)).append('\n');
        sb.append("Finished:     ").append(DateTimeFormatter.ISO_INSTANT.format(end)).append('\n');
        sb.append("Duration:     ").append(Duration.between(start, end).toSeconds()).append("s\n");
        sb.append("Success:      ").append(success).append('\n');
        sb.append("Map output records:    ").append(counter(job, "MAP_OUTPUT_RECORDS")).append('\n');
        sb.append("Combine out records:   ").append(counter(job, "COMBINE_OUTPUT_RECORDS")).append('\n');
        sb.append("Reduce output rows:    ").append(counter(job, "REDUCE_OUTPUT_RECORDS")).append('\n');

        System.out.println();
        System.out.println(sb);

        Files.createDirectories(Paths.get(System.getProperty("user.home"), "flightpulse", "reports"));
        String reportPath = System.getProperty("user.home") + "/flightpulse/reports/route_carrier_" + start.toEpochMilli() + ".txt";
        try (PrintWriter pw = new PrintWriter(new FileWriter(reportPath))) {
            pw.print(sb);
        }
        System.out.println("Report written to: " + reportPath);
    }

    private long counter(Job job, String name) {
        try {
            return job.getCounters().findCounter("org.apache.hadoop.mapreduce.TaskCounter", name).getValue();
        } catch (Exception e) {
            return -1;
        }
    }

    public static void main(String[] args) throws Exception {
        System.exit(ToolRunner.run(new Configuration(), new RouteCarrierMetricsJob(), args));
    }
}
