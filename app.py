import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import wraps
from urllib.parse import urlparse

import click
from openpyxl import Workbook
from dotenv import load_dotenv

load_dotenv()

from config import Config
from flask import (
    Flask,
    abort,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import extract, or_
from sqlalchemy.exc import SQLAlchemyError

from database.extensions import csrf, db, login_manager
from database.models import (
    AuditLog,
    CompanySetting,
    Consignee,
    Consignor,
    Receipt,
    ReceiptParticular,
    User,
)
from pdf.renderer import render_receipt_copies
from services.receipt_service import create_receipt
from services.validators import ValidationError


COMPANY_SETTING_FIELDS = {
    "company_name": "name",
    "tagline": "tagline",
    "jurisdiction": "jurisdiction",
    "registered_office": "registered_office",
    "address": "address",
    "corporate_office": "corporate_office",
    "email": "email",
    "gstin": "gstin",
}


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY is required. Set it in your local .env file.")
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("DATABASE_URL is required. Set it in your local .env file.")
    try:
        tax_rate = Decimal(str(app.config.get("TAX_RATE", "0")))
    except InvalidOperation as exc:
        raise RuntimeError("TAX_RATE must be a decimal percentage from 0 to 100.") from exc
    if not tax_rate.is_finite() or not Decimal("0") <= tax_rate <= Decimal("100"):
        raise RuntimeError("TAX_RATE must be a decimal percentage from 0 to 100.")
    app.config["TAX_RATE"] = tax_rate

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    def roles_required(*roles):
        def decorate(view):
            @wraps(view)
            @login_required
            def wrapped(*args, **kwargs):
                if current_user.role not in roles:
                    abort(403)
                return view(*args, **kwargs)
            return wrapped
        return decorate

    def company_settings():
        company = dict(current_app.config["COMPANY"])
        stored = {setting.key: setting.value for setting in CompanySetting.query.all()}
        for key, company_key in COMPANY_SETTING_FIELDS.items():
            if key in stored:
                company[company_key] = stored[key]
        tax_rate = Decimal(stored.get("tax_rate", str(current_app.config["TAX_RATE"])))
        return company, tax_rate

    def export_query():
        query = Receipt.query.outerjoin(Consignor).outerjoin(Consignee)
        status = request.args.get("status", "").strip()
        start = request.args.get("start", "").strip()
        end = request.args.get("end", "").strip()
        consignor = request.args.get("consignor", "").strip()
        consignee = request.args.get("consignee", "").strip()
        vehicle = request.args.get("vehicle", "").strip()
        payment_status = request.args.get("payment_status", "").strip()
        if status in {"Issued", "Cancelled"}:
            query = query.filter(Receipt.status == status)
        if start:
            try:
                query = query.filter(Receipt.receipt_date >= date.fromisoformat(start))
            except ValueError:
                abort(400, description="Invalid export start date.")
        if end:
            try:
                query = query.filter(Receipt.receipt_date <= date.fromisoformat(end))
            except ValueError:
                abort(400, description="Invalid export end date.")
        if consignor:
            query = query.filter(Consignor.name.ilike(f"%{consignor}%"))
        if consignee:
            query = query.filter(Consignee.name.ilike(f"%{consignee}%"))
        if vehicle:
            pattern = f"%{vehicle}%"
            query = query.filter(or_(Receipt.truck_number.ilike(pattern), Receipt.trailer_number.ilike(pattern)))
        if payment_status in {"Paid", "Partial", "Pending"}:
            query = query.filter(Receipt.payment_status == payment_status)
        return query.distinct().order_by(Receipt.receipt_date, Receipt.sequence_number)

    @app.cli.command("init-db")
    def init_db():
        """Create the MySQL tables for a new installation."""
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("create-admin")
    def create_admin():
        """Create the first administrator using hidden interactive prompts."""
        if User.query.filter_by(role="admin").first():
            raise click.ClickException("An administrator already exists.")
        username = click.prompt("Administrator username").strip()
        if not username:
            raise click.ClickException("Username cannot be empty.")
        if User.query.filter_by(username=username).first():
            raise click.ClickException("That username already exists.")
        password = click.prompt("Administrator password", hide_input=True, confirmation_prompt=True)
        if len(password) < 12:
            raise click.ClickException("Use a password with at least 12 characters.")
        db.session.add(
            User(
                username=username,
                password_hash=generate_password_hash(password),
                role="admin",
            )
        )
        db.session.commit()
        click.echo("Administrator created.")

    @app.cli.command("create-user")
    def create_user():
        """Create an operator or viewer account."""
        username = click.prompt("Username").strip()
        if not username or User.query.filter_by(username=username).first():
            raise click.ClickException("Username is empty or already exists.")
        role = click.prompt("Role", type=click.Choice(["operator", "viewer"]))
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
        if len(password) < 12:
            raise click.ClickException("Use a password with at least 12 characters.")
        db.session.add(
            User(
                username=username,
                password_hash=generate_password_hash(password),
                role=role,
            )
        )
        db.session.commit()
        click.echo(f"{role.title()} account created.")

    @app.get("/manifest.webmanifest")
    def web_manifest():
        response = current_app.send_static_file("manifest.webmanifest")
        response.headers["Content-Type"] = "application/manifest+json"
        return response

    @app.get("/service-worker.js")
    def service_worker():
        response = current_app.send_static_file("service-worker.js")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    @app.get("/")
    def home():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter_by(username=username, is_active=True).first()
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                next_path = request.args.get("next", "")
                parsed = urlparse(next_path)
                if (
                    next_path.startswith("/")
                    and not next_path.startswith("//")
                    and "\\" not in next_path
                    and not parsed.netloc
                ):
                    return redirect(next_path)
                return redirect(url_for("dashboard"))
            flash("Username or password is incorrect.", "error")
        return render_template("login.html")

    @app.post("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/account/password", methods=["GET", "POST"])
    @login_required
    def change_password():
        if request.method == "POST":
            old_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")
            if not check_password_hash(current_user.password_hash, old_password):
                flash("Current password is incorrect.", "error")
            elif len(new_password) < 12:
                flash("New password must contain at least 12 characters.", "error")
            elif new_password != confirm_password:
                flash("New password and confirmation do not match.", "error")
            elif check_password_hash(current_user.password_hash, new_password):
                flash("Choose a password different from your current password.", "error")
            else:
                current_user.password_hash = generate_password_hash(new_password)
                db.session.add(
                    AuditLog(
                        user_id=current_user.id,
                        action="password_changed",
                        details="User changed their account password.",
                    )
                )
                db.session.commit()
                flash("Password changed successfully.", "success")
                return redirect(url_for("dashboard"))
        return render_template("change_password.html")

    @app.get("/dashboard")
    @roles_required("admin", "operator", "viewer")
    def dashboard():
        today = date.today()
        receipts = Receipt.query.order_by(Receipt.created_at.desc()).limit(12).all()
        total = Receipt.query.count()
        today_count = Receipt.query.filter(Receipt.receipt_date == today).count()
        month_count = Receipt.query.filter(
            extract("year", Receipt.receipt_date) == today.year,
            extract("month", Receipt.receipt_date) == today.month,
        ).count()
        cancelled_count = Receipt.query.filter_by(status="Cancelled").count()
        return render_template(
            "dashboard.html",
            receipts=receipts,
            total=total,
            today_count=today_count,
            month_count=month_count,
            cancelled_count=cancelled_count,
        )

    @app.route("/receipts/new", methods=["GET", "POST"])
    @roles_required("admin", "operator")
    def new_receipt():
        errors = []
        if request.method == "POST":
            data = _receipt_form_data(request.form)
            try:
                receipt = create_receipt(data, current_user.id, company_settings()[1])
            except ValidationError as exc:
                errors = exc.errors
            except ValueError as exc:
                errors = [str(exc)]
            except SQLAlchemyError:
                current_app.logger.exception("Database error issuing an LR")
                errors = ["Database error while saving. No receipt was issued; a number may be skipped. Please retry."]
            else:
                flash(f"Receipt {receipt.lr_number} was issued successfully.", "success")
                return redirect(url_for("receipt_detail", receipt_id=receipt.id))
            return render_template(
                "receipt_form.html",
                errors=errors,
                form=request.form,
                consignors=Consignor.query.order_by(Consignor.name).all(),
                consignees=Consignee.query.order_by(Consignee.name).all(),
                tax_rate=company_settings()[1],
            )
        return render_template(
            "receipt_form.html",
            errors=errors,
            form={},
            consignors=Consignor.query.order_by(Consignor.name).all(),
            consignees=Consignee.query.order_by(Consignee.name).all(),
            tax_rate=company_settings()[1],
        )

    @app.get("/receipts")
    @roles_required("admin", "operator", "viewer")
    def receipt_list():
        query = Receipt.query
        term = request.args.get("q", "").strip()
        status = request.args.get("status", "").strip()
        start = request.args.get("start", "").strip()
        end = request.args.get("end", "").strip()
        if term:
            pattern = f"%{term}%"
            query = query.outerjoin(Consignor).outerjoin(Consignee).filter(
                or_(
                    Receipt.lr_number.ilike(pattern),
                    Receipt.truck_number.ilike(pattern),
                    Receipt.trailer_number.ilike(pattern),
                    Consignor.name.ilike(pattern),
                    Consignee.name.ilike(pattern),
                    Receipt.particulars.any(
                        or_(
                            ReceiptParticular.invoice_number.ilike(pattern),
                            ReceiptParticular.shipment_number.ilike(pattern),
                            ReceiptParticular.chassis_number.ilike(pattern),
                        )
                    ),
                )
            ).distinct()
        if status in {"Issued", "Cancelled"}:
            query = query.filter(Receipt.status == status)
        if start:
            try:
                query = query.filter(Receipt.receipt_date >= date.fromisoformat(start))
            except ValueError:
                flash("Start date is invalid.", "error")
        if end:
            try:
                query = query.filter(Receipt.receipt_date <= date.fromisoformat(end))
            except ValueError:
                flash("End date is invalid.", "error")
        receipts = query.order_by(Receipt.receipt_date.desc(), Receipt.sequence_number.desc()).limit(250).all()
        return render_template("receipt_list.html", receipts=receipts)

    @app.get("/reports")
    @roles_required("admin", "operator", "viewer")
    def reports():
        query = Receipt.query.outerjoin(Consignor).outerjoin(Consignee)
        filters = {
            "start": request.args.get("start", "").strip(),
            "end": request.args.get("end", "").strip(),
            "consignor": request.args.get("consignor", "").strip(),
            "consignee": request.args.get("consignee", "").strip(),
            "vehicle": request.args.get("vehicle", "").strip(),
            "status": request.args.get("status", "").strip(),
            "payment_status": request.args.get("payment_status", "").strip(),
        }
        for key in ("start", "end"):
            if filters[key]:
                try:
                    selected_date = date.fromisoformat(filters[key])
                except ValueError:
                    flash(f"{key.title()} date is invalid.", "error")
                    continue
                condition = Receipt.receipt_date >= selected_date if key == "start" else Receipt.receipt_date <= selected_date
                query = query.filter(condition)
        if filters["consignor"]:
            query = query.filter(Consignor.name.ilike(f"%{filters['consignor']}%"))
        if filters["consignee"]:
            query = query.filter(Consignee.name.ilike(f"%{filters['consignee']}%"))
        if filters["vehicle"]:
            pattern = f"%{filters['vehicle']}%"
            query = query.filter(or_(Receipt.truck_number.ilike(pattern), Receipt.trailer_number.ilike(pattern)))
        if filters["status"] in {"Issued", "Cancelled"}:
            query = query.filter(Receipt.status == filters["status"])
        if filters["payment_status"] in {"Paid", "Partial", "Pending"}:
            query = query.filter(Receipt.payment_status == filters["payment_status"])
        receipts = query.distinct().order_by(Receipt.receipt_date, Receipt.sequence_number).limit(1000).all()
        return render_template(
            "reports.html",
            receipts=receipts,
            filters=filters,
            receipt_count=len(receipts),
            freight_total=sum((receipt.grand_total for receipt in receipts), Decimal("0.00")),
        )

    @app.get("/receipts/export.csv")
    @roles_required("admin", "operator", "viewer")
    def export_receipts():
        receipts = export_query().all()
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(
            ["LR Number", "Date", "Consignor", "Consignee", "Truck", "Freight Total", "Payment Status", "Status"]
        )
        for receipt in receipts:
            def safe_cell(value):
                text = "" if value is None else str(value)
                return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text

            writer.writerow(
                [
                    safe_cell(receipt.lr_number),
                    receipt.receipt_date.isoformat(),
                    safe_cell(receipt.consignor.name),
                    safe_cell(receipt.consignee.name),
                    safe_cell(receipt.truck_number),
                    receipt.grand_total,
                    receipt.payment_status,
                    receipt.status,
                ]
            )
        response = make_response(stream.getvalue())
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = "attachment; filename=lr-register.csv"
        return response

    @app.get("/receipts/export.xlsx")
    @roles_required("admin", "operator", "viewer")
    def export_receipts_xlsx():
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "LR Register"
        sheet.append(
            ["LR Number", "Date", "Consignor", "Consignee", "Truck", "Freight Total", "Payment Status", "Status"]
        )
        for receipt in export_query().all():
            safe_values = [
                receipt.lr_number,
                receipt.receipt_date.isoformat(),
                receipt.consignor.name,
                receipt.consignee.name,
                receipt.truck_number or "",
                float(receipt.grand_total),
                receipt.payment_status,
                receipt.status,
            ]
            row = []
            for value in safe_values:
                text = "" if value is None else str(value)
                row.append(f"'{text}" if text.startswith(("=", "+", "-", "@")) else value)
            sheet.append(row)
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        sheet.column_dimensions["A"].width = 24
        sheet.column_dimensions["C"].width = 28
        sheet.column_dimensions["D"].width = 28
        sheet.column_dimensions["F"].width = 18
        for cell in sheet["F"][1:]:
            cell.number_format = '#,##0.00'
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="lr-register.xlsx",
        )

    @app.get("/receipts/<int:receipt_id>")
    @roles_required("admin", "operator", "viewer")
    def receipt_detail(receipt_id):
        receipt = db.get_or_404(Receipt, receipt_id)
        return render_template("receipt_detail.html", receipt=receipt)

    @app.get("/receipts/<int:receipt_id>/pdf")
    @roles_required("admin", "operator", "viewer")
    def receipt_pdf(receipt_id):
        receipt = db.get_or_404(Receipt, receipt_id)
        copy_type = request.args.get("copy", "all")
        allowed = {"all", "consignor", "consignee", "driver", "record", "extra", "white_consignor"}
        if copy_type not in allowed:
            abort(400)
        if receipt.status == "Cancelled":
            flash("This receipt is cancelled; its PDF is available for record purposes only.", "warning")
        company, _tax_rate = company_settings()
        output = render_receipt_copies(receipt, company, copy_type)
        suffix = "all-copies" if copy_type == "all" else copy_type.replace("_", "-")
        return send_file(
            io.BytesIO(output),
            mimetype="application/pdf",
            as_attachment=request.args.get("download") == "1",
            download_name=f"{receipt.lr_number.replace('/', '-')}-{suffix}.pdf",
        )

    @app.post("/receipts/<int:receipt_id>/cancel")
    @roles_required("admin")
    def cancel_receipt(receipt_id):
        receipt = db.get_or_404(Receipt, receipt_id)
        if receipt.status != "Issued":
            flash("Only issued receipts can be cancelled.", "error")
        else:
            receipt.status = "Cancelled"
            db.session.add(
                AuditLog(
                    user_id=current_user.id,
                    receipt_id=receipt.id,
                    action="receipt_cancelled",
                    details=f"Cancelled {receipt.lr_number}",
                )
            )
            db.session.commit()
            flash(f"{receipt.lr_number} was cancelled. Its number remains reserved.", "success")
        return redirect(url_for("receipt_detail", receipt_id=receipt.id))

    @app.get("/admin/audit")
    @roles_required("admin")
    def audit_log():
        entries = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(300).all()
        return render_template("audit_log.html", entries=entries)

    @app.route("/admin/users", methods=["GET", "POST"])
    @roles_required("admin")
    def manage_users():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            role = request.form.get("role", "")
            password = request.form.get("password", "")
            if not username or len(username) > 80:
                flash("Username must contain 1 to 80 characters.", "error")
            elif User.query.filter_by(username=username).first():
                flash("That username already exists.", "error")
            elif role not in {"admin", "operator", "viewer"}:
                flash("Select a valid role.", "error")
            elif len(password) < 12:
                flash("Use a password with at least 12 characters.", "error")
            else:
                db.session.add(
                    User(
                        username=username,
                        password_hash=generate_password_hash(password),
                        role=role,
                    )
                )
                db.session.add(
                    AuditLog(
                        user_id=current_user.id,
                        action="user_created",
                        details=f"Created {role} account {username}",
                    )
                )
                db.session.commit()
                flash(f"{role.title()} account created.", "success")
                return redirect(url_for("manage_users"))
        users = User.query.order_by(User.username).all()
        return render_template("users.html", users=users)

    @app.post("/admin/users/<int:user_id>/toggle")
    @roles_required("admin")
    def toggle_user(user_id):
        user = db.get_or_404(User, user_id)
        if user.id == current_user.id and user.is_active:
            flash("You cannot deactivate your own account.", "error")
        elif user.role == "admin" and user.is_active and User.query.filter_by(
            role="admin", is_active=True
        ).count() <= 1:
            flash("At least one active administrator must remain.", "error")
        else:
            user.is_active = not user.is_active
            db.session.add(
                AuditLog(
                    user_id=current_user.id,
                    action="user_activated" if user.is_active else "user_deactivated",
                    details=f"Changed account status for {user.username}",
                )
            )
            db.session.commit()
            flash(f"{user.username} is now {'active' if user.is_active else 'inactive'}.", "success")
        return redirect(url_for("manage_users"))

    @app.route("/admin/settings", methods=["GET", "POST"])
    @roles_required("admin")
    def manage_settings():
        if request.method == "POST":
            values = {key: request.form.get(key, "").strip() for key in COMPANY_SETTING_FIELDS}
            values["tax_rate"] = request.form.get("tax_rate", "").strip()
            try:
                tax_rate = Decimal(values["tax_rate"])
            except InvalidOperation:
                tax_rate = Decimal("-1")
            if not values["company_name"]:
                flash("Company name is required.", "error")
            elif not tax_rate.is_finite() or not Decimal("0") <= tax_rate <= Decimal("100"):
                flash("Tax rate must be a percentage from 0 to 100.", "error")
            else:
                for key, value in values.items():
                    setting = db.session.get(CompanySetting, key)
                    if setting is None:
                        db.session.add(CompanySetting(key=key, value=value))
                    else:
                        setting.value = value
                db.session.add(
                    AuditLog(
                        user_id=current_user.id,
                        action="company_settings_updated",
                        details="Updated company and tax configuration.",
                    )
                )
                db.session.commit()
                flash("Company settings saved.", "success")
                return redirect(url_for("manage_settings"))
        company, tax_rate = company_settings()
        values = {key: company.get(company_key, "") for key, company_key in COMPANY_SETTING_FIELDS.items()}
        values["tax_rate"] = str(tax_rate)
        return render_template("settings.html", values=values)

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", title="Access denied", message="Your account is not permitted to perform this action."), 403

    return app


