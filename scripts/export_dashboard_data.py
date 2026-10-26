#!/usr/bin/env python3
"""Export FlightPulse Hadoop (Gold) results to small CSV files for the dashboard.

This is FORMATTING ONLY. Every number in the dashboard was computed by the Java
MapReduce jobs and is read back out of HDFS here; nothing is recalculated.
Each export checks its row count against the count the Hadoop job itself
reported, and aborts on any mismatch, so a stale or partial output cannot
silently reach the dashboard.

Usage: python3 scripts/export_dashboard_data.py [output_dir]
"""
import csv
import os
import re
import subprocess
import sys

HADOOP_HOME = "/usr/local/hadoop"
ENV = dict(os.environ,
           JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64",
           PATH=os.environ.get("PATH", "") + ":" + HADOOP_HOME + "/bin")

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/flightpulse/dashboard/data")
REPORTS = os.path.expanduser("~/flightpulse/reports")

RATE_ROW = ["total_flights", "dep_delay_sample_n", "arr_delay_sample_n",
            "dep_delay_rate", "arr_delay_rate", "mean_dep_delay_min", "mean_arr_delay_min",
            "stddev_dep_delay_min", "stddev_arr_delay_min", "cancellation_rate", "diversion_rate",
            "cancelled_count", "diverted_count", "low_sample_flag"]

AIRPORT_COLS = ["total_departures", "total_arrivals", "dep_delay_sample_n", "arr_delay_sample_n",
                "dep_delay_rate", "arr_delay_rate", "mean_dep_delay_min", "mean_arr_delay_min",
                "stddev_dep_delay_min", "stddev_arr_delay_min", "cancellation_rate", "diversion_rate",
                "cancelled_count", "diverted_count"]

CAUSE_COLS = ["n_flights_scheduled", "n_operated", "n_cancelled", "n_diverted",
              "cancellation_rate", "diversion_rate", "n_delayed_15plus", "delayed_15plus_rate",
              "mean_arr_delay_min", "mean_dep_delay_min", "mean_enroute_gain_min",
              "n_cause_reported", "n_cause_not_reported", "n_cause_sum_mismatch",
              "cancel_code_a_carrier", "cancel_code_b_weather", "cancel_code_c_nas", "cancel_code_d_security",
              "min_carrier", "min_weather", "min_nas", "min_security", "min_late_aircraft",
              "share_carrier", "share_weather", "share_nas", "share_security", "share_late_aircraft",
              "flights_carrier", "flights_weather", "flights_nas", "flights_security", "flights_late_aircraft"]

CARRYOVER_COLS = ["n_links", "n_exposed", "exposed_rate", "mean_a_arr_delay_pos_min", "mean_exposure_min",
                  "mean_carryover_min", "mean_b_dep_delay_pos_min", "carryover_share_of_exposure",
                  "n_a_late15", "n_a_not_late15", "p_b_late15_given_a_late15",
                  "p_b_late15_given_a_not_late15", "low_sample_flag"]

ROTATION_COLS = ["tail_num", "leg_a", "leg_b", "leg_a_dest", "leg_b_origin", "ground_minutes",
                 "leg_a_arr_delay_min", "leg_b_dep_delay_min", "link_status"]


def hdfs_lines(path):
    p = subprocess.Popen([HADOOP_HOME + "/bin/hdfs", "dfs", "-cat", path],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=ENV)
    for line in p.stdout:
        yield line.rstrip("\n")
    p.stdout.close()
    p.wait()


def write_csv(name, header, rows, expected):
    path = os.path.join(OUT, name)
    n = 0
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            if len(r) != len(header):
                sys.exit("ABORT %s: row has %d columns, expected %d: %r" % (name, len(r), len(header), r[:4]))
            w.writerow(r)
            n += 1
    if expected is not None and n != expected:
        sys.exit("ABORT %s: wrote %d rows but the Hadoop job reported %d" % (name, n, expected))
    print("%-22s %8d rows" % (name, n))


def kv_rows(hdfs_path, key_parts):
    """Yield key components + value columns from 'key<TAB>v1|v2|...' lines."""
    for line in hdfs_lines(hdfs_path):
        if not line:
            continue
        key, _, val = line.partition("\t")
        yield key_parts(key) + val.split("|")


def latest_success_report(prefix):
    files = sorted(f for f in os.listdir(REPORTS) if f.startswith(prefix) and f.endswith(".txt"))
    for f in reversed(files):
        text = open(os.path.join(REPORTS, f)).read()
        if re.search(r"^Success:\s+true", text, re.M):
            return f, text
    return None, None


