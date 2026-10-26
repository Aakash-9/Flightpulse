#!/usr/bin/env bash
# Open the interactive PySpark shell on the FlightPulse data, and the Spark web page that shows jobs running.
#
#   ./scripts/pyspark_shell.sh                 open the shell (and the Spark web page in the browser)
#   NO_BROWSER=1 ./scripts/pyspark_shell.sh    do not open the browser; open http://localhost:4040 yourself
#
# Needs HDFS running (./scripts/start_hadoop.sh) and the PySpark venv:  see README, "PySpark cross-check".

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
export FLIGHTPULSE_HOME="$ROOT"
export PYSPARK_PYTHON="$ROOT/.venv-spark/bin/python"
export SPARK_LOCAL_DIRS="$HOME/hadoop_data/tmp/spark"           # real disk, not the small RAM-backed /tmp
mkdir -p "$SPARK_LOCAL_DIRS"
export PYTHONSTARTUP="$ROOT/spark_jobs/shell_startup.py"        # pyspark runs it after its own banner

if ! "$JAVA_HOME/bin/jps" 2>/dev/null | grep -q NameNode; then
  echo "HDFS is not running, so there is no data to read. Start it first:  ./scripts/start_hadoop.sh"; exit 1
fi
[ -x "$ROOT/.venv-spark/bin/pyspark" ] || { echo "PySpark is not installed. See README, section 'PySpark cross-check'."; exit 1; }

if [ -z "$NO_BROWSER" ] && [ -n "$DISPLAY$WAYLAND_DISPLAY" ] && command -v xdg-open >/dev/null 2>&1; then
  # the page only answers once Spark has started, so open it a little later, in the background
  (sleep 12; xdg-open http://localhost:4040/jobs/ >/dev/null 2>&1) &
fi

exec "$ROOT/.venv-spark/bin/pyspark" --master 'local[3]' --driver-memory 2g --name FlightPulse-Shell \
     --conf spark.sql.shuffle.partitions=12 --conf spark.ui.port=4040 \
     --driver-java-options "-Dlog4j2.configurationFile=file:$ROOT/spark_jobs/log4j2-shell.properties"
