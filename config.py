import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 1800}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    WTF_CSRF_TIME_LIMIT = 3600
    COMPANY = {
        "name": os.getenv("COMPANY_NAME", "MOHAN LOGISTICS PRIVATE LIMITED"),
        "tagline": os.getenv("COMPANY_TAGLINE", "JAI MATA DI"),
        "jurisdiction": os.getenv("COMPANY_JURISDICTION", "Subject to Rohtak Jurisdiction"),
        "registered_office": os.getenv(
            "COMPANY_REGISTERED_OFFICE",
            "Gandhra More, 18 K M Stone, Delhi Road, Rohtak, Haryana - 124001",
        ),
        "address": os.getenv(
            "COMPANY_ADDRESS",
            "NH-48, Opp. McDonald, Behind Lakshmi Hotel, V.P.O. Nakhrola, Manesar, Gurgaon (HR) - 122050",
        ),
        "corporate_office": os.getenv(
            "COMPANY_CORPORATE_OFFICE",
            "41/35, 2nd Floor, West Punjabi Bagh, New Delhi-110026 (India)",
        ),
        "email": os.getenv("COMPANY_EMAIL", "admin@mohanindia.co.in"),
        "gstin": os.getenv("COMPANY_GSTIN", "06AAHCS3801K1ZD"),
    }
    TAX_RATE = os.getenv("TAX_RATE", "0")
