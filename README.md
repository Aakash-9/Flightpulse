# FlightPulse

Hadoop-based distributed airline delay analytics over the US BTS Reporting
Carrier On-Time Performance dataset (2020-2025).

Core platform: HDFS + Java MapReduce (YARN), pseudo-distributed single-node
cluster, Hadoop 3.5.0. No Spark, no Hive, no Pig in the core pipeline.

## Status

This is a work in progress. Current state, honestly:

- **Bronze (raw ingest):** done. 66 monthly CSVs (2020-2025, ~5.0GB) loaded
  into `/flightpulse/bronze/<year>/flights_<year>_<month>.csv`.
- **Job A - DatasetAuditJob:** done and validated against the full dataset.
  Schema audit, record counts, data-quality counters (missing tail numbers,
  cancelled/diverted counts, malformed rows). See `reports/dataset_audit_*.txt`.
- **Job B - NormalizeFlightsJob:** done. Run against the full 2020-2025
  dataset (34.8M records -> `/flightpulse/silver/flights`, 3.7GB, 0 invalid/
  quarantined). Parses Bronze with a real CSV parser (quoted commas in city
  names are real in this data - a naive split(",") corrupts rows), derives
  scheduled departure/arrival time from actual time minus delay (this BTS
  package has no CRS_DEP_TIME/CRS_ARR_TIME columns), classifies each record.
  Output lands as `<output>/silver-m-NNNNN` and `<output>/quarantine-m-NNNNN`
  (MultipleOutputs naming - not subdirectories), schema documented in
  `<output>/_SCHEMA.txt` and `NormalizedFlight.SILVER_HEADER`.
- **Job C - AirportMetricsJob:** done. Run against full Silver ->
  `/flightpulse/gold/airport_metrics`, 384 distinct airports. Demonstrates a
  real combiner (69.5M map-output records collapsed to 42,751 before
  shuffle).
- **Job D - RouteMetricsJob:** done. -> `/flightpulse/gold/route_metrics`,
  8,410 distinct directional routes. Flags (not drops) low-sample-size
  routes for ranking purposes.
- **Job E - TemporalMetricsJob:** done. -> `/flightpulse/gold/temporal_metrics`,
  103 time buckets (6 years + 66 months + 7 weekdays + 24 scheduled-departure
  hours). Reuses RouteAccumulator's aggregation math under different keys.
  Findings line up with known real-world aviation patterns (2020's low delay
  rate / high cancellation rate from COVID capacity cuts; Tue/Wed being the
  lightest travel days) - a useful sanity check that the pipeline is
  computing something real, not just running without crashing.
- **Job G - AircraftRotationJob:** done. Hadoop secondary sort (composite
  `TailChronoKey`, `TailNumPartitioner`, `TailGroupComparator`), 3 reducers.
  33.9M eligible legs / 7,439 aircraft -> 33,896,859 adjacent-leg links in
  `/flightpulse/gold/rotation_links` (62.4% LINKED at a 90-minute threshold).
  Ground times are NOT timezone-corrected (no airport timezone data here).
  Local shuffle/spill dirs had to be moved off the RAM-backed `/tmp` tmpfs
  (`hadoop.tmp.dir`, yarn local-dirs) before this job could run.
- **Job H - CarryoverAnalysisJob:** done. Evaluates 9 combinations of
  maxGap (60/90/120) x min-turnaround (20/30/45) in one pass with in-mapper
  combining -> `/flightpulse/gold/carryover_metrics_v2` (3,724 rows, now also by
  airline; baseline G90_T30 = the 21,140,066 LINKED links). Observational proxy
  only; no causal claim. Results depend strongly on the turnaround
  assumption (share of links with positive exposure: 9% at 20 min, 14% at
  30 min, 37% at 45 min, for gap 90).
- **Job F - DelayCauseMetricsJob:** done -> `/flightpulse/gold/delay_cause_metrics_v2`
  (13,788 rows: ALL, YEAR, MONTHOFYEAR, CARRIER, ORIGIN, DEST, ROUTE, ORIGINYEAR,
  CARRIERYEAR, CARRIERORIGIN; the first version with 420 rows is superseded).
  Source-reported cause minutes only (blank = not reported, never 0), plus
  cancellation-code counts and carrier/airport reliability splits. BTS fills the five
  cause columns only for flights arriving 15+ minutes late, and "weather" means
  extreme weather only; the dashboard says so wherever it shows weather.
