package com.flightpulse.causes;

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
 * Job F - source-reported delay causes (RQ3), plus carrier/airport reliability
 * and cancellation-code splits that share the same pass over Silver.
 *
 * Usage: hadoop jar flightpulse.jar com.flightpulse.causes.DelayCauseMetricsJob <silver input> <output>
 */
public class DelayCauseMetricsJob implements Tool {

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
            System.err.println("Usage: DelayCauseMetricsJob <silver input path> <output path>");
            return 2;
        }
        String inputPath = args[0];
        String outputPath = args[1];

        FileSystem fs = FileSystem.get(getConf());
        if (fs.exists(new Path(outputPath))) {
            System.err.println("Output path already exists, refusing to overwrite: " + outputPath);
            return 1;
        }

        Job job = Job.getInstance(getConf(), "FlightPulse - DelayCauseMetricsJob");
        job.setJarByClass(DelayCauseMetricsJob.class);
        job.getConfiguration().setBoolean(FileInputFormat.INPUT_DIR_RECURSIVE, true);

        job.setMapperClass(DelayCauseMetricsMapper.class);
        job.setCombinerClass(DelayCauseReducers.Combiner.class);
        job.setReducerClass(DelayCauseReducers.Finalizer.class);
        job.setNumReduceTasks(1);

        job.setMapOutputKeyClass(Text.class);
        job.setMapOutputValueClass(DelayCauseAccumulator.class);
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
            sb.append("FlightPulse DelayCauseMetricsJob output (pipe-delimited)\n");
            sb.append("Row: ").append(DelayCauseReducers.HEADER).append('\n');
            sb.append("Dimensions: ALL, YEAR|yyyy, MONTHOFYEAR|01-12, CARRIER|<code>, ORIGIN|<airport> (flights leaving it),\n");
            sb.append("            DEST|<airport> (flights arriving at it), ROUTE|<origin>-<dest>, ORIGINYEAR|<airport>|yyyy,\n");
            sb.append("            CARRIERYEAR|<code>|yyyy, CARRIERORIGIN|<code>|<airport>\n");
            sb.append("\nField semantics (BTS):\n");
            sb.append("- The five cause fields are minutes, populated only when a flight arrives 15+ minutes late,\n");
            sb.append("  and are carrier-REPORTED categories, not an independent diagnosis. Blank = not reported, never 0.\n");
            sb.append("- CARRIER = within the airline's control (crew, maintenance, cleaning, fueling...); WEATHER = extreme\n");
            sb.append("  weather; NAS = airport operations, heavy traffic, air traffic control; SECURITY = security events;\n");
            sb.append("  LATE_AIRCRAFT = the previous flight of the same aircraft arrived late.\n");
            sb.append("- SHARE_* = that cause's minutes / total reported cause minutes (minutes-weighted, not flight counts).\n");
            sb.append("- FLIGHTS_* = delayed flights with that cause > 0 (one flight can have several causes).\n");
            sb.append("- N_CAUSE_NOT_REPORTED = delayed 15+ but all five cause fields blank; N_CAUSE_SUM_MISMATCH = reported\n");
            sb.append("  causes differ from ARR_DELAY by more than 1 minute. Both are counted, not hidden.\n");
            sb.append("- MEAN_ENROUTE_GAIN_MIN = mean departure delay - mean arrival delay (positive = time made up in the air).\n");
            sb.append("- CANCEL_CODE_*: BTS cancellation reason codes (A carrier, B weather, C NAS, D security).\n");
            sb.append("- Reported causes do not fully explain operational delay; a LATE_AIRCRAFT share says an earlier\n");
            sb.append("  flight was late, not why it was late.\n");
            out.write(sb.toString().getBytes(StandardCharsets.UTF_8));
        }
    }

    private void writeReport(String inputPath, String outputPath, Instant start, Instant end,
                              boolean success, Job job) throws IOException {
        StringBuilder sb = new StringBuilder();
        sb.append("FlightPulse DelayCauseMetricsJob run report\n");
        sb.append("==============================================\n");
        sb.append("Input path:   ").append(inputPath).append('\n');
        sb.append("Output path:  ").append(outputPath).append('\n');
        sb.append("Started:      ").append(DateTimeFormatter.ISO_INSTANT.format(start)).append('\n');
        sb.append("Finished:     ").append(DateTimeFormatter.ISO_INSTANT.format(end)).append('\n');
        sb.append("Duration:     ").append(Duration.between(start, end).toSeconds()).append("s\n");
        sb.append("Success:      ").append(success).append('\n');
        sb.append("Map input records:   ").append(counter(job, "MAP_INPUT_RECORDS")).append('\n');
        sb.append("Map output records:  ").append(counter(job, "MAP_OUTPUT_RECORDS")).append('\n');
        sb.append("Reduce output rows:  ").append(counter(job, "REDUCE_OUTPUT_RECORDS")).append('\n');

        System.out.println();
        System.out.println(sb);

        Files.createDirectories(Paths.get(System.getProperty("user.home"), "flightpulse", "reports"));
        String reportPath = System.getProperty("user.home") + "/flightpulse/reports/delay_causes_" + start.toEpochMilli() + ".txt";
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
        System.exit(ToolRunner.run(new Configuration(), new DelayCauseMetricsJob(), args));
    }
}
