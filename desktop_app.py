import os
import tempfile
import tkinter as tk
from datetime import date
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash

from app import app
from database.extensions import db
from database.models import Receipt, User
from pdf.renderer import render_receipt_copies
from services.receipt_service import create_receipt
from services.validators import ValidationError


ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class LRDesktop(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Mohan Logistics — Digital LR Book")
        self.geometry("1120x760")
        self.minsize(820, 600)
        self.user_id = None
        self.user_role = None
        logo_path = os.path.join(os.path.dirname(__file__), "static", "images", "mohan_logistics_logo.png")
        with Image.open(logo_path) as source_logo:
            self.logo_pil = source_logo.copy()
        self.logo_image = ctk.CTkImage(
            light_image=self.logo_pil,
            dark_image=self.logo_pil,
            size=(165, 90),
        )
        self._show_login()

    def _clear(self):
        for child in self.winfo_children():
            child.destroy()

    def _show_login(self):
        self._clear()
        frame = ctk.CTkFrame(self, width=420, corner_radius=14)
        frame.place(relx=.5, rely=.5, anchor="center")
        ctk.CTkLabel(frame, image=self.logo_image, text="").pack(padx=35, pady=(22, 4))
        ctk.CTkLabel(frame, text="JAI MATA DI", text_color="#9b6426").pack(padx=35, pady=(30, 5))
        ctk.CTkLabel(frame, text="Mohan Logistics LR Book", font=ctk.CTkFont(size=23, weight="bold")).pack(padx=35, pady=(0, 20))
        self.username = ctk.CTkEntry(frame, width=330, placeholder_text="Username")
        self.username.pack(padx=35, pady=7)
        self.password = ctk.CTkEntry(frame, width=330, placeholder_text="Password", show="•")
        self.password.pack(padx=35, pady=7)
        self.password.bind("<Return>", lambda _event: self._login())
        ctk.CTkButton(frame, text="Sign in", width=330, command=self._login).pack(padx=35, pady=(16, 30))

    def _login(self):
        with app.app_context():
            user = User.query.filter_by(username=self.username.get().strip(), is_active=True).first()
            if not user or not check_password_hash(user.password_hash, self.password.get()):
                messagebox.showerror("Sign in failed", "Username or password is incorrect.")
                return
            self.user_id = user.id
            self.user_role = user.role
        self._show_dashboard()

    def _show_dashboard(self):
        self._clear()
        header = ctk.CTkFrame(self, fg_color="#123a50", corner_radius=0)
        header.pack(fill="x")
        header_logo = ctk.CTkImage(
            light_image=self.logo_pil,
            dark_image=self.logo_pil,
            size=(110, 60),
        )
        ctk.CTkLabel(header, image=header_logo, text="").pack(side="left", padx=15, pady=4)
        ctk.CTkLabel(header, text="MOHAN LOGISTICS  ·  DIGITAL LR BOOK", text_color="white",
                     font=ctk.CTkFont(size=17, weight="bold")).pack(side="left", padx=12, pady=16)
        ctk.CTkButton(header, text="Log out", width=90, command=self._show_login).pack(side="right", padx=20)
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=22, pady=18)
        if self.user_role in ("admin", "operator"):
            ctk.CTkButton(actions, text="＋ Create LR", command=self._show_create).pack(side="left")
        self.search = ctk.CTkEntry(actions, width=270, placeholder_text="Search LR / vehicle / party")
        self.search.pack(side="left", padx=(18, 8))
        ctk.CTkButton(actions, text="Search", width=80, command=self._load_receipts).pack(side="left")
        self.records = ctk.CTkScrollableFrame(self, label_text="Recent receipts", corner_radius=10)
        self.records.pack(fill="both", expand=True, padx=22, pady=(0, 20))
        self._load_receipts()

    def _load_receipts(self):
        if not hasattr(self, "records"):
            return
        for child in self.records.winfo_children():
            child.destroy()
        term = self.search.get().strip()
        with app.app_context():
            query = Receipt.query
            if term:
                like = f"%{term}%"
                query = query.outerjoin(Receipt.consignor).outerjoin(Receipt.consignee).filter(
                    or_(
                        Receipt.lr_number.ilike(like),
                        Receipt.truck_number.ilike(like),
                        Receipt.trailer_number.ilike(like),
                        Receipt.consignor.property.mapper.class_.name.ilike(like),
                        Receipt.consignee.property.mapper.class_.name.ilike(like),
                    )
                ).distinct()
            receipts = query.order_by(Receipt.created_at.desc()).limit(100).all()
            for record in receipts:
                row = ctk.CTkFrame(self.records)
                row.pack(fill="x", padx=8, pady=5)
                details = f"{record.lr_number}  |  {record.receipt_date:%d-%m-%Y}  |  {record.consignor.name} → {record.consignee.name}  |  ₹{record.grand_total:,.2f}  |  {record.status}"
                ctk.CTkLabel(row, text=details, anchor="w").pack(side="left", fill="x", expand=True, padx=10, pady=11)
                ctk.CTkButton(row, text="PDF", width=64, command=lambda item=record: self._open_pdf(item.id)).pack(side="right", padx=8)
                ctk.CTkButton(row, text="View", width=64, command=lambda item=record: self._show_detail(item.id)).pack(side="right", padx=4)

    def _show_create(self):
        self._clear()
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=15)
        ctk.CTkButton(top, text="← Dashboard", width=100, command=self._show_dashboard).pack(side="left")
        ctk.CTkLabel(top, text="Create a new LR", font=ctk.CTkFont(size=22, weight="bold")).pack(side="left", padx=20)
        form = ctk.CTkScrollableFrame(self, label_text="Receipt information")
        form.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        self.fields = {}
        self.particular_fields = []
        groups = [
            ("LR Information", ["receipt_date", "cns_serial_number", "risk_type"]),
            ("Consignor", ["consignor_name", "consignor_company_name", "consignor_address", "consignor_city", "consignor_state", "consignor_pin_code", "consignor_gstin", "consignor_mobile", "consignor_contact_person"]),
            ("Consignee", ["consignee_name", "consignee_company_name", "consignee_address", "consignee_city", "consignee_state", "consignee_pin_code", "consignee_gstin", "consignee_mobile", "consignee_contact_person"]),
            ("Transport", ["from_station", "to_station", "transit_route", "trailer_number", "truck_number", "driver_name", "driver_mobile", "load_number", "packing", "package_count", "actual_weight", "charged_weight", "goods_class", "goods_description", "declared_value"]),
            ("Freight / Payment", ["charge_freight", "charge_surcharge", "charge_cover_fov", "charge_local_godown", "charge_door_delivery", "charge_cod", "charge_miscellaneous", "charge_statistical", "charge_local_collection", "payment_type", "amount_paid", "payment_remarks"]),
        ]
        for title, names in groups:
            ctk.CTkLabel(form, text=title, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=8, pady=(14, 3))
            grid = ctk.CTkFrame(form, fg_color="transparent")
            grid.pack(fill="x", padx=5)
            for index, name in enumerate(names):
                cell = ctk.CTkFrame(grid, fg_color="transparent")
                cell.grid(row=index // 3, column=index % 3, sticky="ew", padx=5, pady=5)
                grid.grid_columnconfigure(index % 3, weight=1)
                ctk.CTkLabel(cell, text=name.replace("_", " ").title()).pack(anchor="w")
                entry = ctk.CTkEntry(cell, placeholder_text="YYYY-MM-DD" if name == "receipt_date" else "")
                entry.pack(fill="x")
                self.fields[name] = entry
                if name == "receipt_date":
                    entry.insert(0, date.today().isoformat())
                elif name == "risk_type":
                    entry.insert(0, "Owner's Risk")
                elif name == "payment_type":
                    entry.insert(0, "To Pay")
                elif name.startswith("charge_") or name in ("amount_paid", "declared_value"):
                    entry.insert(0, "0")
        ctk.CTkLabel(form, text="Vehicle / invoice particulars", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=8, pady=(15, 5))
        self.particular_container = ctk.CTkFrame(form)
        self.particular_container.pack(fill="x", padx=8)
        self._add_particular_row()
        ctk.CTkButton(form, text="＋ Add particulars row", command=self._add_particular_row).pack(anchor="w", padx=8, pady=8)
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkButton(footer, text="Cancel", fg_color="#687782", command=self._show_dashboard).pack(side="right", padx=5)
        ctk.CTkButton(footer, text="Save & issue LR", command=self._save_receipt).pack(side="right", padx=5)

    def _add_particular_row(self):
        frame = ctk.CTkFrame(self.particular_container)
        frame.pack(fill="x", padx=5, pady=5)
        row = {}
        for index, name in enumerate(("chassis_number", "model", "invoice_date", "shipment_number", "invoice_number")):
            cell = ctk.CTkFrame(frame, fg_color="transparent")
            cell.grid(row=0, column=index, sticky="ew", padx=4, pady=5)
            frame.grid_columnconfigure(index, weight=1)
            ctk.CTkLabel(cell, text=name.replace("_", " ").title()).pack(anchor="w")
            row[name] = ctk.CTkEntry(cell, placeholder_text="YYYY-MM-DD" if name == "invoice_date" else "")
            row[name].pack(fill="x")
        self.particular_fields.append(row)
        ctk.CTkButton(
            frame,
            text="Remove",
            width=70,
            fg_color="#8f3a35",
            command=lambda: self._remove_particular_row(frame, row),
        ).grid(row=0, column=len(row), padx=6, pady=14)

    def _remove_particular_row(self, frame, row):
        self.particular_fields.remove(row)
        frame.destroy()

    def _save_receipt(self):
        data = {}
        for key, entry in self.fields.items():
            data[key] = entry.get().strip()
        data["consignor"] = {key.removeprefix("consignor_"): value for key, value in data.items() if key.startswith("consignor_")}
        data["consignee"] = {key.removeprefix("consignee_"): value for key, value in data.items() if key.startswith("consignee_")}
        data["charges"] = {key.removeprefix("charge_"): value for key, value in data.items() if key.startswith("charge_")}
        data["particulars"] = [{key: entry.get().strip() for key, entry in row.items()} for row in self.particular_fields]
        try:
            with app.app_context():
                receipt = create_receipt(data, self.user_id, app.config["TAX_RATE"])
                receipt_number = receipt.lr_number
        except ValidationError as exc:
            messagebox.showerror("Check receipt details", "\n".join(exc.errors))
            return
        except ValueError as exc:
            messagebox.showerror("Check receipt details", str(exc))
            return
        except SQLAlchemyError as exc:
            messagebox.showerror("Could not save receipt", str(exc))
            return
        messagebox.showinfo("LR issued", f"Receipt {receipt_number} was saved.")
        self._show_dashboard()

    def _show_detail(self, receipt_id):
        with app.app_context():
            receipt = db.session.get(Receipt, receipt_id)
            message = (
                f"{receipt.lr_number}\nDate: {receipt.receipt_date:%d-%m-%Y}\n"
                f"Consignor: {receipt.consignor.name}\nConsignee: {receipt.consignee.name}\n"
                f"Vehicle: {receipt.truck_number or '—'}\nTotal: ₹{receipt.grand_total:,.2f}\n"
                f"Status: {receipt.status}"
            )
        messagebox.showinfo("Receipt details", message)

    def _open_pdf(self, receipt_id):
        with app.app_context():
            receipt = db.session.get(Receipt, receipt_id)
            contents = render_receipt_copies(receipt, app.config["COMPANY"])
        handle, path = tempfile.mkstemp(prefix="mohan-lr-", suffix=".pdf")
        with os.fdopen(handle, "wb") as file:
            file.write(contents)
        try:
            os.startfile(path)
        except OSError as exc:
            messagebox.showerror("PDF preview failed", str(exc))


if __name__ == "__main__":
    LRDesktop().mainloop()
