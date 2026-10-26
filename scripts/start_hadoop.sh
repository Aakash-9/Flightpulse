#!/usr/bin/env bash
# Start HDFS + YARN and wait until they are really ready (safe mode off, YARN node RUNNING).
# Safe to run when they are already up. Usage: ./scripts/start_hadoop.sh
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
export HADOOP_HOME="${HADOOP_HOME:-/usr/local/hadoop}"
export PATH="$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin"

jps | grep -q NameNode || start-dfs.sh 2>&1 | grep -v WARN
echo -n "waiting for HDFS safe mode to end"
for _ in $(seq 1 60); do
  hdfs dfsadmin -safemode get 2>/dev/null | grep -q "OFF" && break
  echo -n "."; sleep 3
done
echo

jps | grep -q ResourceManager || start-yarn.sh 2>&1 | grep -v WARN
echo -n "waiting for the YARN node to register"
for _ in $(seq 1 60); do
  yarn node -list -all 2>/dev/null | grep -q "RUNNING" && break
  echo -n "."; sleep 3
done
echo

echo; echo "Services:"; jps | grep -E "NameNode|DataNode|SecondaryNameNode|ResourceManager|NodeManager" | sort -k2
yarn node -list -all 2>/dev/null | grep -E "RUNNING|UNHEALTHY|Total Nodes"
echo "Ready."
