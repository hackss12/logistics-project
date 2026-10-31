from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CHARGE_FIELDS = (
    "freight",
    "surcharge",
    "cover_fov",
    "local_godown",
    "door_delivery",
    "cod",
    "miscellaneous",
    "statistical",
    "local_collection",
)


def as_money(value, field="amount"):
    try:
        amount = Decimal(str(value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field.replace('_', ' ').title()} must be a valid amount.")
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"{field.replace('_', ' ').title()} cannot be negative.")
    return amount


def calculate_charges(charges, tax_rate=Decimal("0"), amount_paid=Decimal("0")):
    normalized = {name: as_money(charges.get(name, 0), name) for name in CHARGE_FIELDS}
    subtotal = sum(normalized.values(), Decimal("0.00")).quantize(Decimal("0.01"))
    rate = Decimal(str(tax_rate))
    if rate < 0 or rate > 100:
        raise ValueError("Tax rate must be between 0 and 100.")
    tax = (subtotal * rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = subtotal + tax
    paid = as_money(amount_paid, "amount_paid")
    if paid > total:
        raise ValueError("Amount paid cannot exceed the grand total.")
    return {
        "charges": normalized,
        "subtotal": subtotal,
        "tax_rate": rate,
        "tax_amount": tax,
        "grand_total": total,
        "amount_paid": paid,
        "balance_due": total - paid,
    }
