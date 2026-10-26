"""Runs inside the interactive PySpark shell (started by scripts/pyspark_shell.sh) after Spark's own banner.

`spark` and `sc` already exist. This adds `flights` (the 34.8 million cleaned flights in HDFS, read lazily:
nothing is scanned until you ask a question) and `F` (Spark's functions).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.environ["FLIGHTPULSE_HOME"], "spark_jobs"))
import spark_common as S                      # noqa: E402
from pyspark.sql import functions as F        # noqa: E402,F401

flights = S.read_silver(spark)                # noqa: F821  (spark is created by the pyspark shell)
label = sc.setJobDescription                  # noqa: F821  label("text") names the next jobs on the Spark web page

print("""
FlightPulse is loaded.   flights = the cleaned flights in HDFS (all columns are text; delays need .cast("double"))
Watch every question you type run as a job:  http://localhost:%s   (open it in the browser, Jobs tab)

Tip: type  label("any text")  first, and the Jobs page shows your text instead of Spark's internal name.

Try these, one at a time:
  label("Count every flight")
  flights.count()

  label("Flights per airline")
  flights.groupBy("carrier").count().orderBy("count", ascending=False).show(5)

  label("Cancelled flights by reason")
  flights.where("record_status = 'CANCELLED'").groupBy("cancellation_code").count().show()

  late = flights.where(F.col("arr_delay_min").cast("double") >= 15)
  label("Which airports have the most late flights")
  late.groupBy("origin").count().orderBy("count", ascending=False).show(5)

After each one, press F5 in the browser: the Spark page does not refresh by itself.

Leave with  exit()
""" % sc.uiWebUrl.rsplit(":", 1)[1])          # noqa: F821  (the port, normally 4040)
