from datetime import date, datetime, timezone
from decimal import Decimal

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, UniqueConstraint

from database.extensions import db


def utcnow_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="operator")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)


class Consignor(db.Model):
    __tablename__ = "consignors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    company_name = db.Column(db.String(160))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    pin_code = db.Column(db.String(6))
    gstin = db.Column(db.String(15))
    mobile = db.Column(db.String(15))
    contact_person = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)


class Consignee(db.Model):
    __tablename__ = "consignees"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    company_name = db.Column(db.String(160))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    pin_code = db.Column(db.String(6))
    gstin = db.Column(db.String(15))
    mobile = db.Column(db.String(15))
    contact_person = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)


class LRSequence(db.Model):
    __tablename__ = "lr_sequences"

    sequence_number = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    allocated_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)


class Receipt(db.Model):
    __tablename__ = "receipts"
    __table_args__ = (
        UniqueConstraint("lr_number", name="uq_receipts_lr_number"),
        UniqueConstraint("sequence_number", name="uq_receipts_sequence_number"),
        CheckConstraint("package_count IS NULL OR package_count >= 0", name="ck_receipts_packages_nonnegative"),
        CheckConstraint("declared_value >= 0 AND subtotal >= 0 AND tax_amount >= 0 AND grand_total >= 0",
                        name="ck_receipts_amounts_nonnegative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    lr_number = db.Column(db.String(32), nullable=True)
    sequence_number = db.Column(db.BigInteger, db.ForeignKey("lr_sequences.sequence_number"), nullable=True)
    cns_serial_number = db.Column(db.String(40))
    receipt_date = db.Column(db.Date, nullable=False)
    consignor_id = db.Column(db.Integer, db.ForeignKey("consignors.id"), nullable=False)
    consignee_id = db.Column(db.Integer, db.ForeignKey("consignees.id"), nullable=False)
    from_station = db.Column(db.String(120))
    to_station = db.Column(db.String(120))
    transit_route = db.Column(db.String(255))
    risk_type = db.Column(db.String(30), nullable=False, default="Owner's Risk")
    trailer_number = db.Column(db.String(40))
    truck_number = db.Column(db.String(40))
    driver_name = db.Column(db.String(120))
    driver_mobile = db.Column(db.String(15))
    load_number = db.Column(db.String(40))
    packing = db.Column(db.String(120))
    package_count = db.Column(db.Integer)
    actual_weight = db.Column(db.Numeric(12, 3))
    charged_weight = db.Column(db.Numeric(12, 3))
    goods_class = db.Column(db.String(120))
    goods_description = db.Column(db.Text)
    declared_value = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal("0"))
    subtotal = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal("0"))
    tax_rate = db.Column(db.Numeric(7, 4), nullable=False, default=Decimal("0"))
    tax_amount = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal("0"))
    grand_total = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal("0"))
    payment_type = db.Column(db.String(30), nullable=False)
    payment_status = db.Column(db.String(20), nullable=False, default="Pending")
    amount_paid = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal("0"))
    balance_due = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal("0"))
    payment_remarks = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="Issued")
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive, onupdate=utcnow_naive)

    consignor = db.relationship(Consignor)
    consignee = db.relationship(Consignee)
    particulars = db.relationship(
        "ReceiptParticular", back_populates="receipt", cascade="all, delete-orphan", order_by="ReceiptParticular.serial_no"
    )
    charges = db.relationship(
        "ReceiptCharge", back_populates="receipt", cascade="all, delete-orphan"
    )
    payments = db.relationship(
        "ReceiptPayment", back_populates="receipt", cascade="all, delete-orphan"
    )


class ReceiptParticular(db.Model):
    __tablename__ = "receipt_particulars"

    id = db.Column(db.Integer, primary_key=True)
    receipt_id = db.Column(db.Integer, db.ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    serial_no = db.Column(db.Integer, nullable=False)
    chassis_number = db.Column(db.String(80))
    model = db.Column(db.String(100))
    invoice_date = db.Column(db.Date)
    shipment_number = db.Column(db.String(80))
    invoice_number = db.Column(db.String(80))
    receipt = db.relationship(Receipt, back_populates="particulars")


class ReceiptCharge(db.Model):
    __tablename__ = "receipt_charges"

    id = db.Column(db.Integer, primary_key=True)
    receipt_id = db.Column(db.Integer, db.ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    charge_name = db.Column(db.String(80), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal("0"))
    receipt = db.relationship(Receipt, back_populates="charges")


class ReceiptPayment(db.Model):
    __tablename__ = "receipt_payments"

    id = db.Column(db.Integer, primary_key=True)
    receipt_id = db.Column(db.Integer, db.ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_type = db.Column(db.String(30), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False, default=date.today)
    remarks = db.Column(db.Text)
    receipt = db.relationship(Receipt, back_populates="payments")


class CompanySetting(db.Model):
    __tablename__ = "company_settings"

    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive, onupdate=utcnow_naive)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    receipt_id = db.Column(db.Integer, db.ForeignKey("receipts.id"))
    action = db.Column(db.String(40), nullable=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive, index=True)
