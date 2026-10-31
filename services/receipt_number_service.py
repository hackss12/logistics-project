from datetime import date

from sqlalchemy import insert

from database.extensions import db
from database.models import LRSequence


def format_lr_number(receipt_date: date, sequence: int) -> str:
    return f"ML/{receipt_date:%Y/%m}/{sequence:06d}"


def allocate_lr_number(receipt_date: date) -> tuple[str, int]:
    """Reserve a globally unique sequence; committed reservations are never reused."""
    with db.engine.begin() as connection:
        result = connection.execute(insert(LRSequence).values())
        sequence = result.inserted_primary_key[0]
    return format_lr_number(receipt_date, sequence), sequence
