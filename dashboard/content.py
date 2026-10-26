"""Plain-language wording and display-selection helpers for the FlightPulse dashboard.

No analysis happens here. Every rate/count comes from the Hadoop job outputs
(dashboard/data/*.csv). This module only (a) turns those numbers into plain
words, (b) attaches readable names, and (c) picks which rows to display
(sorting, applying a minimum-sample-size filter). It deliberately has no
third-party imports so it can be unit-tested anywhere.
"""
import csv
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

LATE_DEFINITION = "A flight is called \"late\" when it arrives 15 or more minutes after its planned time."


def read_rows(name, data_dir=DATA_DIR):
    with open(os.path.join(data_dir, name), newline="") as f:
        return list(csv.DictReader(f))


def num(row, key):
    return float(row[key])


# ---------- words for numbers ----------

def per100_value(rate):
    """Rate (0..1) -> 'out of every 100' number, with sensible rounding."""
    v = rate * 100.0
    if v >= 10:
        return "%d" % round(v)
    if v >= 1:
        return "%.1f" % v
    return "%.1f" % v


def say_per100(rate):
    v = rate * 100.0
    s = per100_value(rate)
    if v < 0.05:
        return "almost none out of every 100"
    if v < 1:
        return "less than 1 out of every 100 (%s)" % s
    return "about %s out of every 100" % s


def big_count(n):
    n = float(n)
    if n >= 1e9:
        return "%.1f billion" % (n / 1e9)
    if n >= 1e6:
        return "%.1f million" % (n / 1e6)
    if n >= 1e3:
        return "{:,.0f}".format(n)
    return "%d" % n


def enough_flights(n, minimum):
    return float(n) >= minimum


# ---------- names ----------

def load_names(data_dir=DATA_DIR):
    airports = {r["Code"]: r["Description"] for r in read_rows("ref_airports.csv", data_dir)}
    carriers = {r["Code"]: r["Description"] for r in read_rows("ref_carriers.csv", data_dir)}
    return airports, carriers


def city(code, airports):
    """'ATL' -> 'Atlanta, GA' (falls back to the code)."""
    d = airports.get(code)
    if not d:
        return code
    return d.split(":", 1)[0].strip()


def airport_label(code, airports):
    """'ATL' -> 'Atlanta, GA - Hartsfield-Jackson Atlanta International (ATL)'."""
    d = airports.get(code)
    if not d:
        return code
    place, _, name = d.partition(":")
    return "%s - %s (%s)" % (place.strip(), name.strip(), code)


def airline_label(code, carriers):
    d = carriers.get(code)
    return d if d else code


def route_label(route, airports):
    a, _, b = route.partition("-")
    return "%s to %s" % (city(a, airports), city(b, airports))


# ---------- fixed vocabularies ----------

WEEKDAY_SHORT = {"1-MONDAY": "Mon", "2-TUESDAY": "Tue", "3-WEDNESDAY": "Wed", "4-THURSDAY": "Thu",
                 "5-FRIDAY": "Fri", "6-SATURDAY": "Sat", "7-SUNDAY": "Sun"}
WEEKDAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTH_NAMES = {"01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun",
               "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"}

BAND_LABEL = {"MORNING": "Morning (5am to noon)", "AFTERNOON": "Afternoon (noon to 5pm)",
              "EVENING": "Evening (5pm to 10pm)", "NIGHT": "Night (10pm to 5am)"}
BAND_ORDER = ["MORNING", "AFTERNOON", "EVENING", "NIGHT"]

CAUSES = [
    ("carrier", "The airline's own jobs",
     "Things the airline controls: crew, cleaning, fueling, repairs."),
    ("late_aircraft", "The plane arrived late from its last trip",
     "The same plane was late on its trip before, so it started this trip late."),
    ("nas", "Busy skies and airports",
     "Too many planes at once, airport runway work, or air traffic control."),
    ("weather", "Bad weather",
     "Storms, snow, fog or wind that made flying unsafe or slow."),
    ("security", "Security problems",
     "Rare: a terminal evacuation or a security breach."),
]

CANCEL_REASONS = [
    ("a_carrier", "The airline's own problem"),
    ("b_weather", "Bad weather"),
    ("c_nas", "Busy skies and airports"),
    ("d_security", "Marked \"security\" in the data"),
]

CANCEL_D_CAUTION = ("Almost all of the \"security\" cancellations are in 2020 (the year COVID-19 closed down travel). "
                    "That looks like how cancellations were recorded that year, not thousands of real security "
                    "scares. We have not been able to confirm this, so treat that one with care.")

LINK_STATUS_PLAIN = {
    "LINKED": "Same plane, flew straight on to its next trip",
    "GAP_TOO_LARGE": "Plane waited a long time before its next trip",
    "ROUTE_DISCONTINUITY": "Next trip started somewhere else (a flight in between is not in our data)",
    "NEGATIVE_GROUND_TIME": "The plan overlaps itself (the schedule data looks off)",
    "AMBIGUOUS_CHRONOLOGY": "Two trips claim the same start time",
    "DUPLICATE_RECORD": "The same trip appears twice",
}

SLACK_LABEL = {"<0": "Planned stop was shorter than our guess for the time needed",
               "0-14": "Only 0 to 14 spare minutes",
               "15-29": "15 to 29 spare minutes",
               "30-59": "30 to 59 spare minutes",
               "60+": "60 or more spare minutes"}
SLACK_ORDER = ["<0", "0-14", "15-29", "30-59", "60+"]

