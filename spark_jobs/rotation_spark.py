"""PySpark version of Job G (AircraftRotationJob) and the baseline of Job H (CarryoverAnalysisJob).

Hadoop needed a composite key (TailChronoKey), a custom partitioner and a grouping comparator to get each
aircraft's flights in time order. Spark does the same with one window: group by tail number, order by time,
look at the previous flight (lag).

Same rules as the Java code:
  * only VALID flights with a tail number and scheduled times are chained;
  * time is days*1440 + minutes from the schedule (NOT time-zone corrected - this data has no time zones);
  * a pair (A, B) of consecutive flights is DUPLICATE_RECORD, AMBIGUOUS_CHRONOLOGY, NEGATIVE_GROUND_TIME,
    ROUTE_DISCONTINUITY, GAP_TOO_LARGE (> 90 min) or LINKED;
  * carryover baseline: gap <= 90 min, minimum turnaround 30 min.
Run:  .venv-spark/bin/python spark_jobs/rotation_spark.py
"""
from pyspark.sql import Window
from pyspark.sql import functions as F

import spark_common as S

MAX_GAP, TURNAROUND = 90, 30.0

spark = S.start_spark("FlightPulse-AircraftRotation")
timer = S.Timer("rotation")
c = F.col

silver = S.read_silver(spark)
epoch_day = F.datediff(F.to_date("fl_date"), F.to_date(F.lit("1970-01-01")))
as_int = lambda name: F.coalesce(S.num(name), F.lit(0.0)).cast("long")      # blank -> 0, fraction dropped (like the Java parse)
dep_chrono = (epoch_day + as_int("crs_dep_day_offset")) * 1440 + as_int("crs_dep_min")
arr_chrono = (epoch_day + as_int("crs_arr_day_offset")) * 1440 + as_int("crs_arr_min")

legs = (silver
        .where((c("record_status") == "VALID") & c("tail_num").isNotNull()
               & c("crs_dep_min").isNotNull() & c("crs_arr_min").isNotNull() & F.to_date("fl_date").isNotNull())
        .select("tail_num", "flight_num", "origin", "dest",
                dep_chrono.alias("dep"), arr_chrono.alias("arr"),
                F.coalesce(S.num("dep_delay_min"), F.lit(0.0)).alias("dep_delay"),
                F.coalesce(S.num("arr_delay_min"), F.lit(0.0)).alias("arr_delay")))

# The whole trick: every aircraft's flights in time order, each row able to see the one before it.
# (Ties on the schedule time are broken by flight number etc.; Hadoop leaves that order undefined.)
w = Window.partitionBy("tail_num").orderBy("dep", "arr", "flight_num", "origin", "dest")
prev = lambda name: F.lag(name).over(w)
pairs = (legs.select("tail_num", "origin", "dest", "flight_num", "dep", "arr", "dep_delay",
                     prev("dep").alias("a_dep"), prev("arr").alias("a_arr"), prev("origin").alias("a_origin"),
                     prev("dest").alias("a_dest"), prev("flight_num").alias("a_flight"), prev("arr_delay").alias("a_arr_delay"))
         .where(c("a_dep").isNotNull()))

ground = c("dep") - c("a_arr")
same_instant = c("dep") == c("a_dep")
identical = (c("origin") == c("a_origin")) & (c("dest") == c("a_dest")) & (c("flight_num") == c("a_flight")) & (c("arr") == c("a_arr"))
status = (F.when(same_instant & identical, "DUPLICATE_RECORD")
          .when(same_instant, "AMBIGUOUS_CHRONOLOGY")
          .when(ground < 0, "NEGATIVE_GROUND_TIME")
          .when(c("a_dest") != c("origin"), "ROUTE_DISCONTINUITY")
          .when(ground > MAX_GAP, "GAP_TOO_LARGE")
          .otherwise("LINKED"))
links = pairs.select("tail_num", status.alias("status"), ground.alias("ground"), c("a_arr_delay"), c("dep_delay")).cache()

# Aircraft with two flights at the same scheduled minute: their order is a coin toss in Hadoop's secondary sort
# (the key only holds tail + time), so the pairs around them can legitimately differ between the two engines.
tie_tails = legs.groupBy("tail_num", "dep").count().where(c("count") > 1).select("tail_num").distinct().cache()

counts = {r["status"]: r["count"] for r in links.groupBy("status").count().collect()}
n_links = sum(counts.values())
n_legs = legs.count()
n_aircraft = legs.select("tail_num").distinct().count()

# Hadoop's own output: the last |-field of every link line is its status.
hadoop_links = (spark.read.text(S.GOLD + "/rotation_links/part-r-*")
                .select(F.substring_index(F.substring_index("value", "\t", 1), "|", 1).alias("tail_num"),
                        F.substring_index("value", "|", -1).alias("status")).cache())
hadoop_counts = {r["status"]: r["count"] for r in hadoop_links.groupBy("status").count().collect()}
n_tie_tails = tie_tails.count()
mine_clear = {r["status"]: r["count"] for r in links.join(F.broadcast(tie_tails), "tail_num", "left_anti").groupBy("status").count().collect()}
hadoop_clear = {r["status"]: r["count"] for r in hadoop_links.join(F.broadcast(tie_tails), "tail_num", "left_anti").groupBy("status").count().collect()}

