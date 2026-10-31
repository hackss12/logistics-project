from io import BytesIO
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Flowable,
    PageBreak,
    PageTemplate,
    NextPageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

COPY_TYPES = {
    "consignor": "CONSIGNOR COPY",
    "consignee": "CONSIGNEE COPY",
    "driver": "DRIVER COPY",
    "record": "RECORD COPY",
    "extra": "EXTRA COPY",
    "white_consignor": "WHITE CONSIGNOR COPY",
}
STANDARD_COPY_TYPES = ("consignor", "consignee", "driver", "record", "extra")
PAPER_COLORS = {
    "consignor": "PINK",
    "consignee": "WHITE",
    "driver": "YELLOW",
    "record": "GREEN",
    "extra": "BLUE",
    "white_consignor": "WHITE",
}
COPY_PALETTE = {
    "consignor": {"accent": colors.HexColor("#B83E68"), "tint": colors.HexColor("#FCE8EF")},
    "consignee": {"accent": colors.HexColor("#356477"), "tint": colors.HexColor("#EAF2F5")},
    "driver": {"accent": colors.HexColor("#9A7100"), "tint": colors.HexColor("#FFF4CF")},
    "record": {"accent": colors.HexColor("#34744A"), "tint": colors.HexColor("#E8F3E9")},
    "extra": {"accent": colors.HexColor("#346C9C"), "tint": colors.HexColor("#E8F0FA")},
    "white_consignor": {"accent": colors.HexColor("#356477"), "tint": colors.HexColor("#EAF2F5")},
}
PAGE_SIZE = landscape(A4)
MARGIN = 9 * mm
CONTENT_WIDTH = PAGE_SIZE[0] - 2 * MARGIN
LOGO_PATH = Path(__file__).resolve().parents[1] / "static" / "images" / "mohan_logistics_logo.png"


def _p(text, style):
    value = "" if text is None else escape(str(text), quote=False)
    return Paragraph(value.replace("\n", "<br/>"), style)


def _markup(text, style):
    return Paragraph(text, style)


def _styles():
    base = getSampleStyleSheet()
    return {
        "tiny": ParagraphStyle("Tiny", parent=base["Normal"], fontName="Helvetica", fontSize=6.4, leading=7.5),
        "small": ParagraphStyle("Small", parent=base["Normal"], fontName="Helvetica", fontSize=7.2, leading=8.7),
        "label": ParagraphStyle("Label", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7, leading=8),
        "title": ParagraphStyle("FormTitle", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=14, leading=16, alignment=TA_CENTER),
        "heading": ParagraphStyle("Section", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=9),
        "center": ParagraphStyle("Center", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7, leading=8, alignment=TA_CENTER),
        "right": ParagraphStyle("Right", parent=base["Normal"], fontName="Helvetica", fontSize=7, leading=8, alignment=TA_RIGHT),
    }


class _LogoFlowable(Flowable):
    def __init__(self, reader, width, height):
        super().__init__()
        self.reader = reader
        self.width = width
        self.height = height

    def draw(self):
        image_width, image_height = self.reader.getSize()
        scale = min(self.width / image_width, self.height / image_height)
        draw_width = image_width * scale
        draw_height = image_height * scale
        self.canv.drawImage(
            self.reader,
            (self.width - draw_width) / 2,
            (self.height - draw_height) / 2,
            width=draw_width,
            height=draw_height,
            preserveAspectRatio=True,
            mask="auto",
        )