def _receipt_form_data(form):
    def party(prefix):
        return {
            "name": form.get(f"{prefix}_name", ""),
            "company_name": form.get(f"{prefix}_company_name", ""),
            "address": form.get(f"{prefix}_address", ""),
            "city": form.get(f"{prefix}_city", ""),
            "state": form.get(f"{prefix}_state", ""),
            "pin_code": form.get(f"{prefix}_pin_code", ""),
            "gstin": form.get(f"{prefix}_gstin", ""),
            "mobile": form.get(f"{prefix}_mobile", ""),
            "contact_person": form.get(f"{prefix}_contact_person", ""),
        }

    row_values = {
        key: form.getlist(f"particular_{key}[]")
        for key in ("chassis_number", "model", "invoice_date", "shipment_number", "invoice_number")
    }
    particulars = []
    count = max((len(values) for values in row_values.values()), default=0)
    for index in range(count):
        particulars.append({key: values[index] if index < len(values) else "" for key, values in row_values.items()})

    return {
        "receipt_date": form.get("receipt_date", ""),
        "cns_serial_number": form.get("cns_serial_number", ""),
        "consignor": party("consignor"),
        "consignee": party("consignee"),
        "from_station": form.get("from_station", ""),
        "to_station": form.get("to_station", ""),
        "transit_route": form.get("transit_route", ""),
        "risk_type": form.get("risk_type", "Owner's Risk"),
        "trailer_number": form.get("trailer_number", ""),
        "truck_number": form.get("truck_number", ""),
        "driver_name": form.get("driver_name", ""),
        "driver_mobile": form.get("driver_mobile", ""),
        "load_number": form.get("load_number", ""),
        "packing": form.get("packing", ""),
        "package_count": form.get("package_count", ""),
        "actual_weight": form.get("actual_weight", ""),
        "charged_weight": form.get("charged_weight", ""),
        "goods_class": form.get("goods_class", ""),
        "goods_description": form.get("goods_description", ""),
        "declared_value": form.get("declared_value", "0"),
        "charges": {name: form.get(f"charge_{name}", "0") for name in (
            "freight", "surcharge", "cover_fov", "local_godown", "door_delivery",
            "cod", "miscellaneous", "statistical", "local_collection",
        )},
        "payment_type": form.get("payment_type", ""),
        "amount_paid": form.get("amount_paid", "0"),
        "payment_remarks": form.get("payment_remarks", ""),
        "particulars": particulars,
    }


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=app.config.get("DEBUG", False))
