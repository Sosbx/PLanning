# tests/test_constraints.py
import unittest
from core.Constantes.models import Doctor, TimeSlot, Planning, DayPlanning
from core.Constantes.constraints import PlanningConstraints
from datetime import datetime, timedelta, date

class TestPlanningConstraints(unittest.TestCase):
    def setUp(self):
        self.constraints = PlanningConstraints()
        self.doctor = Doctor(name="Dr. Example", half_parts=2)
        self.slot = TimeSlot(
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=4),
            site="Cenon",
            slot_type="Consultation",
            abbreviation="NL"
        )
        # Création d'un planning fictif
        self.planning = Planning(start_date=date(2024, 10, 1), end_date=date(2024, 10, 31))
        self.planning.days.append(DayPlanning(date=date(2024, 10, 1)))

    def test_check_nl_constraint(self):
        # Simuler qu'un médecin a eu une garde de nuit longue (NL)
        self.doctor.weekday_night_shifts['NL'] = 1  # Le médecin a déjà travaillé une NL
        can_work = self.constraints.check_nl_constraint(self.doctor, datetime.now().date(), self.slot, self.planning)
        self.assertFalse(can_work, "Le médecin ne devrait pas pouvoir travailler après une NL.")

if __name__ == "__main__":
    unittest.main()
