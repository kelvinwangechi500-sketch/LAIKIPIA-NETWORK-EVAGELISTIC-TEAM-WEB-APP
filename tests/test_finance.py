import os
import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "finance-test-secret"

from app import create_app
from routes.treasurer import current_semester
from services.export_service import export_finance_excel, export_finance_pdf


class FinanceSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True)

    def test_semester_calendar_boundaries(self):
        self.assertEqual(current_semester(date(2026, 9, 1)), "Semester 1")
        self.assertEqual(current_semester(date(2026, 12, 31)), "Semester 1")
        self.assertEqual(current_semester(date(2027, 1, 1)), "Semester 2")
        self.assertEqual(current_semester(date(2027, 4, 30)), "Semester 2")
        self.assertIsNone(current_semester(date(2027, 5, 1)))

    def test_finance_routes_are_registered_and_protected(self):
        rules = {rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertIn("/treasurer/dashboard", rules)
        self.assertIn("/treasurer/annual-report", rules)
        self.assertIn("/treasurer/report/export/<fmt>", rules)
        with self.app.test_client() as client:
            self.assertEqual(client.get("/treasurer/dashboard").status_code, 302)
            self.assertEqual(client.get("/treasurer/annual-report").status_code, 302)

    def test_finance_templates_compile(self):
        for template in ("treasurer/dashboard.html", "treasurer/report.html", "treasurer/annual_report.html", "admin/finance.html"):
            self.app.jinja_env.get_template(template)

    def test_finance_exports_generate(self):
        transaction = SimpleNamespace(
            transaction_date=date(2026, 7, 1), transaction_type="expense", income_type="Other",
            category="Printing", description="Test", reference_number="T-1",
            payment_method="M-Pesa", amount=Decimal("100.00"), semester="Semester 2",
        )
        pdf = export_finance_pdf("Test Report", Decimal("0"), Decimal("0"), Decimal("100"), Decimal("-100"), [transaction])
        excel = export_finance_excel("Test Report", Decimal("0"), Decimal("0"), Decimal("100"), Decimal("-100"), [transaction])
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertTrue(excel.startswith(b"PK"))


if __name__ == "__main__":
    unittest.main()
