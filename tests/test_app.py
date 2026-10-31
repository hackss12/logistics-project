import json
import os
import unittest

os.environ["SECRET_KEY"] = "test-key-not-for-production"
os.environ["DATABASE_URL"] = "sqlite://"

from app import create_app
import desktop_app
from database.extensions import db
from database.models import CompanySetting, User
from werkzeug.security import check_password_hash, generate_password_hash


class AppSmokeTests(unittest.TestCase):
    def test_pwa_manifest_and_service_worker_are_available_without_login(self):
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-key-not-for-production",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "WTF_CSRF_ENABLED": False,
            }
        )
        with app.test_client() as client:
            with client.get("/manifest.webmanifest") as manifest_response:
                self.assertEqual(manifest_response.status_code, 200)
                self.assertEqual(manifest_response.mimetype, "application/manifest+json")
                manifest = json.loads(manifest_response.data)
                self.assertEqual(manifest["display"], "standalone")
                self.assertEqual(manifest["scope"], "/")
            with client.get("/service-worker.js") as service_worker_response:
                self.assertEqual(service_worker_response.status_code, 200)
                self.assertEqual(service_worker_response.headers["Service-Worker-Allowed"], "/")
                self.assertIn(b"fetch(event.request)", service_worker_response.data)
            with client.get("/static/images/app-icon.svg") as icon_response:
                self.assertEqual(icon_response.status_code, 200)
                self.assertEqual(icon_response.mimetype, "image/svg+xml")

    def test_login_page_renders(self):
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-key-not-for-production",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "WTF_CSRF_ENABLED": False,
            }
        )
        with app.test_client() as client:
            response = client.get("/login")
            logo_response = client.get("/static/images/mohan_logistics_logo.png")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Access the shared Mohan Logistics LR book", response.data)
            self.assertEqual(logo_response.status_code, 200)
            self.assertTrue(logo_response.data.startswith(b"\x89PNG\r\n\x1a\n"))
            logo_response.close()

    def test_admin_can_save_settings_and_manage_users(self):
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-key-not-for-production",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        with app.app_context():
            db.create_all()
            admin = User(
                username="admin",
                password_hash=generate_password_hash("test-only-admin-password"),
                role="admin",
            )
            db.session.add(admin)
            db.session.commit()

        with app.test_client() as client:
            login = client.post(
                "/login",
                data={"username": "admin", "password": "test-only-admin-password"},
            )
            self.assertEqual(login.status_code, 302)
            self.assertEqual(client.get("/reports").status_code, 200)
            self.assertEqual(client.get("/receipts/new").status_code, 200)
            self.assertEqual(client.get("/account/password").status_code, 200)
            self.assertEqual(client.get("/receipts/export.xlsx").status_code, 200)
            password_response = client.post(
                "/account/password",
                data={
                    "current_password": "test-only-admin-password",
                    "new_password": "test-only-new-password",
                    "confirm_password": "test-only-new-password",
                },
            )
            self.assertEqual(password_response.status_code, 302)
            settings_response = client.post(
                "/admin/settings",
                data={
                    "company_name": "MOHAN LOGISTICS TEST",
                    "tagline": "JAI MATA DI",
                    "jurisdiction": "Subject to Rohtak Jurisdiction",
                    "registered_office": "Rohtak",
                    "address": "Manesar",
                    "corporate_office": "New Delhi",
                    "email": "admin@example.invalid",
                    "gstin": "06AAHCS3801K1ZD",
                    "tax_rate": "5",
                },
            )
            self.assertEqual(settings_response.status_code, 302)
            create_user_response = client.post(
                "/admin/users",
                data={
                    "username": "operator",
                    "role": "operator",
                    "password": "test-only-operator-password",
                },
            )
            self.assertEqual(create_user_response.status_code, 302)

        with app.app_context():
            self.assertEqual(db.session.get(CompanySetting, "company_name").value, "MOHAN LOGISTICS TEST")
            self.assertIsNotNone(User.query.filter_by(username="operator").first())
            self.assertTrue(
                check_password_hash(
                    User.query.filter_by(username="admin").first().password_hash,
                    "test-only-new-password",
                )
            )
            db.drop_all()


if __name__ == "__main__":
    unittest.main()
