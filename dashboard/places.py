"""Full, readable names for airports/cities and airlines (no codes shown to readers).

Names come from the official BTS lookup tables shipped with the data
(ref_airports.csv, ref_carriers.csv). Where one city has more than one busy
airport (Chicago, New York, Washington...), the airport's own name is added so
two different places are never shown under the same label.
"""
import re

from content import DATA_DIR, read_rows

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "Washington, D.C.", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "PR": "Puerto Rico", "VI": "U.S. Virgin Islands", "GU": "Guam", "AS": "American Samoa",
    "MP": "Northern Mariana Islands",
}

# A city only gets its airport name added when it really has several busy airports.
BUSY_AIRPORT_DEPARTURES = 5000


def airline_name(description):
    """'Southwest Airlines Co.' -> 'Southwest Airlines'; 'ExpressJet Airlines LLC d/b/a aha!' -> 'ExpressJet Airlines'."""
    s = re.sub(r"\s+d/b/a.*$", "", description.strip(), flags=re.I)
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"[\s,]+(Inc\.?|Co\.?|LLC|Corp\.?|Ltd\.?|Company)$", "", s, flags=re.I)
    return s.strip()


def _airport_with_suffix(name):
    name = name.strip()
    if re.search(r"(airport|airfield|field|strip|base|heliport|landing|seaplane)$", name, re.I):
        return name
    return name + " Airport"


class Places:
    def __init__(self, data_dir=DATA_DIR, airports_rows=None):
        ref = {r["Code"]: r["Description"] for r in read_rows("ref_airports.csv", data_dir)}
        rows = airports_rows if airports_rows is not None else read_rows("airports.csv", data_dir)
        self.info = {}
        self.groups = {}
        for r in rows:
            code = r["airport"]
            desc = ref.get(code, "")
            left, _, airport = desc.partition(":")
            city, _, st = left.rpartition(",")
            if not city:
                city, st = left, ""
            city, st = city.strip() or code, st.strip()
            self.info[code] = {
                "code": code, "city": city, "state_code": st, "state": STATE_NAMES.get(st, st),
                "airport": _airport_with_suffix(airport) if airport.strip() else code,
                "departures": int(float(r["total_departures"])),
            }
            self.groups.setdefault((city, st), []).append(code)
        for codes in self.groups.values():
            codes.sort(key=lambda c: -self.info[c]["departures"])

    # ----- labels
    def city(self, code):
        i = self.info.get(code)
        if not i:
            return code
        if i["state_code"] == "DC":
            return "Washington, D.C."
        return "%s, %s" % (i["city"], i["state"]) if i["state"] else i["city"]

    def is_shared_city(self, code):
        i = self.info.get(code)
        if not i:
            return False
        busy = [c for c in self.groups[(i["city"], i["state_code"])]
                if self.info[c]["departures"] >= BUSY_AIRPORT_DEPARTURES]
        return len(busy) >= 2 and code in busy

    def label(self, code):
        """Readable name: 'Atlanta, Georgia', or 'Chicago, Illinois (Chicago O'Hare International Airport)'."""
        i = self.info.get(code)
        if not i:
            return code
        if self.is_shared_city(code):
            return "%s (%s)" % (self.city(code), i["airport"])
        return self.city(code)

    def airport(self, code):
        i = self.info.get(code)
        return i["airport"] if i else code

    def route(self, origin, dest):
        return "%s to %s" % (self.label(origin), self.label(dest))

    def route_from_key(self, key):
        o, _, d = key.partition("-")
        return self.route(o, d)

    def group_codes(self, code):
        i = self.info.get(code)
        return list(self.groups[(i["city"], i["state_code"])]) if i else [code]