ARR_LABEL = {"<=0": "On time or early", "1-14": "A little late (1 to 14 min)",
             "15-44": "Late (15 to 44 min)", "45-89": "Very late (45 to 89 min)",
             "90+": "Extremely late (90+ min)"}
ARR_ORDER = ["<=0", "1-14", "15-44", "45-89", "90+"]

GLOSSARY = [
    ("Late", LATE_DEFINITION),
    ("Cancelled", "The airline decided not to fly that trip at all."),
    ("Diverted", "The plane landed at a different airport than planned."),
    ("Route", "A trip from one airport to another, in one direction. New York to Los Angeles is a different route from Los Angeles to New York."),
    ("Aircraft chain", "All the trips one plane makes, one after another. We rebuild these from each plane's tail number."),
    ("Spare minutes", "Time a plane has sitting at the airport beyond the minutes we guess it needs to get ready again."),
    ("Hadoop", "A way for a team of computers to share a very big job. Here it reads and counts every one of the 34.8 million flights."),
]


# ---------- choosing what to show ----------

def rank_rows(rows, key, min_n, n_key, top=10, worst_first=True):
    """Return the top rows by `key`, ignoring rows with fewer than `min_n` flights.

    Small samples can look extreme by chance, so they are excluded from rankings
    (they are still in the data files, never deleted).
    """
    ok = [r for r in rows if float(r[n_key]) >= min_n]
    ok.sort(key=lambda r: float(r[key]), reverse=worst_first)
    return ok[:top]


def pick_rows(rows, **equals):
    return [r for r in rows if all(r.get(k) == v for k, v in equals.items())]


def best_and_worst(rows, key, min_n, n_key):
    ok = [r for r in rows if float(r[n_key]) >= min_n]
    if not ok:
        return None, None
    return min(ok, key=lambda r: float(r[key])), max(ok, key=lambda r: float(r[key]))


def main_cause(row):
    """Name of the delay cause with the biggest share of delay minutes in this row."""
    best = max(CAUSES, key=lambda c: float(row["share_" + c[0]]))
    return best[1]


def dim_rows(rows, dimension):
    return [r for r in rows if r["dimension"] == dimension]


# ---------- the "what we found" cards (every number comes from the Hadoop output rows) ----------

def hour_label(h):
    h = int(h)
    if h == 0:
        return "midnight"
    if h == 12:
        return "noon"
    return "%dam" % h if h < 12 else "%dpm" % (h - 12)


def findings(causes, temporal, carryover):
    """Six plain-language headline findings, built from exported Hadoop rows only."""
    all_row = pick_rows(causes, dimension="ALL")[0]
    late = float(all_row["delayed_15plus_rate"])

    cells = pick_rows(temporal, dimension="WEEKDAYHOUR")
    best, worst = best_and_worst(cells, "arr_delay_rate", 20000, "total_flights")

    def cell_name(r):
        day, hour = r["value"].split("|")
        return "%s %s" % (WEEKDAY_SHORT[day], hour_label(hour))

    co = pick_rows(carryover, params="G90_T30", dimension="ALL")[0]
    p_late = float(co["p_b_late15_given_a_late15"])
    p_ontime = float(co["p_b_late15_given_a_not_late15"])

    shares = sorted(((float(all_row["share_" + k]), label) for k, label, _ in CAUSES), reverse=True)
    y2020 = pick_rows(causes, dimension="YEAR", value="2020")[0]
    y2021 = pick_rows(causes, dimension="YEAR", value="2021")[0]
    gain = float(all_row["mean_enroute_gain_min"])

    return [
        {"big": "%s in 100" % per100_value(late), "title": "flights arrive late",
         "more": "Late means 15 or more minutes after the planned time. We counted %s flights between 2020 and mid-2025."
                 % big_count(all_row["n_flights_scheduled"])},
        {"big": cell_name(worst), "title": "is the roughest time to fly",
         "more": "About %s in 100 flights arrive late then. At the calmest time, %s, only about %s in 100 do."
                 % (per100_value(float(worst["arr_delay_rate"])), cell_name(best), per100_value(float(best["arr_delay_rate"])))},
        {"big": "%s in 100" % per100_value(p_late), "title": "next trips leave late when the plane before landed late",
         "more": "If the plane before landed on time, only about %s in 100 leave late. Late planes tend to pass lateness on."
                 % per100_value(p_ontime)},
        {"big": "%d%%" % round(shares[0][0] * 100), "title": "of all lateness: %s" % shares[0][1].lower(),
         "more": "Next: %s (%d%%), then %s (%d%%) and %s (%d%%)."
                 % (shares[1][1].lower(), round(shares[1][0] * 100), shares[2][1].lower(), round(shares[2][0] * 100),
                    shares[3][1].lower(), round(shares[3][0] * 100))},
        {"big": "%s in 100" % per100_value(float(y2020["cancellation_rate"])), "title": "flights were cancelled in 2020, the COVID year",
         "more": "In 2021 it was about %s in 100. In 2020 flights were also late less often (%s in 100). It was the year travel dropped sharply."
                 % (per100_value(float(y2021["cancellation_rate"])), per100_value(float(y2020["delayed_15plus_rate"])))},
        {"big": "%d min" % round(gain), "title": "caught up in the air, on average",
         "more": "Planes leave about %d minutes late on average but land only about %d minutes late."
                 % (round(float(all_row["mean_dep_delay_min"])), round(float(all_row["mean_arr_delay_min"])))},
    ]
