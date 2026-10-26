package com.flightpulse.rotation;

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
 * Job G - aircraft rotation reconstruction via Hadoop secondary sort.
 *
 * Usage: hadoop jar flightpulse.jar com.flightpulse.rotation.AircraftRotationJob <silver input> <output> [maxGapMinutes]
 */
public class AircraftRotationJob implements Tool {

    public static final String HEADER = String.join("|",
            "TAIL_NUM(key)",
            "LEG_A", "LEG_B", "LEG_A_DEST", "LEG_B_ORIGIN",
            "GROUND_MINUTES", "LEG_A_ARR_DELAY_MIN", "LEG_B_DEP_DELAY_MIN",
            "LINK_STATUS");

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
        if (args.length < 2 || args.length > 3) {
            System.err.println("Usage: AircraftRotationJob <silver input path> <output path> [maxGapMinutes, default "
                    + AircraftRotationReducer.DEFAULT_MAX_GAP_MINUTES + "]");
            return 2;
        }
        String inputPath = args[0];
        String outputPath = args[1];
        long maxGap = args.length == 3 ? Long.parseLong(args[2]) : AircraftRotationReducer.DEFAULT_MAX_GAP_MINUTES;

        FileSystem fs = FileSystem.get(getConf());
        if (fs.exists(new Path(outputPath))) {
            System.err.println("Output path already exists, refusing to overwrite: " + outputPath);
            return 1;
        }

        Job job = Job.getInstance(getConf(), "FlightPulse - AircraftRotationJob (maxGap=" + maxGap + "m)");
        job.setJarByClass(AircraftRotationJob.class);
        job.getConfiguration().setBoolean(FileInputFormat.INPUT_DIR_RECURSIVE, true);
        job.getConfiguration().setLong(AircraftRotationReducer.MAX_GAP_CONF_KEY, maxGap);

        // The shuffle here cannot be combined (every leg is a distinct key), so
        // it carries ~2GB of map output. On this 40GB single-node VM that
        // overflowed local disk during the reduce-side merge when run through
        // one uncompressed reducer. Defaults below can be overridden with -D.
        Configuration jc = job.getConfiguration();
        // Hadoop's own default for mapreduce.map.output.compress is the explicit
        // string "false", so "only set if unset" never fired (compression
        // silently did nothing). Use our own flag, default on; pass
        // -D flightpulse.rotation.compress=false for the uncompressed benchmark.
        boolean compress = jc.getBoolean("flightpulse.rotation.compress", true);
        jc.setBoolean("mapreduce.map.output.compress", compress);
        if (compress) {
            jc.set("mapreduce.map.output.compress.codec", "org.apache.hadoop.io.compress.DefaultCodec");
        }
        job.setNumReduceTasks(jc.getInt("flightpulse.rotation.reducers", 3));

        job.setMapperClass(AircraftRotationMapper.class);
        job.setReducerClass(AircraftRotationReducer.class);
        job.setPartitionerClass(TailNumPartitioner.class);
        job.setGroupingComparatorClass(TailGroupComparator.class);
        // No custom sort comparator needed: TailChronoKey's own compareTo
        // already sorts by (tailNum, chronoMin), which is exactly the order
        // the secondary sort requires.

        job.setMapOutputKeyClass(TailChronoKey.class);
        job.setMapOutputValueClass(FlightLeg.class);
        job.setOutputKeyClass(Text.class);
        job.setOutputValueClass(Text.class);

        FileInputFormat.addInputPath(job, new Path(inputPath));
        FileOutputFormat.setOutputPath(job, new Path(outputPath));

        Instant start = Instant.now();
        boolean success = job.waitForCompletion(true);
        Instant end = Instant.now();

        if (success) {
            writeSchemaDoc(fs, outputPath, maxGap);
        }
        writeReport(inputPath, outputPath, start, end, success, job, maxGap);

        return success ? 0 : 1;
    }

    private void writeSchemaDoc(FileSystem fs, String outputPath, long maxGap) throws IOException {
        try (FSDataOutputStream out = fs.create(new Path(outputPath, "_SCHEMA.txt"))) {
            StringBuilder sb = new StringBuilder();
            sb.append("FlightPulse AircraftRotationJob output (pipe-delimited)\n");
            sb.append("Key: TAIL_NUM   Value: ").append(HEADER).append('\n');
            sb.append("maxGapMinutes used for this run: ").append(maxGap).append('\n');
            sb.append("\nLINK_STATUS values:\n");
            sb.append("  LINKED                - valid candidate rotation link\n");
            sb.append("  ROUTE_DISCONTINUITY   - leg A's destination != leg B's origin\n");
            sb.append("  GAP_TOO_LARGE         - ground time exceeds maxGapMinutes\n");
            sb.append("  NEGATIVE_GROUND_TIME  - B's scheduled departure precedes A's scheduled arrival\n");
            sb.append("  AMBIGUOUS_CHRONOLOGY  - A and B share a scheduled-departure instant but differ otherwise\n");
            sb.append("  DUPLICATE_RECORD      - A and B are the same flight\n");
            sb.append("\nLIMITATION (see README/mapper javadoc): ground time is computed from a\n");
            sb.append("calendar-local chronological ordinal, NOT a timezone-aware instant - this\n");
            sb.append("dataset has no airport timezone reference. Gaps on timezone-crossing\n");
            sb.append("connections are not corrected for that difference. Only RECORD_STATUS=VALID\n");
            sb.append("legs participate; cancelled/diverted/missing-tail flights are excluded (see\n");
            sb.append("AircraftRotationMapper) and so do not appear as link endpoints or break chains.\n");
            out.write(sb.toString().getBytes(StandardCharsets.UTF_8));
        }
    }

    private void writeReport(String inputPath, String outputPath, Instant start, Instant end,
                              boolean success, Job job, long maxGap) throws IOException {
        StringBuilder sb = new StringBuilder();
        sb.append("FlightPulse AircraftRotationJob run report\n");
        sb.append("=============================================\n");
        sb.append("Input path:     ").append(inputPath).append('\n');
        sb.append("Output path:    ").append(outputPath).append('\n');
        sb.append("maxGapMinutes:  ").append(maxGap).append('\n');
        sb.append("Started:        ").append(DateTimeFormatter.ISO_INSTANT.format(start)).append('\n');
        sb.append("Finished:       ").append(DateTimeFormatter.ISO_INSTANT.format(end)).append('\n');
        sb.append("Duration:       ").append(Duration.between(start, end).toSeconds()).append("s\n");
        sb.append("Success:        ").append(success).append('\n');
        sb.append("Reduce output records (candidate links): ")
                .append(getCounterSafe(job, "org.apache.hadoop.mapreduce.TaskCounter", "REDUCE_OUTPUT_RECORDS"))
                .append('\n');
        sb.append("Map output records (eligible legs):      ")
                .append(getCounterSafe(job, "org.apache.hadoop.mapreduce.TaskCounter", "MAP_OUTPUT_RECORDS"))
                .append('\n');

        System.out.println();
        System.out.println(sb);

        Files.createDirectories(Paths.get(System.getProperty("user.home"), "flightpulse", "reports"));
        String reportPath = System.getProperty("user.home") + "/flightpulse/reports/rotation_" + start.toEpochMilli() + ".txt";
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
        int exitCode = ToolRunner.run(new Configuration(), new AircraftRotationJob(), args);
        System.exit(exitCode);
    }
}
