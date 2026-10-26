"""Run with:  python3 -m unittest dashboard/test_content.py   (from the project root)
or:          python3 -m unittest test_content.py              (from inside dashboard/)

Part 1 tests the wording/selection helpers. Part 2 checks the exported data files
against figures the Hadoop jobs themselves reported, so a stale or wrong export fails.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import content as c  # noqa: E402


class WordingTests(unittest.TestCase):
    def test_per100_wording(self):
        self.assertEqual(c.say_per100(0.189), "about 19 out of every 100")
        self.assertEqual(c.say_per100(0.023), "about 2.3 out of every 100")
        self.assertEqual(c.say_per100(0.0023), "less than 1 out of every 100 (0.2)")
        self.assertEqual(c.say_per100(0.0), "almost none out of every 100")

    def test_big_count(self):
        self.assertEqual(c.big_count(34786532), "34.8 million")
        self.assertEqual(c.big_count(7439), "7,439")

    def test_names(self):
        airports, carriers = c.load_names()
        self.assertEqual(c.city("ATL", airports), "Atlanta, GA")
        self.assertIn("Hartsfield-Jackson", c.airport_label("ATL", airports))
        self.assertEqual(c.route_label("JFK-LAX", airports), "New York, NY to Los Angeles, CA")
        self.assertEqual(c.airline_label("WN", carriers), "Southwest Airlines Co.")
        self.assertEqual(c.city("QQQQ", airports), "QQQQ")  # unknown code falls back, never crashes


class SelectionTests(unittest.TestCase):
    ROWS = [
        {"r": "A", "rate": "0.50", "n": "10"},      # extreme but tiny sample
        {"r": "B", "rate": "0.30", "n": "5000"},
        {"r": "C", "rate": "0.10", "n": "9000"},
        {"r": "D", "rate": "0.20", "n": "7000"},
    ]

    def test_small_samples_never_ranked(self):
        top = c.rank_rows(self.ROWS, "rate", 1000, "n", top=2)
        self.assertEqual([r["r"] for r in top], ["B", "D"])

    def test_best_and_worst_respect_minimum(self):
        best, worst = c.best_and_worst(self.ROWS, "rate", 1000, "n")
        self.assertEqual((best["r"], worst["r"]), ("C", "B"))

    def test_best_and_worst_when_nothing_qualifies(self):
        self.assertEqual(c.best_and_worst(self.ROWS, "rate", 10**6, "n"), (None, None))


class DataAgreesWithHadoopCounters(unittest.TestCase):
    """Figures below are what the Hadoop jobs printed in their own run reports."""

    def test_row_counts(self):
        self.assertEqual(len(c.read_rows("airports.csv")), 384)
        self.assertEqual(len(c.read_rows("routes.csv")), 8410)
        self.assertEqual(len(c.read_rows("temporal.csv")), 271)
        self.assertEqual(len(c.read_rows("causes.csv")), 13788)
        self.assertEqual(len(c.read_rows("carryover.csv")), 3724)
        self.assertEqual(len(c.read_rows("route_carrier.csv")), 72946)

    def test_total_flights_agree_across_independent_jobs(self):
        audit_total = sum(int(r["records"]) for r in c.read_rows("audit_months.csv"))
        all_row = c.pick_rows(c.read_rows("causes.csv"), dimension="ALL")[0]
        self.assertEqual(audit_total, 34786532)
        self.assertEqual(int(all_row["n_flights_scheduled"]), audit_total)

    def test_cancellation_reasons_add_up_to_cancellations(self):
        r = c.pick_rows(c.read_rows("causes.csv"), dimension="ALL")[0]
        codes = sum(int(r["cancel_code_" + k]) for k, _ in c.CANCEL_REASONS)
        self.assertEqual(codes, int(r["n_cancelled"]))

    def test_cause_shares_add_to_one(self):
        r = c.pick_rows(c.read_rows("causes.csv"), dimension="ALL")[0]
        total = sum(float(r["share_" + k]) for k, _, _ in c.CAUSES)
        self.assertAlmostEqual(total, 1.0, delta=0.001)

    def test_carryover_baseline_links_match_rotation_job(self):
        row = c.pick_rows(c.read_rows("carryover.csv"), params="G90_T30", dimension="ALL")[0]
        self.assertEqual(int(row["n_links"]), 21140066)  # LINKED count from AircraftRotationJob

    def test_biggest_delay_cause_overall(self):
        r = c.pick_rows(c.read_rows("causes.csv"), dimension="ALL")[0]
        self.assertEqual(c.main_cause(r), "The plane arrived late from its last trip")

    def test_every_carrier_in_data_has_a_name(self):
        _, carriers = c.load_names()
        codes = {r["carrier"] for r in c.read_rows("route_carrier.csv")}
        self.assertEqual(codes - set(carriers), set())


class FindingsTests(unittest.TestCase):
    def test_headline_findings_match_hadoop_numbers(self):
        f = c.findings(c.read_rows("causes.csv"), c.read_rows("temporal.csv"), c.read_rows("carryover.csv"))
        self.assertEqual(len(f), 6)
        self.assertEqual(f[0]["big"], "19 in 100")        # 18.9% late (DelayCauseMetricsJob)
        self.assertEqual(f[1]["big"], "Sun 8pm")          # worst weekday-hour cell with >=20k flights
        self.assertEqual(f[2]["big"], "78 in 100")        # P(B late | A late), G90_T30
        self.assertIn("9.6 in 100", f[2]["more"])         # P(B late | A on time)
        self.assertEqual(f[3]["big"], "38%")              # late-aircraft share of delay minutes
        self.assertEqual(f[4]["big"], "6.0 in 100")       # 2020 cancellation rate
        self.assertEqual(f[5]["big"], "6 min")            # mean departure delay - mean arrival delay

    def test_hour_labels(self):
        self.assertEqual([c.hour_label(h) for h in (0, 5, 12, 13, 20)], ["midnight", "5am", "noon", "1pm", "8pm"])


if __name__ == "__main__":
    unittest.main()