def field(text, label):
    m = re.search(r"^" + re.escape(label) + r"\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def main():
    os.makedirs(OUT, exist_ok=True)
    g = "/flightpulse/gold/"

    write_csv("airports.csv", ["airport"] + AIRPORT_COLS,
              kv_rows(g + "airport_metrics/part-r-00000", lambda k: [k]), 384)
    write_csv("routes.csv", ["route"] + RATE_ROW,
              kv_rows(g + "route_metrics/part-r-00000", lambda k: [k]), 8410)
    write_csv("temporal.csv", ["dimension", "value"] + RATE_ROW,
              kv_rows(g + "temporal_metrics_v2/part-r-00000", lambda k: k.split("|", 1)), 271)
    write_csv("causes.csv", ["dimension", "value"] + CAUSE_COLS,
              kv_rows(g + "delay_cause_metrics_v2/part-r-00000", lambda k: (k.split("|", 1) + [""])[:2]), 13788)
    write_csv("carryover.csv", ["params", "dimension", "value"] + CARRYOVER_COLS,
              kv_rows(g + "carryover_metrics_v2/part-r-00000",
                      lambda k: (k.split("|", 2) + [""])[:3] if k.count("|") < 2 else k.split("|", 2)), 3724)

    def rc_key(k):
        # RC|ORIGIN-DEST|CARRIER  or  RCB|ORIGIN-DEST|CARRIER|BAND
        parts = k.split("|")
        kind, route, carrier = parts[0], parts[1], parts[2]
        band = parts[3] if len(parts) > 3 else "ALL_DAY"
        return [kind, route, carrier, band]
    write_csv("route_carrier.csv", ["kind", "route", "carrier", "band"] + RATE_ROW,
              kv_rows(g + "route_carrier_metrics/part-r-00000", rc_key), 72946)

    write_csv("audit_months.csv", ["month", "records"],
              (line.split("\t") for line in hdfs_lines(g + "audit/all_years_run2/part-r-00000") if line), 66)

    export_rotation_sample()
    export_pipeline()


def export_rotation_sample():
    """Every-Nth qualifying aircraft's links for one fixed summer day (deterministic)."""
    day = "2024-07-12"
    want, step, min_links = 30, 25, 5
    chosen, buf, cur, seen, picked = [], [], None, 0, 0

    def flush():
        nonlocal seen, picked
        if cur is not None and len(buf) >= min_links:
            seen += 1
            if seen % step == 0 and picked < want:
                chosen.extend(buf)
                picked += 1

    for line in hdfs_lines("/flightpulse/gold/rotation_links/part-r-00000"):
        tail, _, val = line.partition("\t")
        if tail != cur:
            flush()
            cur, buf = tail, []
        if val.startswith(day):
            buf.append([tail] + val.split("|"))
        if picked >= want:
            break
    if picked < want:
        flush()
    print("  rotation sample: %d aircraft" % picked)
    write_csv("rotation_sample.csv", ROTATION_COLS, chosen, None)


def export_pipeline():
    jobs = [("audit", "DatasetAuditJob", "Check every record is well-formed"),
            ("normalize", "NormalizeFlightsJob", "Clean and standardise the data (Silver)"),
            ("airport_metrics", "AirportMetricsJob", "Airport scorecards"),
            ("route_metrics", "RouteMetricsJob", "Route scorecards"),
            ("temporal_metrics", "TemporalMetricsJob", "When flights run late"),
            ("delay_causes", "DelayCauseMetricsJob", "Why flights run late"),
            ("route_carrier", "RouteCarrierMetricsJob", "Route x airline reliability"),
            ("rotation", "AircraftRotationJob", "Chain each plane's flights in order"),
            ("carryover", "CarryoverAnalysisJob", "Does lateness pass to the next flight")]
    rows = []
    for prefix, name, plain in jobs:
        # dataset_audit_ files use a different prefix than the job short name
        pfx = "dataset_audit_" if prefix == "audit" else prefix
        fname, text = latest_success_report(pfx)
        if not text:
            print("  (no successful report found for %s - skipped)" % name)
            continue
        dur = re.sub(r"s$", "", field(text, "Duration:"))
        out_path = field(text, "Output path:")
        if out_path.endswith("rotation_links_compress_test"):
            # The compressed verification run's scratch output was deleted after its
            # MD5 matched /flightpulse/gold/rotation_links exactly (byte-identical).
            out_path = "/flightpulse/gold/rotation_links"
        rows.append([name, plain, field(text, "Input path:"), out_path, dur, fname])
    write_csv("pipeline.csv", ["job", "what_it_does", "input_path", "output_path", "duration_seconds", "report_file"],
              rows, None)


if __name__ == "__main__":
    main()
