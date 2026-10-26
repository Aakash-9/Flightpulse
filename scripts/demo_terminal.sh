#!/usr/bin/env bash
# FlightPulse - show the Hadoop code and results in the terminal, step by step.
#
#   ./scripts/demo_terminal.sh          walk through every step (press Enter to continue)
#   ./scripts/demo_terminal.sh 5        jump to one step (1-9)
#   DEMO_NOPAUSE=1 ./scripts/demo_terminal.sh   print everything without pausing
#
# Tip: zoom the terminal text with Ctrl+Plus so the room can read it.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/src/main/java/com/flightpulse"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
export HADOOP_HOME="${HADOOP_HOME:-/usr/local/hadoop}"
export PATH="$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin"

B=$'\e[1m'; C=$'\e[36m'; G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[0m'

title() { printf '\n%s%s=== %s ===%s\n' "$B" "$C" "$1" "$R"; }
say()   { printf '%s%s%s\n' "$G" "$1" "$R"; }
note()  { printf '%s%s%s\n' "$Y" "$1" "$R"; }
pause() { [ -n "$DEMO_NOPAUSE" ] || read -r -p "  [press Enter for the next step] " _; }

# show FILE [FROM [TO]]  -> highlighted Java with the REAL line numbers of the file
show() {
  local f="$1" a="${2:-1}" b="${3:-100000}"
  printf '\n%s%s%s   (lines %s-%s)\n' "$B" "${f#$ROOT/}" "$R" "$a" "$([ "$b" = 100000 ] && wc -l < "$f" || echo "$b")"
  if command -v pygmentize >/dev/null 2>&1; then
    sed -n "${a},${b}p" "$f" | pygmentize -l java -f terminal256 -O style=monokai 2>/dev/null \
      | awk -v s="$a" '{printf "%s%4d%s  %s\n", "\033[90m", NR+s-1, "\033[0m", $0}'
  else
    sed -n "${a},${b}p" "$f" | awk -v s="$a" '{printf "%4d  %s\n", NR+s-1, $0}'
  fi
}

# grep -n for the wiring lines of a file
find_lines() { grep -n --color=always -E "$2" "$1" | sed "s|^|  |"; }

step1() {
  title "1. The project: 42 Java files, one folder per job"
  say "Every analysis is a Java MapReduce program that runs on Hadoop (HDFS + YARN)."
  (cd "$SRC" && for d in audit normalize airport route temporal causes rotation carryover util; do
     printf '  %-10s %s lines\n' "$d/" "$(cat "$d"/*.java | wc -l)"; done)
  echo; printf '  main code: %s lines   tests: %s lines\n' "$(cat "$SRC"/*/*.java | wc -l)" "$(find "$ROOT/src/test" -name '*.java' | xargs cat | wc -l)"
  pause
}

step2() {
  title "2. Hadoop is really running (these are its 5 services)"
  if jps | grep -q NameNode; then
    jps | grep -E "NameNode|DataNode|SecondaryNameNode|ResourceManager|NodeManager" | sort -k2
    echo; say "The data lives in HDFS:"
    hdfs dfs -ls /flightpulse 2>/dev/null | grep -v WARN
    echo; hdfs dfs -du -s -h /flightpulse/bronze /flightpulse/silver /flightpulse/gold 2>/dev/null | grep -v WARN
    note "  bronze = raw files, silver = cleaned records, gold = the answers"
  else
    note "Hadoop is not running. Start it with:  start-dfs.sh && start-yarn.sh   (then wait ~30 s)"
  fi
  pause
}

step3() {
  title "3. A small job: Mapper = turn each flight into (airport, numbers)"
  say "Hadoop gives the mapper one line of the data at a time. This one emits two pairs per flight."
  show "$SRC/airport/AirportMetricsMapper.java" 19 51
  pause
}

step4() {
  title "4. The combiner: add up early, before sending data between computers"
  say "Without it, 69.6 million records are shipped. With it, only 42,751 are."
  show "$SRC/airport/AirportAccumulatorCombiner.java"
  echo; say "...it is switched on in the job driver:"
  find_lines "$SRC/airport/AirportMetricsJob.java" "setMapperClass|setCombinerClass|setReducerClass"
  pause
}

step5() {
  title "5. The main idea: SECONDARY SORT (put each plane's flights in time order)"
  say "Hadoop does not order values inside a group. We need each plane's flights in order, so we use 3 small classes."
  say "(a) The key = plane number + planned time. Sorting by it gives plane-then-time order:"
  show "$SRC/rotation/TailChronoKey.java" 30 37
  say "(b) The partitioner sends every flight of one plane to the same worker (it ignores the time):"
  show "$SRC/rotation/TailNumPartitioner.java" 10 16
  say "(c) The grouping comparator makes the reducer see one plane at a time, already sorted:"
  show "$SRC/rotation/TailGroupComparator.java" 13 25
  say "(d) The driver plugs them in:"
  find_lines "$SRC/rotation/AircraftRotationJob.java" "setPartitionerClass|setGroupingComparatorClass|setMapOutputKeyClass|setNumReduceTasks"
  pause
}

step6() {
  title "6. The reducer walks one plane's flights in order and checks each pair"
  show "$SRC/rotation/AircraftRotationReducer.java" 45 60
  echo; say "The rules for a valid link (this is what the unit tests check):"
  show "$SRC/rotation/LinkClassification.java" 18 36
  pause
}

step7() {
  title "7. The carryover formula (does a late plane make the next trip late?)"
  show "$SRC/carryover/CarryoverMath.java" 20 30
  pause
}

step8() {
  title "8. Real results, read straight from HDFS"
  if jps | grep -q NameNode; then
    say "Airport scorecards (airport, departures, arrivals, ... late-rate, ... cancel-rate):"
    hdfs dfs -cat /flightpulse/gold/airport_metrics/part-r-00000 2>/dev/null | grep -E "^(ATL|ORD|LAX|JFK)[[:space:]]"
    echo; say "One plane's flights, in time order, with the link verdict at the end:"
    hdfs dfs -cat /flightpulse/gold/rotation_links/part-r-00000 2>/dev/null | head -6
    echo; say "How big the secondary-sort output is:"
    hdfs dfs -du -s -h /flightpulse/gold/rotation_links 2>/dev/null | grep -v WARN
  else
    note "Hadoop is not running - start it first (step 2)."
  fi
  pause
}

step9() {
  title "9. How a job is launched, and the proof it ran"
  say "Launch command (one of the 9 jobs):"
  echo "  hadoop jar target/flightpulse.jar com.flightpulse.carryover.CarryoverAnalysisJob \\"
  echo "       /flightpulse/gold/rotation_links /flightpulse/gold/carryover_metrics"
  echo; say "Every run writes a report. The latest ones:"
  ls -1t "$ROOT"/reports/*.txt 2>/dev/null | head -5 | sed "s|$ROOT/||"
  latest=$(ls -1t "$ROOT"/reports/carryover_*.txt 2>/dev/null | head -1)
  [ -n "$latest" ] && { echo; sed -n 1,12p "$latest"; }
  echo; say "Run the unit tests yourself (takes about a minute):  cd ~/flightpulse && mvn -q -o test"
  pause
}

case "${1:-all}" in
  all) for n in 1 2 3 4 5 6 7 8 9; do step$n; done; title "That is the whole Hadoop pipeline."; ;;
  [1-9]) step$1 ;;
  *) echo "usage: $0 [1-9]"; exit 1 ;;
esac
