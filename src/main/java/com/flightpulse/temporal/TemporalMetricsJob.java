package com.flightpulse.temporal;

import com.flightpulse.route.RouteAccumulator;
import com.flightpulse.route.RouteAccumulatorCombiner;
import com.flightpulse.route.RouteMetricsReducer;
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
 * Job E - temporal disruption metrics (RQ3): year, year-month, weekday, and
 * scheduled-departure-hour buckets.
 *
 * Usage: hadoop jar flightpulse.jar com.flightpulse.temporal.TemporalMetricsJob <silver input> <output>
 */
public class TemporalMetricsJob implements Tool {

    public static final String HEADER = String.join("|",
            "DIMENSION_KEY",
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
            System.err.println("Usage: TemporalMetricsJob <silver input path> <output path>");
            return 2;
        }
        String inputPath = args[0];
        String outputPath = args[1];

        FileSystem fs = FileSystem.get(getConf());
        if (fs.exists(new Path(outputPath))) {
            System.err.println("Output path already exists, refusing to overwrite: " + outputPath);
            return 1;
        }

        Job job = Job.getInstance(getConf(), "FlightPulse - TemporalMetricsJob");
        job.setJarByClass(TemporalMetricsJob.class);
        job.getConfiguration().setBoolean(FileInputFormat.INPUT_DIR_RECURSIVE, true);

        job.setMapperClass(TemporalMetricsMapper.class);
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
            sb.append("FlightPulse TemporalMetricsJob output (pipe-delimited)\n");
            sb.append("Key: DIMENSION_KEY, one of:\n");
            sb.append("  YEAR|<yyyy>\n");
            sb.append("  MONTH|<yyyy-MM>\n");
            sb.append("  WEEKDAY|<1-7>-<MONDAY..SUNDAY>  (ISO-8601: 1=Monday)\n");
            sb.append("  HOUR|<00-23>  (scheduled departure hour, DERIVED field - see note below)\n");
            sb.append("  WEEKDAYHOUR|<1-7>-<DAY>|<00-23>  (heatmap cell: weekday x scheduled departure hour; 168 cells)\n");
            sb.append("Value: ").append(HEADER).append('\n');
            sb.append("\nNotes:\n");
            sb.append("- Every record contributes to YEAR, MONTH and WEEKDAY. HOUR is only populated when ");
            sb.append("CRS_DEP_MIN was derivable (operated flights with valid actual-time+delay); its sample ");
            sb.append("size is therefore smaller and not directly comparable to the other three dimensions.\n");
            sb.append("- LOW_SAMPLE_FLAG=1 means TOTAL_FLIGHTS < ").append(RouteMetricsReducer.MIN_SAMPLE_SIZE).append(".\n");
            sb.append("- No anomaly detection is performed by this job - it reports counts/rates only. Any ");
            sb.append("\"anomaly\" claim belongs in analysis on top of this output, with its threshold and ");
            sb.append("baseline stated explicitly, not invented here.\n");
            out.write(sb.toString().getBytes(StandardCharsets.UTF_8));
        }
    }

    private void writeReport(String inputPath, String outputPath, Instant start, Instant end,
                              boolean success, Job job) throws IOException {
        StringBuilder sb = new StringBuilder();
        sb.append("FlightPulse TemporalMetricsJob run report\n");
        sb.append("===========================================\n");
        sb.append("Input path:   ").append(inputPath).append('\n');
        sb.append("Output path:  ").append(outputPath).append('\n');
        sb.append("Started:      ").append(DateTimeFormatter.ISO_INSTANT.format(start)).append('\n');
        sb.append("Finished:     ").append(DateTimeFormatter.ISO_INSTANT.format(end)).append('\n');
        sb.append("Duration:     ").append(Duration.between(start, end).toSeconds()).append("s\n");
        sb.append("Success:      ").append(success).append('\n');
        sb.append("Reduce output records (distinct time buckets): ")
                .append(getCounterSafe(job, "org.apache.hadoop.mapreduce.TaskCounter", "REDUCE_OUTPUT_RECORDS"))
                .append('\n');

        System.out.println();
        System.out.println(sb);

        Files.createDirectories(Paths.get(System.getProperty("user.home"), "flightpulse", "reports"));
        String reportPath = System.getProperty("user.home") + "/flightpulse/reports/temporal_metrics_" + start.toEpochMilli() + ".txt";
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
        int exitCode = ToolRunner.run(new Configuration(), new TemporalMetricsJob(), args);
        System.exit(exitCode);
    }
}
