"""A small, honest question-answering assistant for FlightPulse.

It is NOT a general AI. It reads a question, works out which city / airline / route /
reason / year it is about and what kind of question it is, then answers ONLY from the
numbers the Hadoop jobs produced (see store.py). Every answer says where its numbers
came from, and anything it cannot answer gets a polite "try one of these" instead of
a guess. No third-party imports, so it is unit-tested like any other module.
"""
import re
from dataclasses import dataclass, field

import content as C
from store import CANCEL_KEYS, CAUSE_KEYS, Store, combine

RED, GREEN, BLUE, AMBER = "#d64545", "#2e9d5b", "#2f6fd0", "#e09a2b"

CAUSE_LABEL = {k: label for k, label, _ in C.CAUSES}
CAUSE_SHORT = {"carrier": "the airline's own problems", "late_aircraft": "the plane arriving late from its last trip",
               "nas": "busy skies and airport operations", "weather": "bad weather", "security": "security problems"}
CANCEL_FOR_CAUSE = {"carrier": "a_carrier", "weather": "b_weather", "nas": "c_nas", "security": "d_security"}

CAUSE_WORDS = {
    "weather": ["weather", "storm", "storms", "snow", "rain", "fog", "wind", "windy", "hurricane", "hurricanes",
                "blizzard", "thunderstorm", "thunderstorms", "icy", "tornado"],
    "nas": ["traffic", "air traffic", "congestion", "congested", "busy sky", "busy skies", "busy airport", "atc",
            "controller", "controllers", "runway", "airport operations", "crowded"],
    "carrier": ["airline fault", "airline s own", "airlines own", "airline problem", "airline problems", "own fault",
                "crew", "crews", "maintenance", "cleaning", "fueling", "baggage"],
    "security": ["security"],
    "late_aircraft": ["late plane", "late planes", "late aircraft", "late arriving", "previous flight", "earlier flight",
                      "previous trip", "earlier trip", "knock on", "inbound plane"],
}

MIN_OPERATED = {"city": 50000, "airline": 250000, "route": 5000, "airline_at_city": 5000, "route_from_city": 2000}


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower().replace("'", "").replace("’", "")).strip()


def has_phrase(q, phrase):
    return (" %s " % phrase) in (" %s " % q)


@dataclass
class Chart:
    kind: str                    # "hbar" or "vbar"
    title: str
    labels: list
    values: list
    value_title: str
    fmt: str = ".0f"
    color: str = RED
    highlight: list = field(default_factory=list)   # indexes drawn in a stronger colour


@dataclass
class Answer:
    text: str
    chart: Chart = None
    sources: list = field(default_factory=list)
    followups: list = field(default_factory=list)
    understood: bool = True


@dataclass
class Entity:
    kind: str                     # country | place | airline | route | airline_at_place
    label: str
    codes: list = field(default_factory=list)       # airports (place / route origin)
    dest_codes: list = field(default_factory=list)  # route destination airports
    side: str = "origin"
    airline: str = None
    note: str = ""


