import unittest
from datetime import date

from services.receipt_number_service import format_lr_number


class ReceiptNumberFormatTests(unittest.TestCase):
    def test_global_sequence_is_not_reset_for_month_or_year(self):
        cases = [
            (date(2026, 10, 31), 1, "ML/2026/10/000001"),
            (date(2026, 10, 31), 2, "ML/2026/10/000002"),
            (date(2026, 11, 1), 3, "ML/2026/11/000003"),
            (date(2027, 1, 1), 4, "ML/2027/01/000004"),
        ]
        for receipt_date, sequence, expected in cases:
            with self.subTest(sequence=sequence):
                self.assertEqual(format_lr_number(receipt_date, sequence), expected)


if __name__ == "__main__":
    unittest.main()
