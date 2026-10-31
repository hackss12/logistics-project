import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from urllib.parse import urlparse

from app import create_app
from database.extensions import db
from services.receipt_number_service import allocate_lr_number

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@unittest.skipUnless(TEST_DATABASE_URL, "Set TEST_DATABASE_URL to a disposable MySQL database ending in _test.")
class MySqlSequenceConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database_name = urlparse(TEST_DATABASE_URL).path.lstrip("/")
        if not database_name.endswith("_test"):
            raise RuntimeError("Refusing to run destructive sequence tests unless TEST_DATABASE_URL ends in _test.")
        cls.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-key-not-for-production",
                "SQLALCHEMY_DATABASE_URI": TEST_DATABASE_URL,
            }
        )
        with cls.app.app_context():
            db.drop_all()
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.drop_all()

    def test_parallel_allocations_are_unique_and_continuous(self):
        def reserve(_):
            with self.app.app_context():
                return allocate_lr_number(date(2026, 10, 29))

        with ThreadPoolExecutor(max_workers=12) as executor:
            results = list(executor.map(reserve, range(40)))
        sequences = [sequence for _number, sequence in results]
        self.assertEqual(len(set(sequences)), 40)
        self.assertEqual(sorted(sequences), list(range(1, 41)))


if __name__ == "__main__":
    unittest.main()