- **Compression benchmark (first Milestone 7 data point):** AircraftRotationJob
  with map-output compression off vs on (DefaultCodec), 3 reducers: shuffle
  3.18GB -> 0.71GB, 1124s -> 506s, outputs byte-identical (same MD5). An
  earlier "compression" run had silently done nothing because Hadoop's own
  default is the string "false", not unset; fixed with an explicit
  `flightpulse.rotation.compress` flag.
- **Extra jobs for the dashboard:** `TemporalMetricsJob` now also emits a
  168-cell weekday x scheduled-hour grid (`/flightpulse/gold/temporal_metrics_v2`,
  271 buckets); `RouteCarrierMetricsJob` gives route x airline reliability overall
  and by time-of-day band (`/flightpulse/gold/route_carrier_metrics`, 72,946 rows).
- **Dashboard (Streamlit), `dashboard/`:** 8 pages in plain words, every place and airline
  by its full name (no codes), and a "grown-up details" toggle.
  - *Ask a question* (`views/ask.py`, `chatbot.py`): a rule-based question box, not an LLM. It
    works out which city, airline, route, reason and year a question means, answers in a
    sentence with a chart, and says "I did not understand" instead of guessing. Example:
    "How many flights were delayed by bad weather leaving Chicago?" Every number comes from
    the exported Hadoop output and each answer names the job and rows it came from.
  - *Cities*, *Routes*, *Airlines*: a ranking view and a one-place view with reasons,
    cancellations, routes that add to the delay, airlines, whether late planes pass lateness
    on, and a "What could help" section (`advice.py`).
  - *When and why*, *Late planes* (the aircraft-chain finding), *How we built this*
    (pipeline, benchmarks and the real Java code), and *About this project*.
  - "What could help" ideas are rule-driven (a reason must be 3 points above the national
    share) and each is labelled "Backed by research", "Mixed evidence" or "Common practice,
    not proven here". They are ideas to look into: this data cannot show what would work.
  It only DISPLAYS Hadoop output: `scripts/export_dashboard_data.py` copies the Gold results
  out of HDFS into `dashboard/data/*.csv` and aborts if any row count differs from the
  job counter. 42 unit tests (`python3 -m unittest discover -s dashboard -p "test_*.py"`)
  cover the wording helpers, the chatbot (each past bug has a regression test) and check
  the exported files against figures the independent jobs reported. Every city (305),
  airline (18), route origin (50) and 30 chat questions were also run headlessly with
  Streamlit's AppTest without errors, and the pages were screenshotted in a real browser
  (Playwright + Chromium) and fixed from what they showed. Whether the wording reads well
  to someone who has never seen the project has not been tested on a real person.
  Run locally: `pip install -r dashboard/requirements.txt` then
  `streamlit run app.py` from inside `dashboard/`. It does not need Hadoop.
- **Terminal demo scripts:** `scripts/start_hadoop.sh` starts HDFS+YARN and waits until
  they are really ready (use it after any VM reboot). `scripts/demo_terminal.sh` walks
  through the Hadoop code (colour-highlighted, real line numbers) and live results in
  9 steps (`./scripts/demo_terminal.sh 5` jumps to one step; `DEMO_NOPAUSE=1` prints all).