def _company_header(company, styles):
    lines = [
        f"<b>{escape(company['name'], quote=False)}</b>",
        f"Registered Office: {escape(company['registered_office'], quote=False)}",
        f"Address: {escape(company['address'], quote=False)}",
        f"Corporate Office: {escape(company['corporate_office'], quote=False)}",
        f"Email: {escape(company['email'], quote=False)} | GSTIN: {escape(company['gstin'], quote=False)}",
    ]
    company_text = _markup("<br/>".join(lines), styles["small"])
    if not LOGO_PATH.is_file():
        raise FileNotFoundError(f"Company logo asset is missing: {LOGO_PATH}")
    logo_reader = ImageReader(BytesIO(LOGO_PATH.read_bytes()))
    logo = _LogoFlowable(logo_reader, width=28 * mm, height=17 * mm)
    top = Table(
        [[_p(company["tagline"], styles["center"]), company_text, logo]],
        colWidths=[30 * mm, CONTENT_WIDTH - 60 * mm, 30 * mm],
    )
    top.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("ALIGN", (-1, 0), (-1, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [top, _p(company["jurisdiction"], styles["right"]), Spacer(1, 2 * mm)]


def _party_box(title, party, styles):
    fields = [
        f"<b>{escape(title, quote=False)}</b>",
        f"Name: {escape(party.name or '', quote=False)}",
        f"Company: {escape(party.company_name or '', quote=False)}",
        f"Address: {escape(party.address or '', quote=False)}",
        f"City/State/PIN: {escape(party.city or '', quote=False)} / {escape(party.state or '', quote=False)} / {escape(party.pin_code or '', quote=False)}",
        f"GSTIN: {escape(party.gstin or '', quote=False)}   Mobile: {escape(party.mobile or '', quote=False)}",
        f"Contact: {escape(party.contact_person or '', quote=False)}",
    ]
    return _markup("<br/>".join(fields), styles["small"])


def _receipt_story(receipt, company, copy_type, styles):
    story = _company_header(company, styles)
    copy_title = COPY_TYPES[copy_type]
    palette = COPY_PALETTE[copy_type]
    copy_heading = ParagraphStyle(
        f"CopyHeading-{copy_type}",
        parent=styles["center"],
        textColor=colors.white,
        fontSize=8,
        leading=10,
    )
    copy_banner = Table(
        [[_markup(f"<b>{copy_title}  |  INTENDED PAPER: {PAPER_COLORS[copy_type]}</b>", copy_heading)]],
        colWidths=[CONTENT_WIDTH],
    )
    copy_banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), palette["accent"]),
        ("BOX", (0, 0), (-1, -1), 0.6, palette["accent"]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(copy_banner)
    story.append(Spacer(1, 2 * mm))

    info = [
        [_markup(f"<b>LR No.</b> {escape(receipt.lr_number or 'DRAFT', quote=False)}", styles["small"]),
         _markup(f"<b>CNS/Serial No.</b> {escape(receipt.cns_serial_number or '', quote=False)}", styles["small"]),
         _markup(f"<b>Date</b> {receipt.receipt_date:%d-%m-%Y}", styles["small"]),
         _markup(f"<b>Risk</b> {escape(receipt.risk_type or '', quote=False)}", styles["small"])],
        [_markup(f"<b>From STN</b> {escape(receipt.from_station or '', quote=False)}", styles["small"]),
         _markup(f"<b>To STN</b> {escape(receipt.to_station or '', quote=False)}", styles["small"]),
         _markup(f"<b>Transit/Route</b> {escape(receipt.transit_route or '', quote=False)}", styles["small"]),
         _markup(f"<b>Load No.</b> {escape(receipt.load_number or '', quote=False)}", styles["small"])],
    ]
    table = Table(info, colWidths=[CONTENT_WIDTH * 0.25] * 4)
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), palette["tint"]),
        ("TEXTCOLOR", (0, 0), (-1, -1), palette["accent"]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)
    story.append(Spacer(1, 2 * mm))

    parties = Table(
        [[_party_box("CONSIGNOR", receipt.consignor, styles), _party_box("CONSIGNEE", receipt.consignee, styles)]],
        colWidths=[CONTENT_WIDTH / 2] * 2,
    )
    parties.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), palette["tint"]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(parties)
    story.append(Spacer(1, 2 * mm))

    transport = [
        ["Truck No.", receipt.truck_number or "", "Trailer No.", receipt.trailer_number or "", "Driver", receipt.driver_name or ""],
        ["Driver Mobile", receipt.driver_mobile or "", "Packing", receipt.packing or "", "Packages", receipt.package_count or ""],
        ["Actual Weight", receipt.actual_weight or "", "Charged Weight", receipt.charged_weight or "", "Class of Goods", receipt.goods_class or ""],
        ["Goods Description", receipt.goods_description or "", "Declared Value (Rs.)", f"{receipt.declared_value:,.2f}", "Status", receipt.status],
    ]
    transport = [[_p(value, styles["tiny"]) for value in row] for row in transport]
    transport_table = Table(transport, colWidths=[22 * mm, CONTENT_WIDTH * .15, 22 * mm, CONTENT_WIDTH * .15, 22 * mm, CONTENT_WIDTH * .30])
    transport_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.black),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 6.5),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTNAME", (4, 0), (4, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (0, -1), palette["tint"]),
        ("BACKGROUND", (2, 0), (2, -1), palette["tint"]),
        ("BACKGROUND", (4, 0), (4, -1), palette["tint"]),
        ("TEXTCOLOR", (0, 0), (0, -1), palette["accent"]),
        ("TEXTCOLOR", (2, 0), (2, -1), palette["accent"]),
        ("TEXTCOLOR", (4, 0), (4, -1), palette["accent"]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), palette["accent"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(transport_table)
    story.append(Spacer(1, 2 * mm))
    story.append(_markup("<b>VEHICLE / CHASSIS / INVOICE PARTICULARS</b>", styles["heading"]))
    rows = [[_p(label, styles["center"]) for label in (
        "Sr. No.", "Chassis No.", "Model", "Invoice Date", "Shipment No.", "Invoice No."
    )]]
    for row in receipt.particulars:
        rows.append([
            _p(row.serial_no, styles["tiny"]),
            _p(row.chassis_number or "", styles["tiny"]),
            _p(row.model or "", styles["tiny"]),
            _p(row.invoice_date.strftime("%d-%m-%Y") if row.invoice_date else "", styles["tiny"]),
            _p(row.shipment_number or "", styles["tiny"]),
            _p(row.invoice_number or "", styles["tiny"]),
        ])
    if len(rows) == 1:
        rows.append(["", "", "", "", "", ""])
    particulars_table = Table(rows, colWidths=[14 * mm, 42 * mm, 30 * mm, 27 * mm, 38 * mm, CONTENT_WIDTH - 151 * mm], repeatRows=1)
    particulars_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 1), (-1, -1), 6.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(particulars_table)
    story.append(Spacer(1, 2 * mm))

    charge_rows = [[_markup("<b>Freight and Charges</b>", styles["small"]), _markup("<b>Amount (Rs.)</b>", styles["right"])]]
    for charge in receipt.charges:
        charge_rows.append([charge.charge_name, f"{charge.amount:,.2f}"])
    charge_rows.extend([
        ["Subtotal", f"{receipt.subtotal:,.2f}"],
        [f"Applicable Tax ({receipt.tax_rate}%)", f"{receipt.tax_amount:,.2f}"],
        ["Grand Total", f"{receipt.grand_total:,.2f}"],
        [f"Payment: {receipt.payment_type} / {receipt.payment_status}", f"Paid {receipt.amount_paid:,.2f} | Due {receipt.balance_due:,.2f}"],
    ])
    charges_table = Table(charge_rows, colWidths=[CONTENT_WIDTH * .68, CONTENT_WIDTH * .32], hAlign="RIGHT")
    charges_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.black),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BACKGROUND", (0, 0), (-1, 0), palette["accent"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -3), (-1, -1), palette["tint"]),
        ("TEXTCOLOR", (0, -3), (-1, -1), palette["accent"]),
        ("FONTSIZE", (0, 0), (-1, -1), 6.5),
        ("FONTNAME", (0, -3), (-1, -1), "Helvetica-Bold"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(charges_table)
    if receipt.payment_remarks:
        story.append(_p(f"<b>Payment Remarks:</b> {receipt.payment_remarks}", styles["small"]))
    story.append(Spacer(1, 5 * mm))
    story.append(Table(
        [["Consignor's Signature", "Consignee's Signature", "Driver's Signature", "For Mohan Logistics Pvt. Ltd."]],
        colWidths=[CONTENT_WIDTH / 4] * 4,
        rowHeights=[13 * mm],
        style=TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("TEXTCOLOR", (0, 0), (-1, -1), palette["accent"]),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTSIZE", (0, 0), (-1, -1), 6.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]),
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(_p(company["jurisdiction"], styles["tiny"]))
    return story


class _ReceiptDoc(BaseDocTemplate):
    def __init__(self, stream, receipt, **kwargs):
        super().__init__(stream, pagesize=PAGE_SIZE, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=10 * mm, bottomMargin=12 * mm, **kwargs)
        self.lr_number = receipt.lr_number or "DRAFT"
        frame = Frame(
            MARGIN,
            12 * mm,
            PAGE_SIZE[0] - 2 * MARGIN,
            PAGE_SIZE[1] - 22 * mm,
            id="receipt",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        templates = []
        for copy_type in COPY_TYPES:
            templates.append(
                PageTemplate(
                    id=copy_type,
                    frames=frame,
                    onPage=lambda canvas, doc, name=copy_type: self._draw_page(canvas, doc, name),
                )
            )
        self.addPageTemplates(templates)

    def _draw_page(self, canvas, _doc, copy_type):
        palette = COPY_PALETTE[copy_type]
        canvas.saveState()
        canvas.setFillColor(palette["accent"])
        canvas.rect(0, PAGE_SIZE[1] - 3 * mm, PAGE_SIZE[0], 3 * mm, stroke=0, fill=1)
        canvas.setStrokeColor(palette["accent"])
        canvas.setLineWidth(0.7)
        canvas.roundRect(
            MARGIN / 2,
            MARGIN / 2,
            PAGE_SIZE[0] - MARGIN,
            PAGE_SIZE[1] - MARGIN,
            2 * mm,
            stroke=1,
            fill=0,
        )
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(palette["accent"])
        canvas.drawString(MARGIN, 6 * mm, f"LR No: {self.lr_number}")
        canvas.drawRightString(PAGE_SIZE[0] - MARGIN, 6 * mm, f"{COPY_TYPES[copy_type]} | Intended paper: {PAPER_COLORS[copy_type]}")
        canvas.restoreState()


def render_receipt_copies(receipt, company, selected="all"):
    copy_types = list(STANDARD_COPY_TYPES) if selected == "all" else [selected]
    stream = BytesIO()
    styles = _styles()
    story = []
    for index, copy_type in enumerate(copy_types):
        if index:
            story.extend([NextPageTemplate(copy_type), PageBreak()])
        story.extend(_receipt_story(receipt, company, copy_type, styles))
    doc = _ReceiptDoc(stream, receipt, title=f"{receipt.lr_number} LR Copies")
    doc.build(story)
    return stream.getvalue()
