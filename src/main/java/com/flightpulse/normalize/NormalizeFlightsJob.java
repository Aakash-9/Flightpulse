package com.flightpulse.normalize;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.FSDataOutputStream;
import org.apache.hadoop.fs.FileSystem;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.NullWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
import org.apache.hadoop.mapreduce.lib.output.FileOutputFormat;
import org.apache.hadoop.mapreduce.lib.output.LazyOutputFormat;
import org.apache.hadoop.mapreduce.lib.output.MultipleOutputs;
import org.apache.hadoop.mapreduce.lib.output.TextOutputFormat;
import org.apache.hadoop.util.Tool;
import org.apache.hadoop.util.ToolRunner;

import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.time.Instant;
import java.time.format.DateTimeFormatter;

/**
 * Job B - normalization and data-quality classification.
 *
 * Reads raw Bronze CSV, writes two named outputs directly under <output>
 * (MultipleOutputs naming: <output>/silver-m-NNNNN, <output>/quarantine-m-NNNNN):
 *   silver-m-*      - normalized, pipe-delimited, schema in NormalizedFlight.SILVER_HEADER
 *   quarantine-m-*  - raw lines that failed parsing/validation, preserved verbatim with a reason
 *
 * Usage: hadoop jar flightpulse.jar com.flightpulse.normalize.NormalizeFlightsJob <input> <output>
 */
public class NormalizeFlightsJob implements Tool {

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
            System.err.println("Usage: NormalizeFlightsJob <input path> <output path>");
            return 2;
        }
        String inputPath = args[0];
        String outputPath = args[1];

        FileSystem fs = FileSystem.get(getConf());
        if (fs.exists(new Path(outputPath))) {
            System.err.println("Output path already exists, refusing to overwrite: " + outputPath);
            return 1;
        }

        Job job = Job.getInstance(getConf(), "FlightPulse - NormalizeFlightsJob");
        job.setJarByClass(NormalizeFlightsJob.class);
        job.getConfiguration().setBoolean(FileInputFormat.INPUT_DIR_RECURSIVE, true);

        job.setMapperClass(NormalizeFlightsMapper.class);
        job.setNumReduceTasks(0);

        job.setOutputKeyClass(NullWritable.class);
        job.setOutputValueClass(Text.class);
        // NOT NullOutputFormat: its OutputCommitter is a no-op and never
        // promotes MultipleOutputs' files out of _temporary/. LazyOutputFormat
        // wrapping a real FileOutputFormat gets correct commit behavior while
        // still not creating any empty default part-files, since the mapper
        // never calls context.write() directly - only multipleOutputs.write().
        LazyOutputFormat.setOutputFormatClass(job, TextOutputFormat.class);

        MultipleOutputs.addNamedOutput(job, "silver", TextOutputFormat.class, NullWritable.class, Text.class);
        MultipleOutputs.addNamedOutput(job, "quarantine", TextOutputFormat.class, NullWritable.class, Text.class);

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
        // Named outputs ("silver", "quarantine") land directly under outputPath
        // as silver-m-NNNNN / quarantine-m-NNNNN, not in subdirectories.
        Path schemaPath = new Path(outputPath, "_SCHEMA.txt");
        try (FSDataOutputStream out = fs.create(schemaPath)) {
            StringBuilder sb = new StringBuilder();
            sb.append("FlightPulse Silver schema (pipe-delimited '|', no header row in data files)\n");
            sb.append(NormalizedFlight.SILVER_HEADER).append('\n');
            sb.append("\nNotes:\n");
            sb.append("- City-name fields dropped (see L_AIRPORT.csv for ORIGIN/DEST city lookup).\n");
            sb.append("- CRS_DEP_*/CRS_ARR_* are DERIVED (actual - delay); source has no CRS_DEP_TIME/CRS_ARR_TIME.\n");
            sb.append("- *_DAY_OFFSET is relative to FL_DATE (0 = same day, +/-1 = crossed midnight).\n");
            sb.append("- Timezones are NOT resolved here; absolute chronology is handled in the rotation job.\n");
            sb.append("- RECORD_STATUS in {VALID, CANCELLED, DIVERTED, MISSING_TAIL}. INVALID rows are quarantined, not here.\n");
            out.write(sb.toString().getBytes(StandardCharsets.UTF_8));
        }
    }

    private void writeReport(String inputPath, String outputPath, Instant start, Instant end,
                              boolean success, Job job) throws IOException {
        StringBuilder sb = new StringBuilder();
        sb.append("FlightPulse NormalizeFlightsJob run report\n");
        sb.append("============================================\n");
        sb.append("Input path:   ").append(inputPath).append('\n');
        sb.append("Output path:  ").append(outputPath).append('\n');
        sb.append("Started:      ").append(DateTimeFormatter.ISO_INSTANT.format(start)).append('\n');
        sb.append("Finished:     ").append(DateTimeFormatter.ISO_INSTANT.format(end)).append('\n');
        sb.append("Duration:     ").append(java.time.Duration.between(start, end).toSeconds()).append("s\n");
        sb.append("Success:      ").append(success).append('\n');
        sb.append("\nClassification counters\n");
        sb.append("------------------------\n");
        for (NormalizeCounters c : NormalizeCounters.values()) {
            sb.append(String.format("%-24s %d%n", c.name(), job.getCounters().findCounter(c).getValue()));
        }

        System.out.println();
        System.out.println(sb);

        Files.createDirectories(Paths.get(System.getProperty("user.home"), "flightpulse", "reports"));
        String reportPath = System.getProperty("user.home") + "/flightpulse/reports/normalize_" + start.toEpochMilli() + ".txt";
        try (PrintWriter pw = new PrintWriter(new FileWriter(reportPath))) {
            pw.print(sb);
        }
        System.out.println("Report written to: " + reportPath);
    }

    public static void main(String[] args) throws Exception {
        int exitCode = ToolRunner.run(new Configuration(), new NormalizeFlightsJob(), args);
        System.exit(exitCode);
    }
}
