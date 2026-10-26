"""Tests for full names, the data store, the question-answering assistant and the advice rules.

Expected numbers are read straight from the exported CSV files with plain csv code (not through
Store/Bot), so an answer that disagrees with the Hadoop output fails.
"""
import csv
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import advice  # noqa: E402
import content as C  # noqa: E402
from chatbot import Bot  # noqa: E402
from places import Places, airline_name  # noqa: E402
from store import Store  # noqa: E402

S = Store()
BOT = Bot(S)


def raw(name):
    return list(csv.DictReader(open(os.path.join(C.DATA_DIR, name))))


def causes(dimension, value=""):
    return next(r for r in raw("causes.csv") if r["dimension"] == dimension and r["value"] == value)


class NameTests(unittest.TestCase):
    def test_no_airport_code_is_shown_when_a_name_exists(self):
        P = S.places
        self.assertEqual(P.label("ATL"), "Atlanta, Georgia")
        self.assertEqual(P.label("DCA").split(" (")[0], "Washington, D.C.")
        self.assertEqual(P.label("ORD"), "Chicago, Illinois (Chicago O'Hare International Airport)")
        self.assertNotEqual(P.label("ORD"), P.label("MDW"))           # two Chicago airports are never confused
        self.assertEqual([c for c in P.info if P.label(c) == c], [])   # every airport has a readable name
        self.assertEqual(P.route("ATL", "LAX"), "Atlanta, Georgia to Los Angeles, California")

    def test_airline_names_lose_legal_suffixes(self):
        self.assertEqual(airline_name("Southwest Airlines Co."), "Southwest Airlines")
        self.assertEqual(airline_name("ExpressJet Airlines LLC d/b/a aha!"), "ExpressJet Airlines")
        self.assertEqual(S.airline_label("WN"), "Southwest Airlines")
        self.assertTrue(all(len(v) > 2 for v in S.airlines.values()))


class BotNumberTests(unittest.TestCase):
    def test_weather_delays_leaving_chicago_adds_both_airports(self):
        expect = sum(int(float(causes("ORIGIN", c)["flights_weather"])) for c in ("ORD", "MDW"))
        a = BOT.ask("How many flights were delayed by bad weather leaving Chicago?")
        self.assertIn("{:,}".format(expect), a.text)
        self.assertIsNotNone(a.chart)
        self.assertEqual(max(a.chart.values), max(int(float(causes("ORIGIN", "ORD")["flights_" + k])) + int(float(causes("ORIGIN", "MDW")["flights_" + k])) for k in
                                                  ("carrier", "late_aircraft", "nas", "weather", "security")))
        self.assertIn("extreme", a.text)                               # the "what counts as weather" caveat is shown

    def test_single_airport_by_name_and_year(self):
        ohare = causes("ORIGINYEAR", "ORD|2022")
        a = BOT.ask("How many flights were delayed by weather at O'Hare in 2022?")
        self.assertIn("{:,}".format(int(float(ohare["flights_weather"]))), a.text)      # O'Hare alone, not O'Hare + Midway
        self.assertIn("in 2022", a.text)
        atl = causes("ORIGINYEAR", "ATL|2023")
        a2 = BOT.ask("flights delayed by weather leaving Atlanta in 2023")
        self.assertIn("{:,}".format(int(float(atl["flights_weather"]))), a2.text)

    def test_airline_cancellations_by_weather(self):
        d = causes("CARRIER", "DL")
        a = BOT.ask("How many Delta flights were cancelled because of weather?")
        self.assertIn("{:,}".format(int(float(d["cancel_code_b_weather"]))), a.text)

    def test_ranking_cities_by_count_and_share(self):
        rows = [r for r in raw("causes.csv") if r["dimension"] == "ORIGIN"]
        top = max(rows, key=lambda r: float(r["n_delayed_15plus"]))
        a = BOT.ask("Which city has the most late flights?")
        self.assertIn(S.places.label(top["value"]), a.text)
        self.assertEqual(a.chart.values[0], int(float(top["n_delayed_15plus"])))
        self.assertTrue(all(a.chart.values[i] >= a.chart.values[i + 1] for i in range(len(a.chart.values) - 1)))

    def test_airline_ranking_and_route_ranking(self):
        self.assertIn("late flights", BOT.ask("Which airline is late the most often?").text.lower())
        r = BOT.ask("Which route causes the most delay?")
        self.assertIn(" to ", r.text)
        self.assertEqual(len(r.chart.labels), 10)

    def test_carryover_for_an_airline_matches_hadoop(self):
        row = next(x for x in raw("carryover.csv") if x["params"] == "G90_T30" and x["dimension"] == "CARRIER" and x["value"] == "DL")
        a = BOT.ask("Does a late plane make the next flight late for Delta?")
        self.assertIn(C.per100_value(float(row["p_b_late15_given_a_late15"])), a.text)

    def test_route_advice(self):
        a = BOT.ask("What is the best time to fly from New York to Los Angeles?")
        self.assertIn("New York", a.text)
        self.assertIn("Los Angeles", a.text)
        self.assertIsNotNone(a.chart)

    def test_compare_two_airlines(self):
        a = BOT.ask("Compare Delta and United")
        self.assertIn("Delta Air Lines", a.text)
        self.assertIn("United Air Lines", a.text)

    def test_why_for_a_city_sums_to_a_story(self):
        a = BOT.ask("Why are flights late in Denver?")
        self.assertIn("%", a.text)
        self.assertTrue(abs(sum(a.chart.values) - 100) < 1.0)         # shares of lateness add up to 100%


