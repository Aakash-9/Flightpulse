package com.flightpulse.carryover;

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
 * Job H - slack-aware potential carryover estimation and sensitivity analysis (RQ2).
 *
 * Usage: hadoop jar flightpulse.jar com.flightpulse.carryover.CarryoverAnalysisJob <rotation links input> <output>
 * Optional: -D flightpulse.carryover.gaps=60,90,120 -D flightpulse.carryover.turnarounds=20,30,45
 */
public class CarryoverAnalysisJob implements Tool {

    public static final String HEADER = String.join("|",
            "KEY(G<maxGap>_T<minTurnaround>|dimension|value)",
            "N_LINKS", "N_EXPOSED", "EXPOSED_RATE",
            "MEAN_A_ARR_DELAY_POS_MIN", "MEAN_EXPOSURE_MIN", "MEAN_CARRYOVER_MIN", "MEAN_B_DEP_DELAY_POS_MIN",
            "CARRYOVER_SHARE_OF_EXPOSURE",
            "N_A_LATE15", "N_A_NOT_LATE15",
            "P_B_LATE15_GIVEN_A_LATE15", "P_B_LATE15_GIVEN_A_NOT_LATE15",
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
            System.err.println("Usage: CarryoverAnalysisJob <rotation links input> <output>");
            return 2;
        }
        String inputPath = args[0];
        String outputPath = args[1];

        FileSystem fs = FileSystem.get(getConf());
        if (fs.exists(new Path(outputPath))) {
            System.err.println("Output path already exists, refusing to overwrite: " + outputPath);
            return 1;
        }

        Job job = Job.getInstance(getConf(), "FlightPulse - CarryoverAnalysisJob");
        job.setJarByClass(CarryoverAnalysisJob.class);

        job.setMapperClass(CarryoverMapper.class);
        job.setCombinerClass(CarryoverReducers.Combiner.class);
        job.setReducerClass(CarryoverReducers.Finalizer.class);
        job.setNumReduceTasks(1);

        job.setMapOutputKeyClass(Text.class);
        job.setMapOutputValueClass(CarryoverAccumulator.class);
        job.setOutputKeyClass(Text.class);
        job.setOutputValueClass(Text.class);

        // Rotation output also contains _SCHEMA.txt / _SUCCESS; FileInputFormat
        // ignores names starting with '_', so only part-r-* files are read.
        FileInputFormat.addInputPath(job, new Path(inputPath));
        FileOutputFormat.setOutputPath(job, new Path(outputPath));

        Instant start = Instant.now();
        boolean success = job.waitForCompletion(true);
        Instant end = Instant.now();

        if (success) {
            writeSchemaDoc(fs, outputPath, job.getConfiguration());
        }
        writeReport(inputPath, outputPath, start, end, success, job);
        return success ? 0 : 1;
    }

    private void writeSchemaDoc(FileSystem fs, String outputPath, Configuration c) throws IOException {
        try (FSDataOutputStream out = fs.create(new Path(outputPath, "_SCHEMA.txt"))) {
            StringBuilder sb = new StringBuilder();
            sb.append("FlightPulse CarryoverAnalysisJob output (pipe-delimited)\n");
            sb.append("Row: ").append(HEADER).append('\n');
            sb.append("maxGap values (min):        ").append(c.get(CarryoverMapper.GAPS_KEY, "60,90,120")).append('\n');
            sb.append("minTurnaround values (min): ").append(c.get(CarryoverMapper.TURNAROUNDS_KEY, "20,30,45")).append('\n');
            sb.append("Dimensions: ALL, SLACK|<bucket>, ARRDELAY_A|<bucket>, YEAR|<yyyy>, AIRPORT|<connection airport = leg A destination>, CARRIER|<airline code of leg A>\n");
            sb.append("\nFormulas (minutes):\n");
            sb.append("  Slack = ScheduledGround - MinTurnaround\n");
            sb.append("  PotentialExposure = max(0, max(0, ArrDelay(A)) - Slack)\n");
            sb.append("  EstimatedCarryover = min(max(0, DepDelay(B)), PotentialExposure)\n");
            sb.append("\nCaveats:\n");
            sb.append("- Observational proxy only. It does NOT establish that the preceding flight caused the later flight's delay.\n");
            sb.append("- MinTurnaround and maxGap are modelling assumptions, not operating standards; that is why all combinations are reported.\n");
            sb.append("- ScheduledGround comes from derived scheduled times (actual - delay) and is NOT timezone-corrected (no airport timezone data in this package).\n");
            sb.append("- Only STATUS LINKED/GAP_TOO_LARGE links with ground <= maxGap are used; cancelled/diverted legs never appear in the rotation input.\n");
            sb.append("- LOW_SAMPLE_FLAG=1 when N_LINKS < ").append(CarryoverReducers.Finalizer.LOW_SAMPLE_BELOW).append(".\n");
            out.write(sb.toString().getBytes(StandardCharsets.UTF_8));
        }
    }

    private void writeReport(String inputPath, String outputPath, Instant start, Instant end,
                              boolean success, Job job) throws IOException {
        StringBuilder sb = new StringBuilder();
        sb.append("FlightPulse CarryoverAnalysisJob run report\n");
        sb.append("==============================================\n");
        sb.append("Input path:   ").append(inputPath).append('\n');
        sb.append("Output path:  ").append(outputPath).append('\n');
        sb.append("Started:      ").append(DateTimeFormatter.ISO_INSTANT.format(start)).append('\n');
        sb.append("Finished:     ").append(DateTimeFormatter.ISO_INSTANT.format(end)).append('\n');
        sb.append("Duration:     ").append(Duration.between(start, end).toSeconds()).append("s\n");
        sb.append("Success:      ").append(success).append('\n');
        sb.append("Map input records:    ").append(counter(job, "MAP_INPUT_RECORDS")).append('\n');
        sb.append("Map output records:   ").append(counter(job, "MAP_OUTPUT_RECORDS")).append('\n');
        sb.append("Reduce output rows:   ").append(counter(job, "REDUCE_OUTPUT_RECORDS")).append('\n');
        try {
            sb.append("Unparseable links:    ")
                    .append(job.getCounters().findCounter("Carryover", "UNPARSEABLE_LINK").getValue()).append('\n');
        } catch (Exception ignored) {
            // counters unavailable when the job failed early
        }

        System.out.println();
        System.out.println(sb);

        Files.createDirectories(Paths.get(System.getProperty("user.home"), "flightpulse", "reports"));
        String reportPath = System.getProperty("user.home") + "/flightpulse/reports/carryover_" + start.toEpochMilli() + ".txt";
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
        System.exit(ToolRunner.run(new Configuration(), new CarryoverAnalysisJob(), args));
    }
}
