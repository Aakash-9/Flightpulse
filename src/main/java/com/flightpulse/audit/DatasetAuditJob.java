package com.flightpulse.audit;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.FileSystem;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.IntWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
import org.apache.hadoop.mapreduce.lib.output.FileOutputFormat;
import org.apache.hadoop.util.Tool;
import org.apache.hadoop.util.ToolRunner;

import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.time.Instant;
import java.time.format.DateTimeFormatter;

/**
 * Job A - source audit, schema validation and record profiling.
 *
 * Usage: hadoop jar flightpulse.jar com.flightpulse.audit.DatasetAuditJob <input> <output>
 */
public class DatasetAuditJob implements Tool {

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
            System.err.println("Usage: DatasetAuditJob <input path> <output path>");
            return 2;
        }
        String inputPath = args[0];
        String outputPath = args[1];

        FileSystem fs = FileSystem.get(getConf());
        if (fs.exists(new Path(outputPath))) {
            System.err.println("Output path already exists, refusing to overwrite: " + outputPath);
            System.err.println("Choose a new (versioned) output path instead.");
            return 1;
        }

        Job job = Job.getInstance(getConf(), "FlightPulse - DatasetAuditJob");
        job.setJarByClass(DatasetAuditJob.class);

        // Bronze is organized as <input>/<year>/<month>.csv. Without this,
        // FileInputFormat silently lists year subdirectories as if they were
        // input files instead of recursing into them, and every map task
        // fails trying to open a directory as a file.
        job.getConfiguration().setBoolean(FileInputFormat.INPUT_DIR_RECURSIVE, true);

        job.setMapperClass(DatasetAuditMapper.class);
        job.setCombinerClass(DatasetAuditReducer.class);
        job.setReducerClass(DatasetAuditReducer.class);

        job.setOutputKeyClass(Text.class);
        job.setOutputValueClass(IntWritable.class);

        FileInputFormat.addInputPath(job, new Path(inputPath));
        FileOutputFormat.setOutputPath(job, new Path(outputPath));

        Instant start = Instant.now();
        boolean success = job.waitForCompletion(true);
        Instant end = Instant.now();

        writeReport(inputPath, outputPath, start, end, success, job);

        return success ? 0 : 1;
    }

    private void writeReport(String inputPath, String outputPath, Instant start, Instant end,
                              boolean success, Job job) throws IOException {
        StringBuilder sb = new StringBuilder();
        sb.append("FlightPulse DatasetAuditJob run report\n");
        sb.append("========================================\n");
        sb.append("Input path:   ").append(inputPath).append('\n');
        sb.append("Output path:  ").append(outputPath).append('\n');
        sb.append("Started:      ").append(DateTimeFormatter.ISO_INSTANT.format(start)).append('\n');
        sb.append("Finished:     ").append(DateTimeFormatter.ISO_INSTANT.format(end)).append('\n');
        sb.append("Duration:     ").append(java.time.Duration.between(start, end).toSeconds()).append("s\n");
        sb.append("Success:      ").append(success).append('\n');
        sb.append("Map input records:    ").append(getCounterSafe(job, "org.apache.hadoop.mapreduce.TaskCounter", "MAP_INPUT_RECORDS")).append('\n');
        sb.append("Map output records:   ").append(getCounterSafe(job, "org.apache.hadoop.mapreduce.TaskCounter", "MAP_OUTPUT_RECORDS")).append('\n');
        sb.append("Reduce output records:").append(getCounterSafe(job, "org.apache.hadoop.mapreduce.TaskCounter", "REDUCE_OUTPUT_RECORDS")).append('\n');
        sb.append("\nData-quality counters\n");
        sb.append("----------------------\n");
        for (AuditCounters c : AuditCounters.values()) {
            sb.append(String.format("%-32s %d%n", c.name(), job.getCounters().findCounter(c).getValue()));
        }

        System.out.println();
        System.out.println(sb);

        Files.createDirectories(Paths.get(System.getProperty("user.home"), "flightpulse", "reports"));
        String fileName = "dataset_audit_" + start.toEpochMilli() + ".txt";
        String reportPath = System.getProperty("user.home") + "/flightpulse/reports/" + fileName;
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
        int exitCode = ToolRunner.run(new Configuration(), new DatasetAuditJob(), args);
        System.exit(exitCode);
    }
}
