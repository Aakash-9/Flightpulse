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
 * Job D - per-route (ORIGIN-DEST pair) disruption metrics (RQ1).
 *
 * Usage: hadoop jar flightpulse.jar com.flightpulse.route.RouteMetricsJob <silver input> <output>
 */
public class RouteMetricsJob implements Tool {

    public static final String HEADER = String.join("|",
            "ROUTE",
            "TOTAL_FLIGHTS", "DEP_DELAY_SAMPLE_N", "ARR_DELAY_SAMPLE_N",
            "DEP_DELAY_RATE", "ARR_DELAY_RATE",
            "MEAN_DEP_DELAY_MIN", "MEAN_ARR_DELAY_MIN",
            "STDDEV_DEP_DELAY_MIN", "STDDEV_ARR_DELAY_MIN",
            "CANCELLATION_RATE", "DIVERSION_RATE",
            "CANCELLED_COUNT", "DIVERTED_COUNT",
            "LOW_SAMPLE_FLAG");

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
            System.err.println("Usage: RouteMetricsJob <silver input path> <output path>");
            return 2;
        }
        String inputPath = args[0];
        String outputPath = args[1];

        FileSystem fs = FileSystem.get(getConf());
        if (fs.exists(new Path(outputPath))) {
            System.err.println("Output path already exists, refusing to overwrite: " + outputPath);
            return 1;
        }

        Job job = Job.getInstance(getConf(), "FlightPulse - RouteMetricsJob");
        job.setJarByClass(RouteMetricsJob.class);
        job.getConfiguration().setBoolean(FileInputFormat.INPUT_DIR_RECURSIVE, true);

        job.setMapperClass(RouteMetricsMapper.class);
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

        if (success) {
            writeSchemaDoc(fs, outputPath);
        }
        writeReport(inputPath, outputPath, start, end, success, job);

        return success ? 0 : 1;
    }

    private void writeSchemaDoc(FileSystem fs, String outputPath) throws IOException {
        try (FSDataOutputStream out = fs.create(new Path(outputPath, "_SCHEMA.txt"))) {
            StringBuilder sb = new StringBuilder();
            sb.append("FlightPulse RouteMetricsJob output (pipe-delimited)\n");
            sb.append("Key: ROUTE (\"ORIGIN-DEST\", directional)   Value: ").append(HEADER).append('\n');
            sb.append("\nNotes:\n");
            sb.append("- Directional: LAX-JFK and JFK-LAX are separate routes.\n");
            sb.append("- LOW_SAMPLE_FLAG=1 means TOTAL_FLIGHTS < ").append(RouteMetricsReducer.MIN_SAMPLE_SIZE)
                    .append(" across all of 2020-2025 combined. Row is still included (never silently dropped), ")
                    .append("but should be excluded from any \"most disrupted route\" ranking.\n");
            sb.append("- Year-over-year breakdown is NOT computed by this job - see TemporalMetricsJob.\n");
            out.write(sb.toString().getBytes(StandardCharsets.UTF_8));
        }
    }

    private void writeReport(String inputPath, String outputPath, Instant start, Instant end,
                              boolean success, Job job) throws IOException {
        StringBuilder sb = new StringBuilder();
        sb.append("FlightPulse RouteMetricsJob run report\n");
        sb.append("========================================\n");
        sb.append("Input path:   ").append(inputPath).append('\n');
        sb.append("Output path:  ").append(outputPath).append('\n');
        sb.append("Started:      ").append(DateTimeFormatter.ISO_INSTANT.format(start)).append('\n');
        sb.append("Finished:     ").append(DateTimeFormatter.ISO_INSTANT.format(end)).append('\n');
        sb.append("Duration:     ").append(Duration.between(start, end).toSeconds()).append("s\n");
        sb.append("Success:      ").append(success).append('\n');
        sb.append("Reduce output records (distinct routes): ")
                .append(getCounterSafe(job, "org.apache.hadoop.mapreduce.TaskCounter", "REDUCE_OUTPUT_RECORDS"))
                .append('\n');
        sb.append("Combiner input/output records: ")
                .append(getCounterSafe(job, "org.apache.hadoop.mapreduce.TaskCounter", "COMBINE_INPUT_RECORDS"))
                .append(" / ")
                .append(getCounterSafe(job, "org.apache.hadoop.mapreduce.TaskCounter", "COMBINE_OUTPUT_RECORDS"))
                .append('\n');

        System.out.println();
        System.out.println(sb);

        Files.createDirectories(Paths.get(System.getProperty("user.home"), "flightpulse", "reports"));
        String reportPath = System.getProperty("user.home") + "/flightpulse/reports/route_metrics_" + start.toEpochMilli() + ".txt";
        try (PrintWriter pw = new PrintWriter(new FileWriter(reportPath))) {
            pw.print(sb);
        }
        System.out.println("Report written to: " + reportPath);
    }

    private long getCounterSafe(Job job, String group, String name) {
        try {
            return job.getCounters().findCounter(group, name).getValue();
        } catch (Exception e) {
            return -1;
        }
    }

    public static void main(String[] args) throws Exception {
        int exitCode = ToolRunner.run(new Configuration(), new RouteMetricsJob(), args);
        System.exit(exitCode);
    }
}
