import unittest
from datetime import date

from app import create_app
from database.extensions import db
from database.models import Receipt, User
from services.receipt_service import create_receipt
from werkzeug.security import generate_password_hash


class ReceiptCreationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-key-not-for-production",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        user = User(username="test-admin", password_hash=generate_password_hash("test-only-password"), role="admin")
        db.session.add(user)
        db.session.commit()
        self.user_id = user.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    @staticmethod
    def _receipt_data(receipt_date):
        return {
            "receipt_date": receipt_date.isoformat(),
            "consignor": {"name": "Consignor"},
            "consignee": {"name": "Consignee"},
            "payment_type": "To Pay",
            "charges": {"freight": "125.50"},
            "particulars": [
                {
                    "chassis_number": "CH-1",
                    "model": "Truck",
                    "invoice_date": "2026-10-01",
                    "shipment_number": "S-1",
                    "invoice_number": "I-1",
                }
            ],
        }

    def test_creation_persists_receipt_charges_particulars_and_audit(self):
        receipt = create_receipt(self._receipt_data(date(2026, 10, 29)), self.user_id)
        saved = db.session.get(Receipt, receipt.id)
        self.assertEqual(saved.lr_number, "ML/2026/10/000001")
        self.assertEqual(saved.particulars[0].invoice_number, "I-1")
        self.assertEqual(saved.charges[0].amount, 125.50)
        self.assertEqual(saved.balance_due, 125.50)

    def test_sequence_continues_across_month_year_and_cancelled_receipt(self):
        first = create_receipt(self._receipt_data(date(2026, 10, 31)), self.user_id)
        first.status = "Cancelled"
        db.session.commit()
        second = create_receipt(self._receipt_data(date(2026, 11, 1)), self.user_id)
        third = create_receipt(self._receipt_data(date(2027, 1, 1)), self.user_id)
        self.assertEqual(
            [first.lr_number, second.lr_number, third.lr_number],
            ["ML/2026/10/000001", "ML/2026/11/000002", "ML/2027/01/000003"],
        )


if __name__ == "__main__":
    unittest.main()