print("\n--- aircraft chains: PySpark vs Hadoop ---")
print("flights chained: %d   aircraft: %d   links: %d   (links = flights - aircraft: %s)" % (
    n_legs, n_aircraft, n_links, n_links == n_legs - n_aircraft))
print("%-22s %12s %12s %8s" % ("link status", "PySpark", "Hadoop", "diff"))
disagree = 0
for st in sorted(set(counts) | set(hadoop_counts), key=lambda k: -hadoop_counts.get(k, 0)):
    a, b = counts.get(st, 0), hadoop_counts.get(st, 0)
    disagree += abs(a - b)
    print("%-22s %12d %12d %8d" % (st, a, b, a - b))
print("RESULT: %s" % ("IDENTICAL" if disagree == 0 else "DIFFERENCES FOUND (%d links)" % disagree))

print("\nSame comparison, only aircraft with NO two flights at the same scheduled minute (%d of %d aircraft have a tie):" % (n_tie_tails, n_aircraft))
print("%-22s %12s %12s %8s" % ("link status", "PySpark", "Hadoop", "diff"))
clear_bad = 0
for st in sorted(set(mine_clear) | set(hadoop_clear), key=lambda k: -hadoop_clear.get(k, 0)):
    a, b = mine_clear.get(st, 0), hadoop_clear.get(st, 0)
    clear_bad += abs(a - b)
    print("%-22s %12d %12d %8d" % (st, a, b, a - b))
print("RESULT (tie-free aircraft): %s" % ("IDENTICAL" if clear_bad == 0 else "DIFFERENCES FOUND (%d links)" % clear_bad))

# ---- carryover baseline (maxGap 90, turnaround 30), the finding behind "78 in 100"
linked = links.where(c("status") == "LINKED")
slack = c("ground") - TURNAROUND
exposure = F.greatest(F.lit(0.0), F.greatest(F.lit(0.0), c("a_arr_delay")) - slack)
a_late, b_late = c("a_arr_delay") >= 15, c("dep_delay") >= 15
mine = linked.agg(
    F.count(F.lit(1)).alias("n_links"), F.sum(F.when(exposure > 0, 1).otherwise(0)).alias("n_exposed"),
    F.sum(F.when(a_late, 1).otherwise(0)).alias("n_a_late15"), F.sum(F.when(~a_late, 1).otherwise(0)).alias("n_a_not_late15"),
    F.avg(F.when(a_late, b_late.cast("double"))).alias("p_b_late15_given_a_late15"),
    F.avg(F.when(~a_late, b_late.cast("double"))).alias("p_b_late15_given_a_not_late15")).collect()[0].asDict()

carry = S.hadoop_kv(spark, S.GOLD + "/carryover_metrics_v2/part-r-00000", ["params", "dimension", "value"],
                    ["n_links", "n_exposed", "exposed_rate", "mean_a_arr_delay_pos_min", "mean_exposure_min",
                     "mean_carryover_min", "mean_b_dep_delay_pos_min", "carryover_share_of_exposure", "n_a_late15",
                     "n_a_not_late15", "p_b_late15_given_a_late15", "p_b_late15_given_a_not_late15", "low_sample_flag"])
hrow = carry.where((c("params") == "G90_T30") & (c("dimension") == "ALL") & c("value").isNull()).collect()[0].asDict()
print("\n--- carryover baseline (gap 90 min, turnaround 30 min): PySpark vs Hadoop ---")
print("%-32s %14s %14s" % ("", "PySpark", "Hadoop"))
carry_bad = 0
for k in ["n_links", "n_exposed", "n_a_late15", "n_a_not_late15"]:
    print("%-32s %14d %14d   (%.4f%% apart)" % (k, mine[k], int(hrow[k]), abs(mine[k] - hrow[k]) / hrow[k] * 100))
    carry_bad = max(carry_bad, abs(mine[k] - hrow[k]) / hrow[k] * 100)
probs_ok = True
for k in ["p_b_late15_given_a_late15", "p_b_late15_given_a_not_late15"]:
    probs_ok &= abs(mine[k] - hrow[k]) <= 6e-5
    print("%-32s %14.4f %14.4f" % (k, mine[k], hrow[k]))
print("So: when a plane lands 15+ minutes late, its next trip leaves 15+ minutes late %.0f times in 100 (on-time landing: %.1f in 100)."
      % (mine["p_b_late15_given_a_late15"] * 100, mine["p_b_late15_given_a_not_late15"] * 100))
print("RESULT: the two probabilities are %s to 4 decimals; the counts are at most %.4f%% apart (the tied flights above)."
      % ("IDENTICAL" if probs_ok else "DIFFERENT", carry_bad))

timer.finish(spark, ["Chained flights: %d" % n_legs, "Aircraft: %d" % n_aircraft, "Links: %d" % n_links,
                     "Link status disagreement vs Hadoop, all aircraft (links): %d" % disagree,
                     "Aircraft with tied schedule times: %d of %d" % (n_tie_tails, n_aircraft),
                     "Link status disagreement vs Hadoop, tie-free aircraft (links): %d" % clear_bad, "Carryover baseline: probabilities identical to 4 decimals: %s; largest count difference: %.4f%%" % (probs_ok, carry_bad),
                     "Note: PySpark counts the links; it does not write all 33.9M link lines the way the Hadoop job does."])
spark.stop()
