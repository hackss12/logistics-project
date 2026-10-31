import unittest
from decimal import Decimal

from services.calculation_service import calculate_charges


class CalculationTests(unittest.TestCase):
    def test_subtotal_tax_total_and_balance_use_decimal_values(self):
        result = calculate_charges(
            {"freight": "1000.10", "cod": "99.90"},
            tax_rate=Decimal("5"),
            amount_paid="500",
        )
        self.assertEqual(result["subtotal"], Decimal("1100.00"))
        self.assertEqual(result["tax_amount"], Decimal("55.00"))
        self.assertEqual(result["grand_total"], Decimal("1155.00"))
        self.assertEqual(result["balance_due"], Decimal("655.00"))

    def test_zero_charges_are_valid(self):
        result = calculate_charges({}, tax_rate=Decimal("0"), amount_paid="0")
        self.assertEqual(result["subtotal"], Decimal("0.00"))
        self.assertEqual(result["grand_total"], Decimal("0.00"))

    def test_negative_amount_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            calculate_charges({"freight": "-0.01"})

    def test_paid_amount_cannot_exceed_total(self):
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            calculate_charges({"freight": "10"}, amount_paid="11")


if __name__ == "__main__":
    unittest.main()
