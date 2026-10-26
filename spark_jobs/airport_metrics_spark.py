"""PySpark version of Job C (AirportMetricsJob): one scorecard per airport.

Same rule as the Java mapper: every flight counts once for its origin airport (a departure) and once for its
destination airport (an arrival). Delay figures use only flights that operated and have a delay value.
Run:  .venv-spark/bin/python spark_jobs/airport_metrics_spark.py
"""
from pyspark.sql import functions as F

import spark_common as S

spark = S.start_spark("FlightPulse-AirportMetrics")
timer = S.Timer("airport_metrics")

flights = S.read_silver(spark).where(F.col("origin").isNotNull() & F.col("dest").isNotNull())
operated = F.col("record_status").isin("VALID", "MISSING_TAIL")

# One pass over the data: each flight becomes two rows, one per airport role (like the Java mapper's two writes).
roles = flights.select(
    F.explode(F.array(
        F.struct(F.col("origin").alias("airport"), F.lit("DEP").alias("role"), S.num("dep_delay_min").alias("delay")),
        F.struct(F.col("dest").alias("airport"), F.lit("ARR").alias("role"), S.num("arr_delay_min").alias("delay")),
    )).alias("r"),
    F.col("record_status"), operated.alias("operated")).select("r.*", "record_status", "operated")


def role_stats(role, prefix):
    is_role = F.col("role") == role
    has_delay = is_role & F.col("operated") & F.col("delay").isNotNull()
    d = F.when(has_delay, F.col("delay"))
    return [
        F.sum(is_role.cast("long")).alias("total_" + prefix),
        F.sum(has_delay.cast("long")).alias(prefix[:3] + "_delay_sample_n"),
        F.sum(F.when(has_delay & (F.col("delay") >= 15), 1).otherwise(0)).alias(prefix[:3] + "_late_n"),
        F.avg(d).alias("mean_" + prefix[:3] + "_delay_min"),
        F.stddev_pop(d).alias("stddev_" + prefix[:3] + "_delay_min"),
    ]


result = roles.groupBy("airport").agg(
    *role_stats("DEP", "departures"), *role_stats("ARR", "arrivals"),
    F.sum(F.when((F.col("role") == "DEP") & (F.col("record_status") == "CANCELLED"), 1).otherwise(0)).alias("cancelled_count"),
    F.sum(F.when((F.col("role") == "DEP") & (F.col("record_status") == "DIVERTED"), 1).otherwise(0)).alias("diverted_count"),
).withColumn("dep_delay_rate", F.coalesce(F.try_divide("dep_late_n", "dep_delay_sample_n"), F.lit(0.0))
).withColumn("arr_delay_rate", F.coalesce(F.try_divide("arr_late_n", "arr_delay_sample_n"), F.lit(0.0))
).withColumn("cancellation_rate", F.coalesce(F.try_divide("cancelled_count", "total_departures"), F.lit(0.0))
).withColumn("diversion_rate", F.coalesce(F.try_divide("diverted_count", "total_departures"), F.lit(0.0))
).fillna(0.0, subset=["mean_dep_delay_min", "mean_arr_delay_min", "stddev_dep_delay_min", "stddev_arr_delay_min"]
).cache()

result.coalesce(1).write.mode("overwrite").option("header", True).csv(S.GOLD + "/spark/airport_metrics")
print("\nBusiest airports (PySpark):")
result.orderBy(F.col("total_departures").desc()).select(
    "airport", "total_departures", F.round("dep_delay_rate", 4).alias("dep_delay_rate")).show(5)

hadoop = S.hadoop_kv(spark, S.GOLD + "/airport_metrics/part-r-00000", ["airport"],
                     ["total_departures", "total_arrivals", "dep_delay_sample_n", "arr_delay_sample_n",
                      "dep_delay_rate", "arr_delay_rate", "mean_dep_delay_min", "mean_arr_delay_min",
                      "stddev_dep_delay_min", "stddev_arr_delay_min", "cancellation_rate", "diversion_rate",
                      "cancelled_count", "diverted_count"])
diff = S.compare(
    "airport metrics (%d airports)" % result.count(), result.select(
        "airport", *[c for c in hadoop.columns if c != "airport"]), hadoop, ["airport"],
    exact=["total_departures", "total_arrivals", "dep_delay_sample_n", "arr_delay_sample_n", "cancelled_count", "diverted_count"],
    approx=["dep_delay_rate", "arr_delay_rate", "cancellation_rate", "diversion_rate",
            "mean_dep_delay_min", "mean_arr_delay_min", "stddev_dep_delay_min", "stddev_arr_delay_min"],
    tolerance={"dep_delay_rate": 6e-5, "arr_delay_rate": 6e-5, "cancellation_rate": 6e-5, "diversion_rate": 6e-5,
               "mean_dep_delay_min": 0.0061, "mean_arr_delay_min": 0.0061, "stddev_dep_delay_min": 0.0061, "stddev_arr_delay_min": 0.0061})
timer.finish(spark, ["Output path: %s/spark/airport_metrics" % S.GOLD, "Compared with: %s/airport_metrics" % S.GOLD,
                     "Disagreeing rows: %d" % diff])
spark.stop()