class BotSafetyTests(unittest.TestCase):
    def test_nonsense_and_empty_get_help_not_a_guess(self):
        for q in ("", "asdf qwerty", "hello"):
            a = BOT.ask(q)
            self.assertTrue(a.followups)                               # always offers something to try
        self.assertNotIn("%s", BOT.ask("asdf qwerty").text)

    def test_unknown_place_does_not_crash(self):
        self.assertTrue(BOT.ask("how many flights were late leaving Atlantis").text)

    def test_all_starter_questions_are_answerable(self):
        for q in BOT.starter_questions():
            a = BOT.ask(q)
            self.assertTrue(a.understood, q)
            self.assertTrue(a.chart is not None or "cancel" in q.lower(), q)

    def test_no_airport_codes_in_answers(self):
        for q in BOT.starter_questions():
            text = BOT.ask(q).text
            for code in ("ORD", "ATL", "JFK", "LAX", "DEN"):
                self.assertNotIn(" %s " % code, text, q)


class AdviceTests(unittest.TestCase):
    def test_every_idea_has_evidence_label_and_numbers(self):
        for code in S.carriers_in_data():
            for idea in advice.airline_ideas(S, code):
                self.assertIn(idea["evidence"], advice.EVIDENCE)
                self.assertTrue(idea["why"] and idea["idea"])
        for codes in ([ "ORD", "MDW"], ["DEN"], ["ATL"]):
            for idea in advice.city_ideas(S, codes, S.place_row(codes)):
                self.assertIn(idea["evidence"], advice.EVIDENCE)

    def test_an_idea_is_only_raised_when_its_reason_is_clearly_above_national(self):
        nat = S.national()
        seen_flagged_city = False
        for code in S.top_airports(60):
            row = S.place_row([code])
            titles = [i["title"] for i in advice.city_ideas(S, [code], row)]
            if row["share_weather"] - nat["share_weather"] < advice.GAP:
                self.assertNotIn("Be ready for bad-weather days", titles, code)
            else:
                seen_flagged_city = True
            if row["share_nas"] - nat["share_nas"] < advice.GAP:
                self.assertNotIn("Spread out the busy hours and protect runway capacity", titles, code)
        self.assertTrue(seen_flagged_city)      # the rule does fire for at least one busy city


class BotRegressionTests(unittest.TestCase):
    """One test per mistake found while building the chatbot, so none can come back."""

    def test_airline_name_beats_a_town_with_the_same_name(self):
        a = BOT.ask("Compare Delta and United")
        self.assertIn("Delta Air Lines", a.text)
        self.assertNotIn("Montrose", a.text)

    def test_everyday_words_are_not_mistaken_for_places(self):
        self.assertNotIn("Moline", BOT.ask("Which cities pass lateness on the most?").text)
        self.assertNotIn("Milwaukee", BOT.ask("delays in general").text)

    def test_a_state_gets_a_redirect_to_its_cities_not_national_numbers(self):
        a = BOT.ask("flights delayed in Illinois")
        self.assertFalse(a.understood)
        self.assertIn("Chicago", a.text)
        self.assertNotIn("The United States", a.text)

    def test_an_unknown_place_is_reported_not_silently_replaced_by_national_numbers(self):
        for q in ("how many flights were late leaving Atlantis", "late flights in atlantis"):
            a = BOT.ask(q)
            self.assertFalse(a.understood)
            self.assertIn("Atlantis", a.text)
            self.assertNotIn("The United States", a.text)

    def test_ordinary_phrases_after_in_are_not_flagged_as_unknown_places(self):
        for q in ("how many flights were late in total", "flights late in 2023", "which airline is best in summer", "delays in general"):
            self.assertTrue(BOT.ask(q).understood, q)

    def test_nationwide_cancellations_by_weather_answers_cancellations_not_late_flights(self):
        a = BOT.ask("how many flights were cancelled due to weather")
        self.assertIn("cancelled", a.text)
        self.assertIn("{:,}".format(int(float(causes("ALL")["cancel_code_b_weather"]))), a.text)

    def test_year_is_not_repeated_in_the_sentence(self):
        self.assertNotIn("in 2021 in 2021", BOT.ask("how many flights were delayed by weather in 2021").text)

    def test_ranking_by_how_much_lateness_is_passed_on(self):
        row = max((r for r in raw("carryover.csv") if r["params"] == "G90_T30" and r["dimension"] == "CARRIER" and float(r["n_a_late15"]) >= 20000),
                  key=lambda r: float(r["p_b_late15_given_a_late15"]))
        a = BOT.ask("Which airline passes lateness on the most?")
        self.assertIn(S.airline_label(row["value"]), a.text)

    def test_season_words_get_an_honest_note_instead_of_a_fake_seasonal_answer(self):
        a = BOT.ask("which city is worst in the winter")
        self.assertIn("can't split", a.text)
        self.assertNotIn("bad weather", a.text.split("\n")[0])      # "winter" must not silently become a weather ranking

    def test_plurals_and_wording_in_rankings(self):
        t = BOT.ask("Which city has the most late flights?").text
        self.assertNotIn("citys", t)
        self.assertNotIn("(of flights", t)


if __name__ == "__main__":
    unittest.main()
