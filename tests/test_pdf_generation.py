import unittest
from datetime import date
from decimal import Decimal
import re
from types import SimpleNamespace

from pdf.renderer import render_receipt_copies


class PdfGenerationTests(unittest.TestCase):
    def test_combined_output_is_a_single_pdf_with_all_copy_titles(self):
        party = SimpleNamespace(
            name="Sample & Transport",
            company_name="Sample Company",
            address="A long address " * 25,
            city="Rohtak",
            state="Haryana",
            pin_code="124001",
            gstin="",
            mobile="9876543210",
            contact_person="Test",
        )
        receipt = SimpleNamespace(
            lr_number="ML/2026/10/000001",
            cns_serial_number="CNS-1",
            receipt_date=date(2026, 10, 29),
            risk_type="Owner's Risk",
            from_station="Rohtak",
            to_station="Delhi",
            transit_route="Rohtak to Delhi",
            load_number="L-1",
            consignor=party,
            consignee=party,
            truck_number="HR-00-AA-0000",
            trailer_number="",
            driver_name="Driver",
            driver_mobile="9876543210",
            packing="Cartons",
            package_count=2,
            actual_weight=Decimal("10.000"),
            charged_weight=Decimal("12.000"),
            goods_class="General",
            goods_description="Goods",
            declared_value=Decimal("1000.00"),
            status="Issued",
            particulars=[
                SimpleNamespace(
                    serial_no=1,
                    chassis_number="CH-1",
                    model="Model",
                    invoice_date=date(2026, 10, 1),
                    shipment_number="S-1",
                    invoice_number="I-1",
                )
            ],
            charges=[SimpleNamespace(charge_name="Freight", amount=Decimal("100.00"))],
            subtotal=Decimal("100.00"),
            tax_rate=Decimal("0"),
            tax_amount=Decimal("0"),
            grand_total=Decimal("100.00"),
            payment_type="To Pay",
            payment_status="Pending",
            amount_paid=Decimal("0"),
            balance_due=Decimal("100.00"),
            payment_remarks="",
        )
        company = {
            "name": "MOHAN LOGISTICS PRIVATE LIMITED",
            "tagline": "JAI MATA DI",
            "jurisdiction": "Subject to Rohtak Jurisdiction",
            "registered_office": "Gandhra More, Rohtak",
            "address": "NH-48, Manesar",
            "corporate_office": "West Punjabi Bagh, New Delhi",
            "email": "admin@mohanindia.co.in",
            "gstin": "06AAHCS3801K1ZD",
        }

        output = render_receipt_copies(receipt, company)
        self.assertTrue(output.startswith(b"%PDF-"))
        self.assertEqual(output.count(b"%%EOF"), 1)
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", output)), 5)
        self.assertIn(b"/Subtype /Image", output)

    def test_selected_white_consignor_copy_is_a_separate_pdf(self):
        party = SimpleNamespace(
            name="Party",
            company_name="",
            address="",
            city="",
            state="",
            pin_code="",
            gstin="",
            mobile="",
            contact_person="",
        )
        receipt = SimpleNamespace(
            lr_number="ML/2026/10/000001",
            cns_serial_number="",
            receipt_date=date(2026, 10, 29),
            risk_type="Owner's Risk",
            from_station="",
            to_station="",
            transit_route="",
            load_number="",
            consignor=party,
            consignee=party,
            truck_number="",
            trailer_number="",
            driver_name="",
            driver_mobile="",
            packing="",
            package_count=None,
            actual_weight=None,
            charged_weight=None,
            goods_class="",
            goods_description="",
            declared_value=Decimal("0"),
            status="Issued",
            particulars=[],
            charges=[],
            subtotal=Decimal("0"),
            tax_rate=Decimal("0"),
            tax_amount=Decimal("0"),
            grand_total=Decimal("0"),
            payment_type="To Pay",
            payment_status="Pending",
            amount_paid=Decimal("0"),
            balance_due=Decimal("0"),
            payment_remarks="",
        )
        company = {
            "name": "MOHAN LOGISTICS PRIVATE LIMITED",
            "tagline": "JAI MATA DI",
            "jurisdiction": "Subject to Rohtak Jurisdiction",
            "registered_office": "Gandhra More, Rohtak",
            "address": "NH-48, Manesar",
            "corporate_office": "West Punjabi Bagh, New Delhi",
            "email": "admin@mohanindia.co.in",
            "gstin": "06AAHCS3801K1ZD",
        }

        output = render_receipt_copies(receipt, company, "white_consignor")
        self.assertTrue(output.startswith(b"%PDF-"))
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", output)), 1)
        self.assertIn(b"/Subtype /Image", output)


if __name__ == "__main__":
    unittest.main()
