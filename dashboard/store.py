"""Read-only access to the exported Hadoop results, shared by the pages and the chatbot.

Nothing here analyses raw flights. It indexes the result files and, when a city has
several airports (Chicago = O'Hare + Midway), adds up the counts Hadoop produced and
re-derives ratios from those counts. Pure Python, no third-party imports, so it can be tested anywhere.
"""
import os

import content as C
from places import Places, airline_name

CAUSE_KEYS = [k for k, _, _ in C.CAUSES]            # carrier, late_aircraft, nas, weather, security
CANCEL_KEYS = [k for k, _ in C.CANCEL_REASONS]      # a_carrier, b_weather, c_nas, d_security

COUNT_COLS = (["n_flights_scheduled", "n_operated", "n_cancelled", "n_diverted", "n_delayed_15plus",
               "n_cause_reported", "n_cause_not_reported", "n_cause_sum_mismatch"]
              + ["cancel_code_" + k for k in CANCEL_KEYS]
              + ["min_" + k for k in CAUSE_KEYS] + ["flights_" + k for k in CAUSE_KEYS])


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def _numeric_row(r):
    return {k: _num(v) for k, v in r.items()}


def combine(rows):
    """Add up Hadoop counts for several airports and re-derive the ratios from the summed counts."""
    if len(rows) == 1:
        return dict(rows[0])
    out = {c: sum(r[c] for r in rows) for c in COUNT_COLS}
    ops = out["n_operated"] or 1
    out["cancellation_rate"] = out["n_cancelled"] / (out["n_flights_scheduled"] or 1)
    out["diversion_rate"] = out["n_diverted"] / (out["n_flights_scheduled"] or 1)
    out["delayed_15plus_rate"] = out["n_delayed_15plus"] / ops
    out["mean_arr_delay_min"] = sum(r["mean_arr_delay_min"] * r["n_operated"] for r in rows) / ops
    out["mean_dep_delay_min"] = sum(r["mean_dep_delay_min"] * r["n_operated"] for r in rows) / ops
    out["mean_enroute_gain_min"] = out["mean_dep_delay_min"] - out["mean_arr_delay_min"]
    total_min = sum(out["min_" + k] for k in CAUSE_KEYS) or 1
    for k in CAUSE_KEYS:
        out["share_" + k] = out["min_" + k] / total_min
    return out


class Store:
    def __init__(self, data_dir=C.DATA_DIR):
        self.dir = data_dir
        self.places = Places(data_dir)
        _, carriers_raw = C.load_names(data_dir)
        self.airlines = {code: airline_name(desc) for code, desc in carriers_raw.items()}

        self.causes_rows = [_numeric_row(r) | {"dimension": r["dimension"], "value": r["value"]}
                            for r in C.read_rows("causes.csv", data_dir)]
        self.causes = {(r["dimension"], r["value"]): r for r in self.causes_rows}
        self.airports = {r["airport"]: _numeric_row(r) | {"airport": r["airport"]}
                         for r in C.read_rows("airports.csv", data_dir)}
        self.routes = {r["route"]: _numeric_row(r) | {"route": r["route"]} for r in C.read_rows("routes.csv", data_dir)}
        self.carryover = {}
        for r in C.read_rows("carryover.csv", data_dir):
            self.carryover[(r["params"], r["dimension"], r["value"])] = _numeric_row(r) | {
                "params": r["params"], "dimension": r["dimension"], "value": r["value"]}
        self.route_carrier = [_numeric_row(r) | {k: r[k] for k in ("kind", "route", "carrier", "band")}
                              for r in C.read_rows("route_carrier.csv", data_dir)]
        self.temporal = [_numeric_row(r) | {"dimension": r["dimension"], "value": r["value"]}
                         for r in C.read_rows("temporal.csv", data_dir)]

    # ---- national / entity rows
    def national(self):
        return self.causes[("ALL", "")]

    def airline_row(self, code, year=None):
        return self.causes.get(("CARRIERYEAR", "%s|%s" % (code, year))) if year else self.causes.get(("CARRIER", code))

    def route_row(self, route):
        return self.causes.get(("ROUTE", route))

    def airline_at_city(self, carrier, airport):
        return self.causes.get(("CARRIERORIGIN", "%s|%s" % (carrier, airport)))

    def place_row(self, codes, side="origin", year=None):
        """Cause/cancellation counts for a city (all its airports combined). side: origin = flights leaving it."""
        if year and side == "origin":
            rows = [self.causes.get(("ORIGINYEAR", "%s|%s" % (c, year))) for c in codes]
        else:
            rows = [self.causes.get(("ORIGIN" if side == "origin" else "DEST", c)) for c in codes]
        rows = [r for r in rows if r]
        return combine(rows) if rows else None

    def carryover_row(self, dimension, value="", params="G90_T30"):
        return self.carryover.get((params, dimension, value))

    # ---- helpers for pages
    def airline_label(self, code):
        return self.airlines.get(code, code)

    def top_airports(self, n=None):
        codes = sorted(self.airports, key=lambda c: -self.airports[c]["total_departures"])
        return codes[:n] if n else codes

    def carriers_in_data(self):
        return sorted({r["value"] for r in self.causes_rows if r["dimension"] == "CARRIER"},
                      key=lambda c: -self.causes[("CARRIER", c)]["n_operated"])

    def routes_from(self, airport):
        out = []
        for (dim, val), r in self.causes.items():
            if dim == "ROUTE" and val.startswith(airport + "-"):
                out.append(r | {"route": val})
        return out

    def routes_to(self, airport):
        out = []
        for (dim, val), r in self.causes.items():
            if dim == "ROUTE" and val.endswith("-" + airport):
                out.append(r | {"route": val})
        return out

    def airlines_at(self, airport, min_operated=1000):
        out = []
        for (dim, val), r in self.causes.items():
            if dim == "CARRIERORIGIN":
                carrier, _, apt = val.partition("|")
                if apt == airport and r["n_operated"] >= min_operated:
                    out.append(r | {"carrier": carrier})
        return out

    def cities_for_airline(self, carrier, min_operated=2000):
        out = []
        for (dim, val), r in self.causes.items():
            if dim == "CARRIERORIGIN":
                c, _, apt = val.partition("|")
                if c == carrier and r["n_operated"] >= min_operated:
                    out.append(r | {"airport": apt})
        return out
