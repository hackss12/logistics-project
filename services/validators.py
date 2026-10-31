import re
from datetime import date
from decimal import Decimal, InvalidOperation

MOBILE_RE = re.compile(r"^[6-9]\d{9}$")
PIN_RE = re.compile(r"^\d{6}$")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


class ValidationError(ValueError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__("; ".join(errors))


def _validate_party(data, label, errors):
    if not (data.get("name") or "").strip():
        errors.append(f"{label} name is required.")
    mobile = (data.get("mobile") or "").strip()
    if mobile and not MOBILE_RE.fullmatch(mobile):
        errors.append(f"{label} mobile must be a valid 10-digit Indian number.")
    pin = (data.get("pin_code") or "").strip()
    if pin and not PIN_RE.fullmatch(pin):
        errors.append(f"{label} PIN code must contain six digits.")
    gstin = (data.get("gstin") or "").strip().upper()
    if gstin and not GSTIN_RE.fullmatch(gstin):
        errors.append(f"{label} GSTIN is not in a valid format.")


def _date(value, label, errors, required=False):
    if not value:
        if required:
            errors.append(f"{label} is required.")
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        errors.append(f"{label} must be a valid date.")
        return None


def validate_receipt(data):
    errors = []
    consignor = data.get("consignor", {})
    consignee = data.get("consignee", {})
    _validate_party(consignor, "Consignor", errors)
    _validate_party(consignee, "Consignee", errors)
    receipt_date = _date(data.get("receipt_date"), "Receipt date", errors, required=True)
    driver_mobile = (data.get("driver_mobile") or "").strip()
    if driver_mobile and not MOBILE_RE.fullmatch(driver_mobile):
        errors.append("Driver mobile must be a valid 10-digit Indian number.")

    for label, field in (("Package count", "package_count"),):
        value = data.get(field)
        if value not in (None, ""):
            try:
                if int(value) < 0:
                    errors.append(f"{label} cannot be negative.")
            except (TypeError, ValueError):
                errors.append(f"{label} must be a whole number.")
    for field in ("actual_weight", "charged_weight"):
        value = data.get(field)
        if value not in (None, ""):
            try:
                number = Decimal(str(value))
                if not number.is_finite() or number < 0:
                    errors.append(f"{field.replace('_', ' ').title()} cannot be negative.")
            except (InvalidOperation, ValueError):
                errors.append(f"{field.replace('_', ' ').title()} must be numeric.")

    particulars = data.get("particulars", [])
    for index, row in enumerate(particulars, 1):
        _date(row.get("invoice_date"), f"Invoice date in row {index}", errors)
        if any((row.get(key) or "").strip() for key in ("chassis_number", "model", "shipment_number", "invoice_number")):
            if not (row.get("chassis_number") or "").strip() and not (row.get("invoice_number") or "").strip():
                errors.append(f"Particulars row {index} needs a chassis number or invoice number.")

    payment_type = data.get("payment_type")
    if payment_type not in {"To Pay", "Paid by Bill", "COD-D/D Amount"}:
        errors.append("Select a valid payment type.")
    if errors:
        raise ValidationError(errors)
    return receipt_date
