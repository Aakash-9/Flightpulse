"""Proves the Spark-vs-Hadoop checker can fail, not only pass.   Run:  .venv-spark/bin/python spark_jobs/test_spark_compare.py"""
import io
import unittest
from contextlib import redirect_stdout

import spark_common as S
from pyspark.sql import SparkSession


class CompareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = SparkSession.builder.master("local[1]").config("spark.ui.enabled", "false").getOrCreate()
        cls.spark.sparkContext.setLogLevel("ERROR")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def run_compare(self, mine, hadoop):
        a = self.spark.createDataFrame(mine, ["k", "n", "rate"])
        b = self.spark.createDataFrame(hadoop, ["k", "n", "rate"])
        with redirect_stdout(io.StringIO()) as out:
            diff = S.compare("test", a, b, ["k"], ["n"], ["rate"], {"rate": 6e-5})
        return diff, out.getvalue()

    def test_identical_data_passes(self):
        diff, out = self.run_compare([("A", 10, 0.1234), ("B", 20, 0.5)], [("A", 10, 0.12341), ("B", 20, 0.5)])
        self.assertEqual(diff, 0)
        self.assertIn("IDENTICAL", out)

    def test_one_wrong_count_is_caught(self):
        diff, out = self.run_compare([("A", 10, 0.1234), ("B", 21, 0.5)], [("A", 10, 0.1234), ("B", 20, 0.5)])
        self.assertEqual(diff, 1)
        self.assertIn("DIFFERENCES FOUND", out)

    def test_ratio_outside_rounding_is_caught(self):
        diff, _ = self.run_compare([("A", 10, 0.1240)], [("A", 10, 0.1234)])
        self.assertEqual(diff, 1)

    def test_missing_row_is_caught(self):
        diff, _ = self.run_compare([("A", 10, 0.1)], [("A", 10, 0.1), ("B", 5, 0.2)])
        self.assertEqual(diff, 1)


if __name__ == "__main__":
    unittest.main()
