# tests/test_planning_generator.py
import unittest
from core.Constantes.models import Doctor, CAT, DailyPostConfiguration, PostConfig
from core.Generator.Weekend.planning_generator import PlanningGenerator
from datetime import date

class TestPlanningGenerator(unittest.TestCase):
    def setUp(self):
        self.doctors = [Doctor("Dr. A", 2), Doctor("Dr. B", 1)]
        self.cats = [CAT("CAT 1"), CAT("CAT 2")]

        # Créer une configuration des postes avec des valeurs par défaut
        self.post_config = DailyPostConfiguration(
            weekday={"NL": PostConfig(total=1)},
            saturday={"NL": PostConfig(total=1)},
            sunday_holiday={"NL": PostConfig(total=1)}
        )

        self.generator = PlanningGenerator(self.doctors, self.cats, self.post_config)

    def test_generate_daily_slots(self):
        day = date(2024, 10, 15)
        day_planning = self.generator.generate_daily_slots(day)
        self.assertGreater(len(day_planning.slots), 0, "Des slots devraient être créés pour ce jour.")

if __name__ == "__main__":
    unittest.main()