- **PySpark cross-check, `spark_jobs/`:** the same Silver data in HDFS, recomputed with PySpark 4.2.0
  (local mode, 3 cores, 2 GB; install in its own venv: `python3 -m venv .venv-spark &&
  .venv-spark/bin/pip install -r spark_jobs/requirements.txt`; needs Java 17). Hadoop stays the
  pipeline and the dashboard source; these jobs compare their answers with the Hadoop output in HDFS:
  - `airport_metrics_spark.py` (Job C): 384 airports x 14 numbers, identical to Hadoop, 38-40 s (Hadoop 240 s).
  - `delay_causes_spark.py` (Job F): 13,788 keys x 29 numbers, identical, 98 s (Hadoop 343 s).
  - `rotation_spark.py` (Jobs G+H): a window function replaces the secondary-sort classes. All 33,896,859
    links match in total. Link types are identical for the 3,604 aircraft with no two flights at the same
    scheduled minute; 1,392 links (0.004%) differ on the other 3,835 aircraft, because Hadoop leaves the
    order of tied flights undefined. The carryover probabilities (78 in 100 and 9.6 in 100) agree to 4
    decimals, the raw counts are at most 0.015% apart. 216 s (Hadoop 506 s, which also writes all 33.9M links).
  - `test_spark_compare.py` shows the checker fails on a wrong count, an out-of-tolerance rate or a missing row.
  Timings are single runs on one machine, on different days and settings (Hadoop ran on YARN with 1 GB
  containers), so they show a trade-off, not that one engine is better. Each run writes `reports/spark_*.txt`.
  Terminal walkthrough: `scripts/demo_spark.sh` (live run included; Spark's web page is at localhost:4040).
  Interactive: `scripts/pyspark_shell.sh` opens the real `pyspark` shell with `flights` (the 34.8M cleaned flights)
  loaded and opens the Spark web page, so every question typed shows up as a running job. Checked: `flights.count()`
  gives 34,786,532 (the Hadoop total) and the top late-flight origins match the dashboard's Cities page.
- **Docker (dashboard only):** `dashboard/Dockerfile` and `dashboard/docker-compose.yml`
  (python:3.12-slim, non-root user, health check). `cd dashboard && docker compose up --build`, then open
  http://localhost:8501. WRITTEN BUT NOT YET RUN: Docker is not installed in this VM, so the image has not
  been built or tested. Hadoop is not containerised.
- **Dashboard code tour:** `scripts/demo_dashboard_code.sh` shows where each dashboard file is and how the
  question box, the numbers and the ideas work, in 8 steps with real line numbers.
- **Not yet built:** remaining Milestone 7 experiments (reducer count,
  combiner on/off, raw vs normalized input) and the final written report.

## Schema notes (verified against the actual data, not assumed)

The BTS CSV columns actually present in this package (identical across all
66 files):

```
FL_DATE, OP_UNIQUE_CARRIER, TAIL_NUM, OP_CARRIER_FL_NUM,
ORIGIN, ORIGIN_CITY_NAME, DEST, DEST_CITY_NAME,
DEP_TIME, DEP_DELAY, TAXI_OUT, WHEELS_OFF, WHEELS_ON, TAXI_IN, ARR_TIME, ARR_DELAY,
CANCELLED, CANCELLATION_CODE, DIVERTED,
AIR_TIME, DISTANCE,
CARRIER_DELAY, WEATHER_DELAY, NAS_DELAY, SECURITY_DELAY, LATE_AIRCRAFT_DELAY
```

No `CRS_DEP_TIME`/`CRS_ARR_TIME`/`CRS_ELAPSED_TIME`. `L_AIRPORT.csv` and
`L_UNIQUE_CARRIERS.csv` are just `Code,Description` - no timezone data, which
matters for the aircraft rotation job later (Milestone 5).

## Building

```
mvn -DskipTests package   # produces target/flightpulse.jar
mvn test                  # unit tests
```

## Running a job

```
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export HADOOP_HOME=/usr/local/hadoop
export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin

start-dfs.sh && start-yarn.sh

hadoop jar target/flightpulse.jar com.flightpulse.audit.DatasetAuditJob \
    /flightpulse/bronze /flightpulse/gold/audit/<run-name>
```

Every job driver writes a run report (input/output paths, duration, success,
counters) to `reports/` and refuses to overwrite an existing output path.

## Project structure

```
src/main/java/com/flightpulse/
  audit/       Job A - DatasetAuditJob
  normalize/   Job B - NormalizeFlightsJob
  airport/     Job C - AirportMetricsJob
  route/       Job D - RouteMetricsJob (RouteAccumulator also reused by temporal/)
  temporal/    Job E - TemporalMetricsJob
  causes/      Job F - DelayCauseMetricsJob
  rotation/    Job G - AircraftRotationJob (secondary sort)
  carryover/   Job H - CarryoverAnalysisJob
  util/        Schema constants, CSV parsing, clock-time math
src/test/java/ ...   mirrors the above
reports/       Per-run job reports: the executed evidence behind each result (Hadoop and PySpark)
scripts/       start_hadoop.sh, demo_terminal.sh, demo_dashboard_code.sh, demo_spark.sh, export_dashboard_data.py
spark_jobs/    PySpark versions of Jobs C, F, G+H that check themselves against the Hadoop output
dashboard/     Streamlit app: app.py, views/, chatbot.py, advice.py, store.py, data/, code/
```

## Environment notes

Developed on a resource-constrained VirtualBox VM (originally 4GB RAM/25GB
disk, since increased to 8GB RAM/40GB disk after early jobs crashed the VM
under real workloads - see git history/commit messages for that process).
Hadoop daemon heap sizes and YARN container sizing in
`$HADOOP_HOME/etc/hadoop/{hadoop,yarn}-env.sh` and
`{mapred,yarn}-site.xml` are tuned down from Hadoop's defaults accordingly;
see the comments in those files before assuming default Hadoop memory
settings apply.
