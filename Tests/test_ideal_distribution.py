# tests/test_ideal_distribution.py
import unittest
from core.Analyzer.pre_analyzer import PlanningPreAnalyzer
from core.Constantes.models import Doctor, DailyPostConfiguration
from datetime import date

class TestPlanningPreAnalyzer(unittest.TestCase):
    def setUp(self):
        self.doctors = [Doctor("Dr. A", 2), Doctor("Dr. B", 1)]
        self.post_config = DailyPostConfiguration()
        self.analyzer = PlanningPreAnalyzer(self.doctors, [], self.post_config, date(2024, 10, 1), date(2024, 10, 31))

    def test_analyze_ideal_distribution(self):
        posts_analysis = {
            "total_posts": {
                "weekday": {"NL": 10},
                "saturday": {"NL": 5},
                "sunday_holiday": {"NL": 5}
            },
            "weekend_groups": {},
            "weekday_groups": {}
        }
        results = self.analyzer.analyze_ideal_distribution(posts_analysis)
        doctor_a_ideal = results["Dr. A"]["weekday_posts"]["NL"]["max"]
        doctor_b_ideal = results["Dr. B"]["weekday_posts"]["NL"]["max"]
        self.assertTrue(doctor_a_ideal >= doctor_b_ideal, "La répartition des postes devrait être équitable.")

if __name__ == "__main__":
    unittest.main()
