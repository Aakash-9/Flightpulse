"""Shared helpers for the PySpark versions of the FlightPulse jobs.

These jobs read the SAME Silver data in HDFS as the Java MapReduce jobs and then check their
answers against the Hadoop output in /flightpulse/gold. They are a comparison, not a replacement:
the dashboard still shows the Hadoop results.
"""
import os
import time

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

HDFS = "hdfs://localhost:9000"
SILVER = HDFS + "/flightpulse/silver/flights"          # only files named silver-m-* are read (see read_silver)
GOLD = HDFS + "/flightpulse/gold"
REPORTS = os.path.expanduser("~/flightpulse/reports")

# Same column order as SilverSchema.java / NormalizedFlight.SILVER_HEADER
SILVER_COLUMNS = ["fl_date", "carrier", "tail_num", "flight_num", "origin", "dest", "crs_dep_day_offset",
                  "crs_dep_min", "dep_min", "dep_delay_min", "taxi_out_min", "wheels_off_min", "wheels_on_min",
                  "taxi_in_min", "crs_arr_day_offset", "crs_arr_min", "arr_min", "arr_delay_min", "cancelled",
                  "cancellation_code", "diverted", "air_time_min", "distance_mi", "carrier_delay_min",
                  "weather_delay_min", "nas_delay_min", "security_delay_min", "late_aircraft_delay_min",
                  "record_status"]


def start_spark(app_name):
    """Local Spark with a small, fixed memory budget: this VM also runs Hadoop (8 GB in total)."""
    # Shuffle/spill files must go to the real disk: /tmp is a small RAM-backed tmpfs on this VM.
    spill = os.path.expanduser("~/hadoop_data/tmp/spark")
    os.makedirs(spill, exist_ok=True)
    os.environ["SPARK_LOCAL_DIRS"] = spill
    spark = (SparkSession.builder.master("local[3]").appName(app_name)
             .config("spark.driver.memory", "2g")
             .config("spark.sql.shuffle.partitions", "12")
             .config("spark.ui.showConsoleProgress", "true")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    return spark


def read_silver(spark):
    """Silver is pipe-delimited text with no header. An empty field becomes null (= 'not reported')."""
    schema = StructType([StructField(c, StringType(), True) for c in SILVER_COLUMNS])
    # pathGlobFilter instead of a wildcard in the path: same files, and no Hadoop "file does not exist" warning on screen
    return spark.read.csv(SILVER, sep="|", schema=schema, header=False, pathGlobFilter="silver-m-*")


def num(col):
    return F.col(col).cast("double")


def hadoop_kv(spark, path, key_names, value_names, whole_key=False):
    """Read a Hadoop text output ('key<TAB>v1|v2|...') as a DataFrame with typed columns.

    `key_names` name the |-separated parts of the key (or, with whole_key=True, the one name for the entire key).
    Values stay as the numbers Hadoop wrote, cast to double.
    """
    raw = spark.read.text(path)
    parts = F.split(F.col("value"), "\t")
    key_parts = F.split(parts.getItem(0), r"\|")
    val_parts = F.split(parts.getItem(1), r"\|")
    # try_element_at is 1-based and gives null (not an error) when a key has fewer parts than names, e.g. 'G90_T30|ALL'
    cols = ([parts.getItem(0).alias(key_names[0])] if whole_key
            else [F.try_element_at(key_parts, F.lit(i + 1)).alias(n) for i, n in enumerate(key_names)])
    cols += [val_parts.getItem(i).cast("double").alias(n) for i, n in enumerate(value_names)]
    return raw.select(*cols)


def compare(label, mine, hadoop, keys, exact, approx, tolerance):
    """Join the Spark result to the Hadoop result and report how many rows differ.

    exact  - whole-number counts that must be identical
    approx - rounded ratios/means; allowed to differ by `tolerance[column]` (Hadoop wrote them rounded)
    Returns the number of rows that disagree.
    """
    j = mine.alias("s").join(hadoop.alias("h"), on=keys, how="full_outer")
    n_s, n_h = mine.count(), hadoop.count()
    both = j.filter(F.col("s." + exact[0]).isNotNull() & F.col("h." + exact[0]).isNotNull())
    bad = F.lit(False)
    for c in exact:
        bad = bad | (F.col("s." + c) != F.col("h." + c))
    for c in approx:
        bad = bad | (F.abs(F.col("s." + c) - F.col("h." + c)) > tolerance[c])
    only_one_side = j.filter(F.col("s." + exact[0]).isNull() | F.col("h." + exact[0]).isNull()).count()
    mismatched = both.filter(bad)
    n_bad = mismatched.count()
    n_both = both.count()
    print("\n--- check against Hadoop: %s ---" % label)
    print("rows from PySpark: %d   rows from Hadoop: %d   in both: %d   in only one: %d" % (n_s, n_h, n_both, only_one_side))
    print("rows where any checked number differs: %d" % n_bad)
    if n_bad:
        mismatched.show(10, truncate=False)
    print("RESULT: %s" % ("IDENTICAL" if n_bad == 0 and only_one_side == 0 else "DIFFERENCES FOUND"))
    return n_bad + only_one_side


class Timer:
    def __init__(self, job):
        self.job, self.t0 = job, time.time()

    def finish(self, spark, lines):
        secs = time.time() - self.t0
        os.makedirs(REPORTS, exist_ok=True)
        path = os.path.join(REPORTS, "spark_%s_%s.txt" % (self.job, time.strftime("%Y%m%d_%H%M%S")))
        with open(path, "w") as f:
            f.write("Job: %s (PySpark %s, local[3], driver memory 2g)\n" % (self.job, spark.version))
            f.write("Input path: %s/silver-m-*\n" % SILVER)
            f.write("Duration: %.0fs\n" % secs)
            f.write("\n".join(lines) + "\n")
        print("\nDuration: %.0f s     report: %s" % (secs, path))
        return secs