class Bot:
    def __init__(self, store=None):
        self.S = store or Store()
        self.P = self.S.places
        self._build_place_index()
        self._build_airline_index()
        # A word that is both an airline and part of a place name ("Delta", "Southwest") means the airline;
        # the place is still reachable by its full name (e.g. "Montrose" or "Southwest Florida").
        for clash in set(self.phrases) & set(self.airline_phrases):
            del self.phrases[clash]
        for clash in set(self.airport_phrases) & set(self.airline_phrases):
            del self.airport_phrases[clash]

    # ------------------------------------------------------------------ recognising names
    def _build_place_index(self):
        P = self.P
        self.group_codes = {}
        self.group_departures = {}
        self.phrases = {}                      # phrase -> list of group keys
        self.airport_phrases = {}              # phrase -> [airport code]
        city_tokens = set()
        for key, codes in P.groups.items():
            city = key[0]
            use = [c for c in codes if P.info[c]["departures"] >= 1000] or codes[:1]
            self.group_codes[key] = use
            self.group_departures[key] = sum(P.info[c]["departures"] for c in codes)
            names = {norm(city)}
            for part in re.split(r"[/-]", city):
                if len(norm(part)) >= 4:
                    names.add(norm(part))
            names.add(norm(city) + " " + norm(P.info[codes[0]]["state"]))
            city_tokens.update(norm(city).split())
            for n in names:
                self.phrases.setdefault(n, []).append(key)
        manual = {"nyc": "New York", "new york city": "New York", "la": "Los Angeles", "sf": "San Francisco",
                  "san fran": "San Francisco", "vegas": "Las Vegas", "philly": "Philadelphia", "dc": "Washington",
                  "washington dc": "Washington", "twin cities": "Minneapolis"}
        for phrase, city in manual.items():
            keys = [k for k in P.groups if k[0] == city]
            if keys:
                self.phrases.setdefault(phrase, []).extend(keys)
        generic = {"international", "airport", "regional", "municipal", "national", "memorial", "field", "county",
                   "metropolitan", "intercontinental", "gateway", "airfield", "john", "ronald", "reagan",
                   # everyday words that must never be mistaken for a place when someone asks a question:
                   "cities", "island", "islands", "valley", "mountain", "mountains", "central", "harbor", "beach", "springs",
                   "river", "northern", "southern", "eastern", "western", "greater", "major", "grand", "falls", "tri-state",
                   "general", "colonel", "captain", "sergeant", "airline", "airlines", "flight", "flights", "delays", "delay",
                   "center", "capital", "coast", "coastal", "express", "magic", "metro", "public", "range", "region", "space",
                   "terminal", "university", "golden", "orange", "liberty", "northeast", "northwest", "america", "triangle",
                   "creek", "ridge", "basin", "corners", "isles", "grass", "sweet", "rocky"}
        from places import STATE_NAMES
        state_tokens = {t for name in STATE_NAMES.values() for t in norm(name).split()}
        for code, i in P.info.items():
            for tok in norm(i["airport"]).split():
                if len(tok) >= 5 and tok not in generic and tok not in city_tokens and tok not in state_tokens:
                    self.airport_phrases.setdefault(tok, []).append(code)
        for alias, code in {"jfk": "JFK", "kennedy": "JFK", "laguardia": "LGA", "ohare": "ORD", "midway": "MDW",
                            "newark": "EWR", "dulles": "IAD", "love field": "DAL"}.items():
            if code in P.info:
                self.airport_phrases[alias] = [code]

    def _build_airline_index(self):
        self.airline_phrases = {}
        for code in self.S.carriers_in_data():
            name = self.S.airline_label(code)
            first = norm(name).split()[0] if name else ""
            self.airline_phrases[norm(name)] = code
            if len(first) >= 4 and first not in ("air", "airlines"):
                self.airline_phrases.setdefault(first, code)
        self.airline_phrases["jet blue"] = self.airline_phrases.get("jetblue", self.airline_phrases.get("jetblue airways"))
        self.airline_phrases = {k: v for k, v in self.airline_phrases.items() if v}

    def find_names(self, question):
        """Return (places, airlines): each a list of (position, phrase, payload) in reading order."""
        q = " %s " % norm(question)
        taken = []
        hits = []

        def free(a, b):
            return all(b <= s or a >= e for s, e in taken)

        cands = []
        for p, keys in self.phrases.items():
            cands.append((p, "place", keys))
        for p, codes in self.airport_phrases.items():
            cands.append((p, "airport", codes))
        for p, code in self.airline_phrases.items():
            cands.append((p, "airline", code))
        for p, kind, payload in sorted(cands, key=lambda c: -len(c[0])):
            if kind == "airline" and p == "united" and " united states " in q:
                continue
            for m in re.finditer(r"(?<= )%s(?= )" % re.escape(p), q):
                if free(m.start(), m.end()):
                    taken.append((m.start(), m.end()))
                    hits.append((m.start(), p, kind, payload))
        for m in re.finditer(r"\b([A-Z]{3})\b", question):          # airport codes only when typed in capitals
            code = m.group(1)
            if code in self.P.info and not any(h[2] == "airport" and h[3] == [code] for h in hits):
                hits.append((q.find(" " + code.lower() + " ") if (" " + code.lower() + " ") in q else 10**6, code, "airport", [code]))
        hits.sort(key=lambda h: h[0])
        places, airlines = [], []
        for pos, phrase, kind, payload in hits:
            if kind == "airline":
                airlines.append((pos, phrase, payload))
            elif kind == "airport":
                places.append((pos, phrase, self._airport_entity(payload[0])))
            else:
                places.append((pos, phrase, self._group_entity(payload)))
        return places, airlines, q

    def _airport_entity(self, code):
        return Entity("place", self.P.label(code), [code])

    def _group_entity(self, keys):
        keys = list(dict.fromkeys(keys))
        if len(keys) > 1 and len({k[1] for k in keys}) == 1:        # several groups, same state (e.g. Dallas + Dallas/Fort Worth)
            codes = [c for k in keys for c in self.group_codes[k]]
            label = ", ".join(sorted({k[0] for k in keys}))
            return Entity("place", "%s, %s" % (keys[0][0], self.P.info[codes[0]]["state"]), codes,
                          note="all the airports around %s combined" % keys[0][0])
        key = max(keys, key=lambda k: self.group_departures[k])
        note = ""
        if len(keys) > 1:
            others = ", ".join("%s, %s" % (k[0], self.P.info[self.group_codes[k][0]]["state"]) for k in keys if k != key)
            note = "I assumed the busiest one. If you meant %s, include the state in your question." % others
        codes = self.group_codes[key]
        label = self.P.city(codes[0])
        if len(codes) > 1:
            note = ("all %d airports in this city combined: %s. " % (len(codes), ", ".join(self.P.airport(c) for c in codes))) + note
        return Entity("place", label, codes, note=note.strip())

    # ------------------------------------------------------------------ names we do NOT recognise
    PLACE_PREPS = {"leaving", "from", "in", "at", "into", "arriving", "near", "around", "departing"}
    NOT_A_NAME = {"the", "a", "an", "this", "that", "these", "those", "each", "every", "all", "any", "general", "total", "overall", "us", "usa",
                  "america", "american", "country", "nation", "nationwide", "order", "particular", "spring", "summer", "fall", "autumn", "winter",
                  "week", "month", "year", "years", "day", "days", "night", "evening", "morning", "afternoon", "weekend", "weekends", "holiday",
                  "holidays", "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
                  "december", "bad", "good", "heavy", "peak", "rush", "hour", "hours", "time", "times", "which", "what", "there", "here", "it",
                  "them", "total", "average", "most", "least", "both", "flight", "flights", "plane", "planes", "trip", "trips", "2020", "2021"}
    NOT_A_NAME_PREFIX = ("cancel", "divert", "delay", "late", "flight", "airport", "airline", "route", "city", "cities", "weather", "storm",
                         "snow", "traffic", "secur", "crew", "mainten")

    def unknown_name(self, q, known_tokens):
        """A word right after 'in / from / leaving / at ...' that is not a recognised place, airline or ordinary word."""
        toks = q.split()
        for i, t in enumerate(toks[:-1]):
            if t in self.PLACE_PREPS:
                nxt = toks[i + 1]
                if (nxt in self.NOT_A_NAME or nxt.isdigit() or nxt in known_tokens or len(nxt) < 3
                        or nxt.startswith(self.NOT_A_NAME_PREFIX)):
                    continue
                return nxt
        return None

    def state_in(self, q):
        from places import STATE_NAMES
        for code, name in STATE_NAMES.items():
            if code not in ("DC", "PR", "VI", "GU", "AS", "MP") and has_phrase(q, norm(name)):
                return code, name
        return None

    def not_found_answer(self, what):
        return Answer("I could not find **%s** among the cities, airlines or routes in this data (US airports, 2020 to mid-2025). "
                      "Try the name of a larger US city or an airline." % what, understood=False, followups=self.starter_questions()[:3])

    def state_answer(self, code, name):
        P = self.P
        cities = sorted((c for c in P.info if P.info[c]["state_code"] == code), key=lambda c: -P.info[c]["departures"])[:4]
        names = ", ".join(dict.fromkeys(P.info[c]["city"] for c in cities))
        return Answer("I answer by **city, airline or route**, not by state. In %s the busiest cities in this data are %s. Ask about one of them, "
                      "for example: *Why are flights late in %s?*" % (name, names, P.info[cities[0]]["city"]),
                      understood=False, followups=["Why are flights late in %s?" % P.info[cities[0]]["city"],
                                                   "How many flights were cancelled leaving %s?" % P.info[cities[0]]["city"]] + self.starter_questions()[:1])

    # ------------------------------------------------------------------ main entry
    SEASON_WORDS = {"winter", "summer", "spring", "fall", "autumn", "january", "february", "march", "april", "june", "july", "august",
                    "september", "october", "november", "december", "holiday", "holidays", "christmas", "thanksgiving", "weekend", "weekends"}

    def ask(self, question):
        ans = self._ask(question)
        words = set(norm(question or "").split())
        if ans.understood and ans.text and words & self.SEASON_WORDS and ans.chart is not None:
            ans.text += ("\n\n_I can't split cities, airlines or routes by season or month, so this covers all of 2020 to mid-2025. "
                         "The **When and why** page shows the month-by-month pattern for the whole country._")
        return ans

    def _ask(self, question):
        question = (question or "").strip()
        if not question:
            return self.help_answer()
        places, airlines, q = self.find_names(question)
        year = None
        m = re.search(r"\b(2020|2021|2022|2023|2024|2025)\b", q)
        if m:
            year = m.group(1)
        cause = self.detect_cause(question, q)
        words = set(q.split())
        cancel = any(w.startswith("cancel") for w in words)
        divert = any(w.startswith("divert") for w in words)
        asc = bool(words & {"least", "fewest", "best", "lowest", "fewer", "smallest", "safest", "better"}) and not ("how many" in q)
        wants_rate = bool(words & {"rate", "percent", "percentage", "share", "likely", "chance", "proportion"}) or "per 100" in q or "out of 100" in q
        greeting = words & {"hello", "hi", "hey", "help", "thanks", "thank"} or "what can you" in q

        if greeting and not places and not airlines and not cause:
            return self.help_answer()

        side = "origin"
        origin_e = dest_e = None
        if len(places) >= 2:
            origin_e, dest_e = places[0][2], places[1][2]
        elif len(places) == 1:
            pos, phrase, ent = places[0]
            before = q[:pos].split()[-3:]
            if set(before) & {"to", "into", "arriving", "arrive", "arrives", "landing", "land", "lands", "arrivals"}:
                side = "dest"
        carry_q = ("next" in words and bool(words & {"late", "delay", "delayed"})) or bool(
            re.search(r"\bcarr(y|ies|ied|ying) ?over\b|\bpass(es|ed)?\s+(\w+\s+){0,2}on\b|chain reaction|knock on", q))

        # ---- decide what the question is about
        ent = None
        if origin_e and dest_e:
            ent = Entity("route", "%s to %s" % (origin_e.label, dest_e.label), origin_e.codes, dest_e.codes)
            ent.note = " ".join(n for n in (origin_e.note, dest_e.note) if n)
        elif places and airlines:
            p = places[0][2]
            ent = Entity("airline_at_place", "%s at %s" % (self.S.airline_label(airlines[0][2]), p.label), p.codes,
                         airline=airlines[0][2], note=p.note)
        elif places:
            ent = places[0][2]
            ent.side = side
        elif airlines:
            ent = Entity("airline", self.S.airline_label(airlines[0][2]), airline=airlines[0][2])
        elif len(airlines) == 0 and not places:
            ent = None

        if ent is None and not (words & {"compare", "versus", "vs"}):
            st = self.state_in(q)
            if st:
                return self.state_answer(*st)
            known = set(t for _, ph, _ in places for t in ph.split()) | set(t for _, ph, _ in airlines for t in ph.split())
            unknown = self.unknown_name(q, known)
            if unknown:
                return self.not_found_answer(unknown.capitalize())
        ranking_words = bool(words & {"which", "what", "who", "top", "worst", "best", "most", "rank", "ranking", "highest", "lowest", "least", "fewest"})
        two_airlines = len(airlines) >= 2 and not places
        two_places_compare = len(places) >= 2 and bool(words & {"compare", "versus", "vs", "difference"})

        # ---- route special: best airline / best time
        if ent is not None and ent.kind == "route" and (words & {"best", "when", "time", "airline", "airlines", "fly", "flight"}) and not cause and not carry_q and not cancel:
            return self.route_advice(ent)
        if two_airlines or two_places_compare:
            return self.compare(places, airlines, year)
        if carry_q:
            if ent is None and (ranking_words or self.rank_target(words, q)):
                return self.carry_rank(self.rank_target(words, q) or "airline")
            return self.carryover_answer(ent)

        # ---- ranking when no single entity was named (or when asking which X at/from a place)
        wants_which = bool(words & {"which", "what", "who", "top", "worst", "best", "most", "rank", "ranking", "highest", "lowest", "least", "fewest"})
        target = self.rank_target(words, q)
        if (ent is None and (wants_which or target)) or (ent is not None and ent.kind in ("place", "airline") and wants_which and target and target != ent.kind.replace("place", "city")):
            return self.rank_answer(target or "city", cause, cancel, divert, asc, wants_rate, year, within=ent)

        if ent is None:
            if (words & {"when", "time", "hour", "day", "month", "weekday"} or "what time" in q) and not (cause or cancel or divert):
                return self.when_answer(asc)
            ent = self.national_entity(year)

        # ---- a named entity: why / how many / profile
        if "why" in words or "reasons" in words or "reason" in words or ("cause" in q and not cause):
            return self.cause_breakdown(ent, year)
        if cancel:
            return self.cancel_answer(ent, cause, year)
        if divert:
            return self.divert_answer(ent, year)
        if cause:
            return self.cause_count(ent, cause, year)
        return self.profile(ent, year)

    # ------------------------------------------------------------------ small parsers
    def detect_cause(self, question, q):
        if re.search(r"(because of|due to|caused by|blame|fault of)( the)? (airline|carrier)", q) or "airline fault" in q:
            return "carrier"
        for key, words in CAUSE_WORDS.items():
            for w in words:
                if has_phrase(q, norm(w)):
                    return key
        return None

    def rank_target(self, words, q):
        if words & {"airline", "airlines", "carrier", "carriers"}:
            return "airline"
        if words & {"route", "routes"} or "flight path" in q:
            return "route"
        if words & {"city", "cities", "airport", "airports", "place", "places", "location", "locations"}:
            return "city"
        return None

    def national_entity(self, year=None):
        row = self.S.causes.get(("YEAR", year)) if year else self.S.national()
        return Entity("country", "the United States", [])

    # ------------------------------------------------------------------ data for an entity
    def row_for(self, ent, year=None):
        S = self.S
        note = ""
        if ent.kind == "country":
            return (S.causes.get(("YEAR", year)) if year else S.national()), note
        if ent.kind == "place":
            row = S.place_row(ent.codes, ent.side, year if ent.side == "origin" else None)
            if year and ent.side == "dest":
                note = "Year-by-year numbers are only available for flights leaving a city, so this covers all years."
            return row, note
        if ent.kind == "airline":
            return S.airline_row(ent.airline, year), note
        if ent.kind == "route":
            rows = [S.route_row("%s-%s" % (o, d)) for o in ent.codes for d in ent.dest_codes]
            rows = [r for r in rows if r]
            if year:
                note = "Year-by-year numbers are not available for single routes, so this covers 2020 to mid-2025."
            return (combine(rows) if rows else None), note
        if ent.kind == "airline_at_place":
            rows = [S.airline_at_city(ent.airline, c) for c in ent.codes]
            rows = [r for r in rows if r]
            if year:
                note = "Year-by-year numbers are not available for an airline at one city, so this covers 2020 to mid-2025."
            return (combine(rows) if rows else None), note
        return None, note

    def side_words(self, ent):
        return "arriving at" if ent.kind == "place" and ent.side == "dest" else ("leaving" if ent.kind == "place" else "on")

    def scope_text(self, ent, year):
        base = ent.label
        if ent.kind == "place":
            base = "%s %s" % (self.side_words(ent), ent.label)
        elif ent.kind == "route":
            base = "on the route %s" % ent.label
        elif ent.kind == "airline":
            base = "for %s" % ent.label
        elif ent.kind == "airline_at_place":
            base = "for %s" % ent.label
        elif ent.kind == "country":
            base = "in " + ent.label
        return base + ((" in %s" % year) if (year and ent.kind in ("place", "airline", "country") and not (ent.kind == "place" and ent.side == "dest")) else "")

    def sources_for(self, ent):
        base = {"country": "DelayCauseMetricsJob (rows ALL / YEAR)", "airline": "DelayCauseMetricsJob (rows CARRIER / CARRIERYEAR)",
                "route": "DelayCauseMetricsJob (rows ROUTE)", "airline_at_place": "DelayCauseMetricsJob (rows CARRIERORIGIN)"}
        if ent.kind == "place":
            return ["DelayCauseMetricsJob (rows %s)" % ("DEST" if ent.side == "dest" else "ORIGIN / ORIGINYEAR")]
        return [base[ent.kind]]

    def no_data(self, ent, year=None):
        return Answer("I could not find any flights for %s%s in the data. Try another city or airline." % (
            ent.label, " in %s" % year if year else ""), understood=False, followups=self.starter_questions()[:3])

    # ------------------------------------------------------------------ answer builders
    def cause_chart(self, row, title, highlight=None):
        keys = sorted(CAUSE_KEYS, key=lambda k: -row["flights_" + k])
        return Chart("hbar", title, [CAUSE_SHORT[k].capitalize() for k in keys], [int(row["flights_" + k]) for k in keys],
                     "Late flights where this was one of the reasons", ",.0f", RED,
                     [keys.index(highlight)] if highlight in keys else [])

    def follow_for(self, ent):
        l = ent.label
        if ent.kind == "place":
            return ["Why are flights late %s %s?" % (self.side_words(ent), l), "Do late planes pass it on at %s?" % l,
                    "Which airline is worst at %s?" % l]
        if ent.kind == "airline":
            return ["Why are %s flights late?" % l, "Do late planes pass it on for %s?" % l, "Which city is worst for %s?" % l]
        if ent.kind == "route":
            return ["What is the best time to fly %s?" % l, "Which airline is best on %s?" % l]
        return self.starter_questions()[:3]

    def profile(self, ent, year=None):
        row, note = self.row_for(ent, year)
        if not row:
            return self.no_data(ent, year)
        late = C.per100_value(row["delayed_15plus_rate"])
        canc = C.per100_value(row["cancellation_rate"])
        text = ("**%s**: from 2020 to mid-2025, %s flights %s flew. About **%s out of every 100 arrived 15 or more minutes late** "
                "and about **%s out of every 100 planned flights were cancelled**." % (
                    ent.label.capitalize() if ent.kind == "country" else ent.label, C.big_count(row["n_operated"]),
                    self.side_words(ent) if ent.kind == "place" else "involving this", late, canc))
        if ent.kind == "country":
            text = ("**The United States**%s: %s flights flew. About **%s out of every 100 arrived 15 or more minutes late** and about **%s out of "
                    "every 100 planned flights were cancelled**." % (" in %s" % year if year else " from 2020 to mid-2025", C.big_count(row["n_operated"]), late, canc))
        text += self.extra_notes(ent, note)
        return Answer(text, self.cause_chart(row, "Why the late flights were late (flights, by reason)"), self.sources_for(ent),
                      self.follow_for(ent))

    def extra_notes(self, ent, note):
        out = ""
        if ent.note:
            out += "\n\n_Note: %s_" % ent.note
        if note:
            out += "\n\n_Note: %s_" % note
        return out

    def cause_count(self, ent, cause, year=None):
        row, note = self.row_for(ent, year)
        if not row:
            return self.no_data(ent, year)
        n, late = int(row["flights_" + cause]), int(row["n_delayed_15plus"])
        share = n / late if late else 0
        text = ("**%s** late flights %s had **%s** listed as a reason. That is about **%s of every 100 late flights** there (%s late flights in all)." % (
            "{:,}".format(n), self.scope_text(ent, year), CAUSE_SHORT[cause], C.per100_value(share), "{:,}".format(late)))
        if cause == "weather":
            text += ("\n\n_What counts as weather: the airlines only list **extreme** weather (storms, snow, hurricanes) under weather. "
                     "Ordinary bad weather and its knock-on effects are counted as \"busy skies and airport operations\"._")
        elif cause == "late_aircraft":
            text += "\n\n_This means the same plane was late on its trip before, so it started this trip late._"
        text += "\n\n_A late flight can have several reasons at once, so the reasons in the chart add up to more than the number of late flights._"
        text += self.extra_notes(ent, note)
        return Answer(text, self.cause_chart(row, "Late flights by reason, %s" % self.scope_text(ent, year), cause), self.sources_for(ent),
                      self.follow_for(ent))

    def national_cause_count(self, cause, year=None):
        return self.cause_count(self.national_entity(year), cause, year)

    def cause_breakdown(self, ent, year=None):
        row, note = self.row_for(ent, year)
        if not row:
            return self.no_data(ent, year)
        keys = sorted(CAUSE_KEYS, key=lambda k: -row["share_" + k])
        top, second = keys[0], keys[1]
        scope = self.scope_text(ent, year)
        if ent.kind == "place":
            scope = "on flights " + scope
        text = ("Of all the minutes of lateness %s, **%s%%** came from **%s** and **%s%%** from **%s**." % (
            scope, round(row["share_" + top] * 100), CAUSE_SHORT[top], round(row["share_" + second] * 100), CAUSE_SHORT[second]))
        text += self.extra_notes(ent, note)
        chart = Chart("hbar", "Share of all lateness (minutes) by reason", [CAUSE_SHORT[k].capitalize() for k in keys],
                      [round(row["share_" + k] * 100, 1) for k in keys], "Share of all minutes of lateness (%)", ".0f", RED, [0])
        return Answer(text, chart, self.sources_for(ent), self.follow_for(ent))

    def cancel_answer(self, ent, cause, year=None):
        row, note = self.row_for(ent, year)
        if not row:
            return self.no_data(ent, year)
        labels = [lab for _, lab in C.CANCEL_REASONS]
        vals = [int(row["cancel_code_" + k]) for k in CANCEL_KEYS]
        if cause in CANCEL_FOR_CAUSE:
            k = CANCEL_FOR_CAUSE[cause]
            n = int(row["cancel_code_" + k])
            text = ("**%s** flights %s were cancelled because of **%s** (out of %s cancelled flights in all)." % (
                "{:,}".format(n), self.scope_text(ent, year), dict(C.CANCEL_REASONS)[k].lower(), "{:,}".format(int(row["n_cancelled"]))))
            hi = [CANCEL_KEYS.index(k)]
        else:
            text = ("**%s** flights %s were cancelled: about **%s out of every 100** planned flights." % (
                "{:,}".format(int(row["n_cancelled"])), self.scope_text(ent, year), C.per100_value(row["cancellation_rate"])))
            hi = [max(range(4), key=lambda i: vals[i])]
        if cause == "late_aircraft":
            text += "\n\n_Cancellations do not have a \"late plane\" reason, so here is the full list of cancellation reasons._"
        if ent.kind == "country" or year in (None, "2020"):
            text += "\n\n_Careful: in 2020 most cancellations are recorded as \"security\", which looks like how they were recorded that pandemic year, not real security events._"
        text += self.extra_notes(ent, note)
        chart = Chart("hbar", "Why flights were cancelled", labels, vals, "Cancelled flights", ",.0f", AMBER, hi)
        return Answer(text, chart, self.sources_for(ent), self.follow_for(ent))

    def divert_answer(self, ent, year=None):
        row, note = self.row_for(ent, year)
        if not row:
            return self.no_data(ent, year)
        text = ("**%s** flights %s were sent to a different airport than planned (diverted): about **%s out of every 100** planned flights." % (
            "{:,}".format(int(row["n_diverted"])), self.scope_text(ent, year), C.per100_value(row["diversion_rate"])))
        text += self.extra_notes(ent, note)
        return Answer(text, None, self.sources_for(ent), self.follow_for(ent))

    # ---- carryover
    def carryover_for(self, ent):
        S = self.S
        if ent is None or ent.kind == "country":
            return S.carryover_row("ALL"), "the whole country"
        if ent.kind == "airline":
            return S.carryover_row("CARRIER", ent.airline), ent.label
        if ent.kind == "place":
            rows = [S.carryover_row("AIRPORT", c) for c in ent.codes]
            rows = [r for r in rows if r]
            if not rows:
                return None, ent.label
            if len(rows) == 1:
                return rows[0], ent.label
            tot = sum(r["n_a_late15"] for r in rows)
            n = sum(r["n_links"] for r in rows)
            return {"n_links": n, "n_a_late15": tot,
                    "p_b_late15_given_a_late15": sum(r["p_b_late15_given_a_late15"] * r["n_a_late15"] for r in rows) / (tot or 1),
                    "p_b_late15_given_a_not_late15": sum(r["p_b_late15_given_a_not_late15"] * r["n_a_not_late15"] for r in rows) / (sum(r["n_a_not_late15"] for r in rows) or 1),
                    "mean_carryover_min": sum(r["mean_carryover_min"] * r["n_links"] for r in rows) / (n or 1)}, ent.label
        return None, ent.label

    def carryover_answer(self, ent):
        row, name = self.carryover_for(ent)
        if not row:
            return Answer("I do not have enough connecting flights to say anything about %s. Try a bigger city or an airline." % (ent.label if ent else "that"),
                          understood=False, followups=self.starter_questions()[:3])
        where = "landed late at %s" % name if ent is not None and ent.kind == "place" else "landed late"
        text = ("When a plane **%s**, its next trip left 15 or more minutes late **%s times out of 100**. When it landed on time, only **%s out of 100** did. "
                "Based on %s plane-to-next-trip pairs." % (
                    where + ((" (flying for %s)" % name) if ent is not None and ent.kind == "airline" else ""),
                    C.per100_value(row["p_b_late15_given_a_late15"]), C.per100_value(row["p_b_late15_given_a_not_late15"]), C.big_count(row["n_links"])))
        text += ("\n\n_This shows late planes and late next trips go together. It does not prove one caused the other: weather or a busy airport can make both late. "
                 "The numbers assume a plane needs about 30 minutes on the ground between flights._")
        chart = Chart("vbar", "Next trip leaves 15+ minutes late (per 100)", ["After a LATE landing", "After an ON-TIME landing"],
                      [round(row["p_b_late15_given_a_late15"] * 100, 1), round(row["p_b_late15_given_a_not_late15"] * 100, 1)],
                      "Per 100 next trips", ".1f", RED, [0])
        return Answer(text, chart, ["CarryoverAnalysisJob (rows %s)" % ("CARRIER" if ent is not None and ent.kind == "airline" else "AIRPORT" if ent is not None and ent.kind == "place" else "ALL")],
                      self.follow_for(ent) if ent is not None else self.starter_questions()[:3])

    # ---- route advice
    def route_advice(self, ent):
        S = self.S
        rcs = [r for r in S.route_carrier if r["kind"] == "RC" and any(r["route"] == "%s-%s" % (o, d) for o in ent.codes for d in ent.dest_codes) and r["total_flights"] >= 1000]
        if not rcs:
            return Answer("There are not enough flights on %s to compare airlines fairly (we need at least 1,000 per airline)." % ent.label,
                          understood=False, followups=self.starter_questions()[:3])
        rcs.sort(key=lambda r: r["arr_delay_rate"])
        best = rcs[0]
        bands = [r for r in S.route_carrier if r["kind"] == "RCB" and any(r["route"] == "%s-%s" % (o, d) for o in ent.codes for d in ent.dest_codes) and r["total_flights"] >= 1000]
        bands.sort(key=lambda r: r["arr_delay_rate"])
        text = "On **%s**, **%s** arrived late least often: about **%s out of every 100** flights." % (
            ent.label, S.airline_label(best["carrier"]), C.per100_value(best["arr_delay_rate"]))
        if bands:
            g = bands[0]
            text += " The best airline-and-time combination was **%s in the %s** (about %s in 100 late)." % (
                S.airline_label(g["carrier"]), C.BAND_LABEL[g["band"]].split(" (")[0].lower(), C.per100_value(g["arr_delay_rate"]))
        text += self.extra_notes(ent, "") + "\n\n_This is how the route went from 2020 to mid-2025, not a promise about your flight._"
        chart = Chart("hbar", "Late flights per 100, by airline", [S.airline_label(r["carrier"]) for r in rcs],
                      [round(r["arr_delay_rate"] * 100, 1) for r in rcs], "Late per 100 flights that flew", ".1f", RED, [0])
        return Answer(text, chart, ["RouteCarrierMetricsJob (rows RC / RCB)"], ["Why are flights late on %s?" % ent.label] + self.starter_questions()[:2])

    # ---- compare
    def compare(self, places, airlines, year):
        ents = []
        if len(airlines) >= 2:
            ents = [Entity("airline", self.S.airline_label(a[2]), airline=a[2]) for a in airlines[:2]]
        elif len(places) >= 2:
            ents = [p[2] for p in places[:2]]
        rows = [self.row_for(e, year)[0] for e in ents]
        if len(ents) < 2 or not all(rows):
            return self.help_answer()
        a, b = ents
        ra, rb = rows
        text = ("**%s**: %s out of every 100 flights arrived late and %s out of 100 were cancelled.\n\n**%s**: %s out of 100 late and %s out of 100 cancelled." % (
            a.label, C.per100_value(ra["delayed_15plus_rate"]), C.per100_value(ra["cancellation_rate"]),
            b.label, C.per100_value(rb["delayed_15plus_rate"]), C.per100_value(rb["cancellation_rate"])))
        chart = Chart("hbar", "Late flights per 100 (flights that flew)", [a.label, b.label],
                      [round(ra["delayed_15plus_rate"] * 100, 1), round(rb["delayed_15plus_rate"] * 100, 1)], "Late per 100", ".1f", RED, [])
        return Answer(text, chart, ["DelayCauseMetricsJob"], self.starter_questions()[:3])

    # ---- national "when"
    def when_answer(self, asc):
        hrs = [r for r in self.S.temporal if r["dimension"] == "HOUR"]
        hrs.sort(key=lambda r: r["value"])
        best = min(hrs, key=lambda r: r["arr_delay_rate"])
        worst = max(hrs, key=lambda r: r["arr_delay_rate"])
        text = ("Flights planned to take off around **%s** were late least often (about %s out of 100). Around **%s** they were late most often (about %s out of 100)." % (
            C.hour_label(best["value"]), C.per100_value(best["arr_delay_rate"]), C.hour_label(worst["value"]), C.per100_value(worst["arr_delay_rate"])))
        chart = Chart("vbar", "Late flights per 100 by planned take-off hour", [C.hour_label(r["value"]) for r in hrs],
                      [round(r["arr_delay_rate"] * 100, 1) for r in hrs], "Late per 100", ".0f", RED,
                      [hrs.index(worst)])
        return Answer(text, chart, ["TemporalMetricsJob (rows HOUR)"], ["Which airline is best on time?", "Which city has the most late flights?"])

    # ---- ranking
    PLURAL = {"city": "cities", "airline": "airlines", "route": "routes"}

    def metric_for(self, kind, cause, cancel, divert, wants_rate):
        """Return (count_fn, rate_fn, count_label, rate_verb, base_col). Rate sentences read:
        'about X out of every 100 flights <rate_verb>'."""
        if cancel:
            if cause in CANCEL_FOR_CAUSE:
                k = "cancel_code_" + CANCEL_FOR_CAUSE[cause]
                return (lambda r: r[k], lambda r: r[k] / (r["n_flights_scheduled"] or 1),
                        "flights cancelled because of %s" % CAUSE_SHORT[cause], "were cancelled because of %s" % CAUSE_SHORT[cause], "n_flights_scheduled")
            return (lambda r: r["n_cancelled"], lambda r: r["cancellation_rate"], "cancelled flights", "were cancelled", "n_flights_scheduled")
        if divert:
            return (lambda r: r["n_diverted"], lambda r: r["diversion_rate"], "diverted flights", "were diverted", "n_flights_scheduled")
        if cause:
            k = "flights_" + cause
            return (lambda r: r[k], lambda r: r[k] / (r["n_operated"] or 1), "late flights that had %s as a reason" % CAUSE_SHORT[cause],
                    "were late with %s as a reason" % CAUSE_SHORT[cause], "n_operated")
        return (lambda r: r["n_delayed_15plus"], lambda r: r["delayed_15plus_rate"], "late flights", "were late", "n_operated")

    def rank_answer(self, target, cause, cancel, divert, asc, wants_rate, year, within=None):
        S = self.S
        count_fn, rate_fn, count_label, rate_verb, base_col = self.metric_for(target, cause, cancel, divert, wants_rate)
        rows, where, min_n, src = [], "", 0, ""
        if target == "city":
            if within is not None and within.kind == "airline":
                rows = [r | {"_name": S.places.label(r["airport"])} for r in S.cities_for_airline(within.airline, MIN_OPERATED["airline_at_city"])]
                where, min_n, src = "for %s" % within.label, MIN_OPERATED["airline_at_city"], "CARRIERORIGIN"
            else:
                key = "ORIGINYEAR" if year else "ORIGIN"
                for (dim, val), r in S.causes.items():
                    if dim == key and (not year or val.endswith("|" + year)):
                        rows.append(r | {"_name": S.places.label(val.split("|")[0])})
                min_n, src = MIN_OPERATED["city"] * (1 if not year else 0.2), "ORIGIN" + ("YEAR" if year else "")
        elif target == "airline":
            if within is not None and within.kind == "place":
                rows = [r | {"_name": S.airline_label(r["carrier"])} for c in within.codes for r in S.airlines_at(c, MIN_OPERATED["airline_at_city"])]
                where, min_n, src = "at %s" % within.label, MIN_OPERATED["airline_at_city"], "CARRIERORIGIN"
            else:
                key = "CARRIERYEAR" if year else "CARRIER"
                for (dim, val), r in S.causes.items():
                    if dim == key and (not year or val.endswith("|" + year)):
                        rows.append(r | {"_name": S.airline_label(val.split("|")[0])})
                min_n, src = MIN_OPERATED["airline"] * (1 if not year else 0.2), "CARRIER" + ("YEAR" if year else "")
        else:
            if within is not None and within.kind == "place":
                rts = []
                for c in within.codes:
                    rts += S.routes_to(c) if within.side == "dest" else S.routes_from(c)
                rows = [r | {"_name": S.places.route_from_key(r["route"])} for r in rts]
                where, min_n, src = "%s %s" % ("into" if within.side == "dest" else "out of", within.label), MIN_OPERATED["route_from_city"], "ROUTE"
            else:
                rows = [r | {"_name": S.places.route_from_key(val)} for (dim, val), r in S.causes.items() if dim == "ROUTE"]
                min_n, src = MIN_OPERATED["route"], "ROUTE"
        if not rows:
            return Answer("I do not have enough data to rank that. Try asking about cities, airlines or routes.", understood=False,
                          followups=self.starter_questions()[:3])
        subject = target + ((" " + where) if where else "")
        plural = self.PLURAL[target] + ((" " + where) if where else "")
        qualified = [r for r in rows if r[base_col] >= min_n]
        year_note = ""
        if target == "route" and year:
            year_note = "\n\n_Routes can't be split by year, so this covers 2020 to mid-2025._"
        floor = "{:,}".format(int(min_n))
        src_list = ["DelayCauseMetricsJob (rows %s)" % src]
        chart_title = "Out of every 100 flights, the number that %s" % rate_verb

        if asc:                                   # "best / fewest": lowest SHARE among reasonably sized ones
            pool = sorted(qualified, key=rate_fn)[:10]
            if not pool:
                return Answer("There are not enough flights to compare fairly.", understood=False, followups=self.starter_questions()[:3])
            lead = pool[0]
            text = "Among %s with at least %s flights, **%s** has the lowest share: about **%s out of every 100** flights %s." % (
                plural, floor, lead["_name"], C.per100_value(rate_fn(lead)), rate_verb)
            chart = Chart("hbar", chart_title + " (lowest first)", [r["_name"] for r in pool], [round(rate_fn(r) * 100, 2) for r in pool],
                          "Per 100 flights", ".1f", GREEN, [0])
            return Answer(text + year_note, chart, src_list, self.starter_questions()[:3])

        by_count = sorted(rows, key=count_fn, reverse=True)[:10]
        by_rate = sorted(qualified, key=rate_fn, reverse=True)[:10]
        c_lead, r_lead = by_count[0], (by_rate[0] if by_rate else None)
        if wants_rate and r_lead:
            text = "By share, the %s with the most trouble is **%s**: about **%s out of every 100** flights %s (among %s with at least %s flights)." % (
                subject, r_lead["_name"], C.per100_value(rate_fn(r_lead)), rate_verb, plural, floor)
            text += "\n\nBy number of flights, the leader is **%s** with %s %s." % (c_lead["_name"], "{:,}".format(int(count_fn(c_lead))), count_label)
            chart = Chart("hbar", chart_title, [r["_name"] for r in by_rate], [round(rate_fn(r) * 100, 2) for r in by_rate],
                          "Per 100 flights", ".1f", RED, [0])
        else:
            text = "The %s with the most %s is **%s**: **%s**." % (subject, count_label, c_lead["_name"], "{:,}".format(int(count_fn(c_lead))))
            if r_lead and r_lead["_name"] != c_lead["_name"]:
                text += ("\n\nThat is mostly because it has so many flights. Counting by **share** instead (among %s with at least %s flights), "
                         "**%s** is worst: about %s out of every 100 flights %s." % (plural, floor, r_lead["_name"], C.per100_value(rate_fn(r_lead)), rate_verb))
            chart = Chart("hbar", "Most %s" % count_label, [r["_name"] for r in by_count], [int(count_fn(r)) for r in by_count],
                          "Number of flights", ",.0f", RED, [0])
        return Answer(text + year_note, chart, src_list, self.starter_questions()[:3])

    def carry_rank(self, target):
        """Which airline / city passes lateness on the most (share of next trips that leave late after a late landing)."""
        S = self.S
        if target == "city":
            rows = [(S.places.label(v), r) for (p, d, v), r in S.carryover.items() if p == "G90_T30" and d == "AIRPORT" and r["n_a_late15"] >= 5000]
            noun, plural, src = "city", "cities", "AIRPORT"
        else:
            rows = [(S.airline_label(v), r) for (p, d, v), r in S.carryover.items() if p == "G90_T30" and d == "CARRIER" and r["n_a_late15"] >= 20000]
            noun, plural, src = "airline", "airlines", "CARRIER"
        if not rows:
            return Answer("I do not have enough connecting flights to rank that.", understood=False, followups=self.starter_questions()[:3])
        rows.sort(key=lambda t: -t[1]["p_b_late15_given_a_late15"])
        top = rows[:10]
        nat = S.carryover_row("ALL")
        text = ("The %s that passes lateness on the most is **%s**: after one of its planes lands late, the next trip leaves late **%s times out of 100** "
                "(whole country: %s). Only %ss with plenty of late landings are ranked.\n\n_This shows late planes and late next trips go together; it does not prove one "
                "caused the other._" % (noun, top[0][0], C.per100_value(top[0][1]["p_b_late15_given_a_late15"]),
                                       C.per100_value(nat["p_b_late15_given_a_late15"]), noun))
        chart = Chart("hbar", "Next trip leaves late after a LATE landing (per 100)", [n for n, _ in top],
                      [round(r["p_b_late15_given_a_late15"] * 100, 1) for _, r in top], "Per 100 next trips", ".1f", RED, [0])
        return Answer(text, chart, ["CarryoverAnalysisJob (rows %s)" % src], self.starter_questions()[:3])

    # ------------------------------------------------------------------ help
    def starter_questions(self):
        S = self.S
        names = [S.places.city(c) for c in S.top_airports(8)]
        city = "Chicago, Illinois" if "Chicago, Illinois" in names else names[0]
        return [
            "How many flights were delayed by bad weather leaving %s?" % city,
            "Which city has the most late flights?",
            "Which airline is late most often?",
            "Which route runs late the most?",
            "Why are flights late in Denver?",
            "Does a late plane make the next flight late for Delta Air Lines?",
            "What is the best time to fly from New York to Los Angeles?",
            "How many flights were cancelled because of weather in 2022?",
        ]

    def help_answer(self):
        text = ("I can answer questions about **cities, airlines and routes** using the 34.8 million flights counted by Hadoop (2020 to mid-2025). "
                "Ask about **how many** flights were late or cancelled, **which** city, airline or route is worst, **why** flights are late, "
                "whether a **late plane makes the next trip late**, or the **best time or airline** for a route. You can add a **year** (2020 to 2025) "
                "or a **reason** such as weather, busy skies, or the airline itself.\n\nI only know what is in this data: I can't answer about live flights, tickets, "
                "pilots or passengers.")
        return Answer(text, None, [], self.starter_questions()[:6])
