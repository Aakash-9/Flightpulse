"""PySpark version of Job F (DelayCauseMetricsJob): why flights are late and cancelled.

Same rules as the Java code:
  * every flight is counted under 10 keys (all flights, year, month, airline, origin, destination, route, ...);
  * a flight is "late" when it operated and arrived 15+ minutes late;
  * the five cause columns are only used for late flights, and a blank cause stays "not reported" (never 0).
Run:  .venv-spark/bin/python spark_jobs/delay_causes_spark.py
"""
from pyspark.sql import functions as F

import spark_common as S

spark = S.start_spark("FlightPulse-DelayCauses")
timer = S.Timer("delay_causes")

CAUSES = ["carrier", "weather", "nas", "security", "late_aircraft"]
c = F.col

flights = S.read_silver(spark).where(F.length("fl_date") >= 7)
dep, arr = S.num("dep_delay_min"), S.num("arr_delay_min")
year, month = F.substring("fl_date", 1, 4), F.substring("fl_date", 6, 2)
carrier, origin, dest = c("carrier"), c("origin"), c("dest")
cj = lambda *parts: F.concat_ws("|", *parts)

# One row per (flight, key) - the Java mapper's ten context.write calls.
keyed = flights.select(
    F.explode(F.array(
        F.lit("ALL"), cj(F.lit("YEAR"), year), cj(F.lit("MONTHOFYEAR"), month), cj(F.lit("CARRIER"), carrier),
        cj(F.lit("ORIGIN"), origin), cj(F.lit("DEST"), dest), cj(F.lit("ROUTE"), F.concat(origin, F.lit("-"), dest)),
        cj(F.lit("ORIGINYEAR"), origin, year), cj(F.lit("CARRIERYEAR"), carrier, year),
        cj(F.lit("CARRIERORIGIN"), carrier, origin))).alias("key"),
    c("record_status"), c("cancellation_code"), dep.alias("dep"), arr.alias("arr"),
    *[S.num(x + "_delay_min").alias(x) for x in CAUSES])

status = c("record_status")
cancelled, diverted = status == "CANCELLED", status == "DIVERTED"
operated = status.isin("VALID", "MISSING_TAIL") & c("dep").isNotNull() & c("arr").isNotNull()
late = operated & (c("arr") >= 15)
cause_cols = [c(x) for x in CAUSES]
any_cause = F.greatest(*[x.isNotNull().cast("int") for x in cause_cols]) == 1
cause_sum = sum(F.coalesce(x, F.lit(0.0)) for x in cause_cols)
count_if = lambda cond, name: F.sum(F.when(cond, 1).otherwise(0)).alias(name)

agg = keyed.groupBy("key").agg(
    F.count(F.lit(1)).alias("n_flights_scheduled"),
    count_if(operated, "n_operated"), count_if(cancelled, "n_cancelled"), count_if(diverted, "n_diverted"),
    count_if(late, "n_delayed_15plus"),
    F.sum(F.when(operated, c("dep"))).alias("sum_dep"), F.sum(F.when(operated, c("arr"))).alias("sum_arr"),
    count_if(late & any_cause, "n_cause_reported"), count_if(late & ~any_cause, "n_cause_not_reported"),
    count_if(late & any_cause & (F.abs(cause_sum - c("arr")) > 1.0), "n_cause_sum_mismatch"),
    *[count_if(cancelled & (F.substring("cancellation_code", 1, 1) == code), "cancel_code_" + name)
      for code, name in zip("ABCD", ["a_carrier", "b_weather", "c_nas", "d_security"])],
    *[F.sum(F.when(late, c(x))).alias("min_" + x) for x in CAUSES],
    *[count_if(late & (c(x) > 0), "flights_" + x) for x in CAUSES])

total_min = sum(F.coalesce(c("min_" + x), F.lit(0.0)) for x in CAUSES)
result = agg.fillna(0.0, subset=["min_" + x for x in CAUSES])
result = (result
          .withColumn("mean_arr_delay_min", F.coalesce(F.try_divide("sum_arr", "n_operated"), F.lit(0.0)))
          .withColumn("mean_dep_delay_min", F.coalesce(F.try_divide("sum_dep", "n_operated"), F.lit(0.0)))
          .withColumn("total_min", total_min))
for x in CAUSES:
    result = result.withColumn("share_" + x, F.coalesce(F.try_divide("min_" + x, "total_min"), F.lit(0.0)))
result = result.cache()
n_rows = result.count()
result.coalesce(1).write.mode("overwrite").option("header", True).csv(S.GOLD + "/spark/delay_causes")

print("\nAll US flights (PySpark):")
result.where(c("key") == "ALL").select("n_flights_scheduled", "n_delayed_15plus", "n_cancelled").show(truncate=False)
print("Airlines with the most late flights (PySpark):")
result.where(c("key").startswith("CARRIER|")).orderBy(c("n_delayed_15plus").desc()).select("key", "n_operated", "n_delayed_15plus").show(5)

hadoop = S.hadoop_kv(
    spark, S.GOLD + "/delay_cause_metrics_v2/part-r-00000", ["key"],
    ["n_flights_scheduled", "n_operated", "n_cancelled", "n_diverted", "cancellation_rate", "diversion_rate",
     "n_delayed_15plus", "delayed_15plus_rate", "mean_arr_delay_min", "mean_dep_delay_min", "mean_enroute_gain_min",
     "n_cause_reported", "n_cause_not_reported", "n_cause_sum_mismatch",
     "cancel_code_a_carrier", "cancel_code_b_weather", "cancel_code_c_nas", "cancel_code_d_security",
     "min_carrier", "min_weather", "min_nas", "min_security", "min_late_aircraft",
     "share_carrier", "share_weather", "share_nas", "share_security", "share_late_aircraft",
     "flights_carrier", "flights_weather", "flights_nas", "flights_security", "flights_late_aircraft"], whole_key=True)
exact = ["n_flights_scheduled", "n_operated", "n_cancelled", "n_diverted", "n_delayed_15plus", "n_cause_reported",
         "n_cause_not_reported", "n_cause_sum_mismatch", "cancel_code_a_carrier", "cancel_code_b_weather",
         "cancel_code_c_nas", "cancel_code_d_security"] + ["flights_" + x for x in CAUSES]
approx = ["mean_arr_delay_min", "mean_dep_delay_min"] + ["min_" + x for x in CAUSES] + ["share_" + x for x in CAUSES]
tol = {"mean_arr_delay_min": 0.0006, "mean_dep_delay_min": 0.0006}
tol.update({"min_" + x: 0.5001 for x in CAUSES})          # Hadoop wrote whole minutes
tol.update({"share_" + x: 6e-5 for x in CAUSES})          # and 4-decimal shares
diff = S.compare("delay causes (%d keys)" % n_rows, result.select("key", *exact, *approx), hadoop, ["key"], exact, approx, tol)
timer.finish(spark, ["Output path: %s/spark/delay_causes" % S.GOLD, "Compared with: %s/delay_cause_metrics_v2" % S.GOLD,
                     "Keys compared: %d" % n_rows, "Disagreeing rows: %d" % diff])
spark.stop()
