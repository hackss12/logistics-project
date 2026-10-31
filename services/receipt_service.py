from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from database.extensions import db
from database.models import Consignee, Consignor, Receipt, ReceiptCharge, ReceiptParticular, ReceiptPayment
from services.audit_service import log_action
from services.calculation_service import CHARGE_FIELDS, as_money, calculate_charges
from services.receipt_number_service import allocate_lr_number
from services.validators import ValidationError, validate_receipt

CHARGE_LABELS = {
    "freight": "Freight",
    "surcharge": "Surcharge",
    "cover_fov": "Cover/FOV",
    "local_godown": "Local Godown Charges",
    "door_delivery": "Door Delivery Charges",
    "cod": "COD Charges",
    "miscellaneous": "Miscellaneous Charges",
    "statistical": "Statistical Charges",
    "local_collection": "Local Collection Charges",
}


def _party_model(model, info):
    existing = model.query.filter(func.lower(model.name) == info["name"].strip().lower()).first()
    if existing:
        return existing
    return model(
        name=info["name"].strip(),
        company_name=(info.get("company_name") or "").strip() or None,
        address=(info.get("address") or "").strip() or None,
        city=(info.get("city") or "").strip() or None,
        state=(info.get("state") or "").strip() or None,
        pin_code=(info.get("pin_code") or "").strip() or None,
        gstin=(info.get("gstin") or "").strip().upper() or None,
        mobile=(info.get("mobile") or "").strip() or None,
        contact_person=(info.get("contact_person") or "").strip() or None,
    )


def _optional_decimal(value, label):
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValidationError([f"{label} must be numeric."])
    if not number.is_finite() or number < 0:
        raise ValidationError([f"{label} cannot be negative."])
    return number


def create_receipt(data, user_id, tax_rate=Decimal("0")):
    receipt_date = validate_receipt(data)
    charges = {name: data.get("charges", {}).get(name, "0") for name in CHARGE_FIELDS}
    amount_paid = data.get("amount_paid", "0") or "0"
    totals = calculate_charges(charges, tax_rate, amount_paid)
    declared_value = as_money(data.get("declared_value", "0"), "declared_value")
    lr_number, sequence = allocate_lr_number(receipt_date)
    session = db.session
    try:
        consignor = _party_model(Consignor, data["consignor"])
        consignee = _party_model(Consignee, data["consignee"])
        receipt = Receipt(
            lr_number=lr_number,
            sequence_number=sequence,
            cns_serial_number=(data.get("cns_serial_number") or "").strip() or None,
            receipt_date=receipt_date,
            consignor=consignor,
            consignee=consignee,
            from_station=(data.get("from_station") or "").strip() or None,
            to_station=(data.get("to_station") or "").strip() or None,
            transit_route=(data.get("transit_route") or "").strip() or None,
            risk_type=data.get("risk_type") or "Owner's Risk",
            trailer_number=(data.get("trailer_number") or "").strip() or None,
            truck_number=(data.get("truck_number") or "").strip() or None,
            driver_name=(data.get("driver_name") or "").strip() or None,
            driver_mobile=(data.get("driver_mobile") or "").strip() or None,
            load_number=(data.get("load_number") or "").strip() or None,
            packing=(data.get("packing") or "").strip() or None,
            package_count=int(data["package_count"]) if data.get("package_count") not in (None, "") else None,
            actual_weight=_optional_decimal(data.get("actual_weight"), "Actual weight"),
            charged_weight=_optional_decimal(data.get("charged_weight"), "Charged weight"),
            goods_class=(data.get("goods_class") or "").strip() or None,
            goods_description=(data.get("goods_description") or "").strip() or None,
            declared_value=declared_value,
            subtotal=totals["subtotal"],
            tax_rate=totals["tax_rate"],
            tax_amount=totals["tax_amount"],
            grand_total=totals["grand_total"],
            payment_type=data["payment_type"],
            payment_status="Paid" if totals["balance_due"] == 0 else ("Partial" if totals["amount_paid"] else "Pending"),
            amount_paid=totals["amount_paid"],
            balance_due=totals["balance_due"],
            payment_remarks=(data.get("payment_remarks") or "").strip() or None,
            status="Issued",
            created_by=user_id,
        )
        for index, row in enumerate(data.get("particulars", []), 1):
            invoice_date = date.fromisoformat(row["invoice_date"]) if row.get("invoice_date") else None
            receipt.particulars.append(
                ReceiptParticular(
                    serial_no=index,
                    chassis_number=(row.get("chassis_number") or "").strip() or None,
                    model=(row.get("model") or "").strip() or None,
                    invoice_date=invoice_date,
                    shipment_number=(row.get("shipment_number") or "").strip() or None,
                    invoice_number=(row.get("invoice_number") or "").strip() or None,
                )
            )
        for name, amount in totals["charges"].items():
            receipt.charges.append(
                ReceiptCharge(charge_name=CHARGE_LABELS[name], amount=amount)
            )
        if totals["amount_paid"] > 0:
            receipt.payments.append(
                ReceiptPayment(
                    payment_type=data["payment_type"],
                    amount=totals["amount_paid"],
                    payment_date=receipt_date,
                    remarks=(data.get("payment_remarks") or "").strip() or None,
                )
            )
        session.add(receipt)
        session.flush()
        log_action(session, user_id, "receipt_issued", receipt.id, f"Issued {lr_number}")
        session.commit()
        return receipt
    except (IntegrityError, SQLAlchemyError):
        session.rollback()
        raise
