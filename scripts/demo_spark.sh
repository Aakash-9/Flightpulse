#!/usr/bin/env bash
# FlightPulse - the PySpark jobs: show the code, run one live, and compare with the Hadoop jobs.
#
#   ./scripts/demo_spark.sh          walk through every step (press Enter to continue)
#   ./scripts/demo_spark.sh 3        jump to one step (1-5)
#   DEMO_NOPAUSE=1 ./scripts/demo_spark.sh   print everything without pausing
#   DEMO_SKIP_RUN=1 ./scripts/demo_spark.sh  do not run the live job in step 3
#
# Tip: zoom the terminal text with Ctrl+Plus so the room can read it.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/src/main/java/com/flightpulse"
PY="$ROOT/spark_jobs"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
export PATH="$PATH:/usr/local/hadoop/bin:/usr/local/hadoop/sbin"

B=$'\e[1m'; C=$'\e[36m'; G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[0m'

title() { printf '\n%s%s=== %s ===%s\n' "$B" "$C" "$1" "$R"; }
say()   { printf '%s%s%s\n' "$G" "$1" "$R"; }
note()  { printf '%s%s%s\n' "$Y" "$1" "$R"; }
pause() { [ -n "$DEMO_NOPAUSE" ] || read -r -p "  [press Enter for the next step] " _; }

# show FILE FROM TO LANG  -> highlighted code with the REAL line numbers of the file
show() {
  local f="$1" a="${2:-1}" b="${3:-100000}" lang="${4:-python}"
  printf '\n%s%s%s   (lines %s-%s)\n' "$B" "${f#$ROOT/}" "$R" "$a" "$([ "$b" = 100000 ] && wc -l < "$f" || echo "$b")"
  if command -v pygmentize >/dev/null 2>&1; then
    sed -n "${a},${b}p" "$f" | pygmentize -l "$lang" -f terminal256 -O style=monokai 2>/dev/null \
      | awk -v s="$a" '{printf "%s%4d%s  %s\n", "\033[90m", NR+s-1, "\033[0m", $0}'
  else
    sed -n "${a},${b}p" "$f" | awk -v s="$a" '{printf "%4d  %s\n", NR+s-1, $0}'
  fi
}

lines() { cat "$@" | wc -l | tr -d ' '; }

# Duration (seconds) of the latest successful report for a job prefix, e.g. hadoop_secs airport_metrics_
hadoop_secs() {
  local f
  for f in $(ls -1 "$ROOT"/reports/"$1"*.txt 2>/dev/null | sort -r); do
    if grep -q "^Success:[[:space:]]*true" "$f"; then grep -m1 "^Duration" "$f" | tr -dc '0-9'; return; fi
  done
}
spark_secs() { local f; f=$(ls -1t "$ROOT"/reports/spark_"$1"_*.txt 2>/dev/null | head -1); [ -n "$f" ] && grep -m1 "^Duration" "$f" | tr -dc '0-9'; }

step1() {
  title "1. PySpark in this project: a second engine, used to double-check Hadoop"
  say "The pipeline and every number in the dashboard come from Hadoop (HDFS + Java MapReduce)."
  say "These 3 PySpark jobs read the SAME cleaned data in HDFS, recompute the answers, and compare them"
  say "row by row with what Hadoop produced."
  echo
  printf '  %-34s %s\n' "spark_jobs/airport_metrics_spark.py" "airport scorecards       (same as Hadoop Job C)"
  printf '  %-34s %s\n' "spark_jobs/delay_causes_spark.py"    "why flights are late     (same as Hadoop Job F)"
  printf '  %-34s %s\n' "spark_jobs/rotation_spark.py"        "each plane's flights in order + the '78 in 100' finding (Jobs G and H)"
  printf '  %-34s %s\n' "spark_jobs/spark_common.py"          "shared: start Spark, read data, compare with Hadoop"
  printf '  %-34s %s\n' "spark_jobs/test_spark_compare.py"    "proves the checker can FAIL (wrong count, missing row, ...)"
  echo
  note "  PySpark runs here in 'local' mode on this one machine, next to Hadoop's HDFS. It does not use YARN."
  pause
}

step2() {
  title "2. Same problem, two engines: put each plane's flights in time order"
  say "Hadoop needs 3 extra classes for 'secondary sort' (key, partitioner, grouping comparator):"
  printf '  %-26s %s lines\n' "TailChronoKey.java"       "$(lines "$SRC/rotation/TailChronoKey.java")"
  printf '  %-26s %s lines\n' "TailNumPartitioner.java"  "$(lines "$SRC/rotation/TailNumPartitioner.java")"
  printf '  %-26s %s lines\n' "TailGroupComparator.java" "$(lines "$SRC/rotation/TailGroupComparator.java")"
  printf '  %-26s %s lines\n' "AircraftRotationMapper/Reducer" "$(lines "$SRC/rotation/AircraftRotationMapper.java" "$SRC/rotation/AircraftRotationReducer.java")"
  show "$SRC/rotation/TailNumPartitioner.java" 1 16 java
  say "PySpark: one window (group by tail number, order by time) and a 'previous flight' lookup, then the 6 link types:"
  show "$PY/rotation_spark.py" 42 58
  note "  It is shorter because Spark has sorting-within-groups built in. Hadoop gives you the pieces and you assemble them."
  pause
}

step3() {
  title "3. Run a PySpark job live: airport scorecards for 34.8 million flights"
  if ! jps 2>/dev/null | grep -q NameNode; then
    note "HDFS is not running. Start it first:  ./scripts/start_hadoop.sh"; pause; return
  fi
  say "While it runs, open the Spark web page:  http://localhost:4040   (Jobs and Stages tabs)"
  note "  To type your own questions instead: ./scripts/pyspark_shell.sh   (opens the pyspark shell with the data loaded)"
  echo
  show "$PY/airport_metrics_spark.py" 17 24
  if [ -n "$DEMO_SKIP_RUN" ]; then note "  (live run skipped)"; pause; return; fi
  echo; say "Running:  .venv-spark/bin/python spark_jobs/airport_metrics_spark.py   (about a minute)"
  (cd "$ROOT" && .venv-spark/bin/python spark_jobs/airport_metrics_spark.py 2>&1 | tr '\r' '\n' \
     | grep -E "^\+|^\||^Busiest|^--- check|^rows |^RESULT|^Duration" | sed 's/^/  /')
  pause
}

step4() {
  title "4. The proof: PySpark's answers against Hadoop's, from the saved reports"
  for j in airport_metrics delay_causes rotation; do
    f=$(ls -1t "$ROOT"/reports/spark_"$j"_*.txt 2>/dev/null | head -1)
    [ -n "$f" ] || continue
    printf '\n  %s%s%s\n' "$B" "${f#$ROOT/}" "$R"
    grep -v "^Input path" "$f" | sed 's/^/    /'
  done
  echo
  say "What was compared, and what came out:"
  echo "    airports:      384 airports x 14 numbers (counts exactly, rates to the rounding Hadoop wrote): IDENTICAL"
  echo "    delay causes:  13,788 keys (all flights, years, months, airlines, airports, routes, ...) x 29 numbers: IDENTICAL"
  echo "    aircraft:      33,896,859 flight-to-flight links, counted per link type:"
  echo "                   IDENTICAL for the 3,604 aircraft with no two flights at the same scheduled minute;"
  echo "                   1,392 links (0.004%) differ on the other 3,835 aircraft."
  note "                   Why: for two flights at the same minute, Hadoop's secondary sort leaves the order undefined,"
  note "                   so the pairs around them can legitimately differ. Probabilities (78 in 100) still agree to 4 decimals."
  pause
}

step5() {
  title "5. Speed on this one machine (a single run each - read the caveats)"
  printf '  %-34s %-12s %s\n' "JOB" "HADOOP" "PYSPARK"
  printf '  %-34s %-12s %s\n' "Airport scorecards"      "$(hadoop_secs airport_metrics_) s"  "$(spark_secs airport_metrics) s"
  printf '  %-34s %-12s %s\n' "Why flights are late"    "$(hadoop_secs delay_causes_) s"     "$(spark_secs delay_causes) s"
  printf '  %-34s %-12s %s\n' "Aircraft chains (+ carryover)" "$(hadoop_secs rotation_) s"   "$(spark_secs rotation) s"
  echo
  note "  Do not read this as 'Spark is better'. Honest caveats:"
  note "   - the Hadoop runs were earlier, on YARN with 1 GB containers (start-up cost); Spark ran in one local process"
  note "   - the PySpark aircraft job counts the links; Hadoop also WRITES all 33.9 million link lines (2.9 GB)"
  note "   - one machine cannot show how either engine scales across many machines"
  say "  What we can say: both engines give identical answers, and the choice is a trade-off, not a verdict."
  pause
}

case "${1:-all}" in
  all) for n in 1 2 3 4 5; do step$n; done; title "That is the PySpark side of the project."; ;;
  [1-5]) step$1 ;;
  *) echo "usage: $0 [1-5]"; exit 1 ;;
esac
