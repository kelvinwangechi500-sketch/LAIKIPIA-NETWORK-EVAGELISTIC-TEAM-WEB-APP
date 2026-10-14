import io
import os
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, send_from_directory, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from extensions import db
from models.finance_asset import FinanceAsset
from models.finance_budget import FinanceBudget
from models.finance_obligation import FinanceObligation
from models.finance_report import FinanceReport
from models.finance_transaction import FinanceTransaction
from services.export_service import export_finance_excel, export_finance_pdf
from utils.decorators import admin_required, role_required


treasurer_bp = Blueprint("treasurer", __name__)
SEMESTERS = ("Semester 1", "Semester 2")
CATEGORIES = (
    "Offerings",
    "Donations",
    "Fundraising",
    "Transport",
    "Meals",
    "Printing",
    "Evangelism materials",
    "Events",
    "Welfare",
    "Equipment",
    "Communication",
    "Bank charges",
    "Other",
)
INCOME_TYPES = ("Offerings", "Donations", "Contributions", "Fundraising", "Other")
PAYMENT_METHODS = ("Cash", "M-Pesa", "Bank", "Cheque", "Other")
OBLIGATION_TYPES = ("Reimbursement", "Commitment", "Unpaid bill", "Other")
ALLOWED_RECEIPTS = {"pdf", "jpg", "jpeg", "png", "webp", "doc", "docx", "xls", "xlsx"}


def current_semester(today=None):
    today = today or date.today()
    if 9 <= today.month <= 12:
        return "Semester 1"
    if 1 <= today.month <= 4:
        return "Semester 2"
    return None


def academic_year(today=None):
    today = today or date.today()
    return today.year if today.month >= 9 else today.year - 1


def semester_start(year, semester):
    return date(year, 9, 1) if semester == "Semester 1" else date(year + 1, 1, 1)


def selected_period():
    try:
        year = int(request.args.get("year", academic_year()))
    except (TypeError, ValueError):
        year = date.today().year
    semester = request.args.get("semester") or current_semester() or "Semester 1"
    if semester not in SEMESTERS:
        semester = "Semester 1"
    return year, semester


def period_query(year, semester):
    return FinanceTransaction.query.filter_by(year=year, semester=semester)


def approved_totals(year=None, semester=None):
    query = FinanceTransaction.query.filter_by(status="approved")
    if year is not None:
        query = query.filter_by(year=year)
    if semester is not None:
        query = query.filter_by(semester=semester)
    rows = query.all()
    income = sum((row.amount for row in rows if row.transaction_type == "income"), Decimal("0"))
    expenses = sum((row.amount for row in rows if row.transaction_type == "expense"), Decimal("0"))
    return income, expenses, rows


def period_balances(year, semester):
    before = FinanceTransaction.query.filter(
        FinanceTransaction.status == "approved",
        FinanceTransaction.transaction_date < semester_start(year, semester),
    ).all()
    opening = sum((row.amount if row.transaction_type == "income" else -row.amount for row in before), Decimal("0"))
    income, expenses, rows = approved_totals(year, semester)
    return opening, income, expenses, opening + income - expenses, rows


def save_receipt(upload):
    if not upload or not upload.filename:
        return None
    original = secure_filename(upload.filename)
    if not original or "." not in original:
        raise ValueError("Choose a supported receipt file.")
    extension = original.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_RECEIPTS:
        raise ValueError("Supported receipts: PDF, Word, Excel, JPG, PNG, or WEBP.")
    stored = f"receipt_{uuid.uuid4().hex}.{extension}"
    folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    upload.save(os.path.join(folder, stored))
    return stored, original, upload.mimetype or "application/octet-stream"


@treasurer_bp.route("/dashboard")
@login_required
@role_required("treasurer")
def dashboard():
    year, semester = selected_period()
    transactions = period_query(year, semester).order_by(
        FinanceTransaction.transaction_date.desc(),
        FinanceTransaction.created_at.desc(),
    ).all()
    income, expenses, approved = approved_totals(year, semester)
    pending = sum(1 for item in transactions if item.status == "pending")
    budgets = FinanceBudget.query.filter_by(year=year, semester=semester).order_by(FinanceBudget.category).all()
    obligations = FinanceObligation.query.filter_by(year=year, semester=semester, status="outstanding").order_by(FinanceObligation.due_date).all()
    actual_by_category = {}
    for item in approved:
        if item.transaction_type == "expense":
            actual_by_category[item.category] = actual_by_category.get(item.category, Decimal("0")) + item.amount
    report_record = FinanceReport.query.filter_by(year=year, semester=semester).first()

    return render_template(
        "treasurer/dashboard.html",
        transactions=transactions[:12],
        year=year,
        semester=semester,
        semesters=SEMESTERS,
        categories=CATEGORIES,
        income_types=INCOME_TYPES,
        payment_methods=PAYMENT_METHODS,
        obligation_types=OBLIGATION_TYPES,
        budgets=budgets,
        actual_by_category=actual_by_category,
        obligations=obligations,
        report_record=report_record,
        today=date.today().isoformat(),
        current_semester=current_semester(),
        total_income=income,
        total_expenses=expenses,
        balance=income - expenses,
        pending_count=pending,
    )


@treasurer_bp.route("/transactions", methods=["POST"])
@login_required
@role_required("treasurer")
def create_transaction():
    transaction_type = request.form.get("transaction_type", "").strip().lower()
    income_type = request.form.get("income_type", "Other").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    payment_method = request.form.get("payment_method", "Cash").strip() or "Cash"
    reference_number = request.form.get("reference_number", "").strip()
    notes = request.form.get("notes", "").strip()
    transaction_date = request.form.get("transaction_date", "").strip()
    semester = request.form.get("semester", "").strip()

    errors = []
    if transaction_type not in {"income", "expense"}:
        errors.append("Choose whether this is income or an expense.")
    if transaction_type == "income" and income_type not in INCOME_TYPES:
        errors.append("Choose a valid income type.")
    if transaction_type == "expense":
        income_type = "Other"
    if not category or category not in CATEGORIES:
        errors.append("Choose a valid financial category.")
    if not description:
        errors.append("A description is required.")
    try:
        amount = Decimal(request.form.get("amount", ""))
        if amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, TypeError):
        errors.append("Enter a valid amount greater than zero.")
        amount = Decimal("0")
    try:
        parsed_date = datetime.strptime(transaction_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        errors.append("Enter a valid transaction date.")
        parsed_date = date.today()
    if semester not in SEMESTERS:
        errors.append("Choose a valid semester.")
    elif current_semester(parsed_date) is None:
        errors.append("The transaction date is outside the September-April semester calendar.")
    elif semester != current_semester(parsed_date):
        errors.append(f"The transaction date belongs to {current_semester(parsed_date)}.")
    if payment_method not in PAYMENT_METHODS:
        errors.append("Choose a valid payment method.")

    if errors:
        for error in errors:
            flash(error, "danger")
        return redirect(url_for("treasurer.dashboard"))

    try:
        receipt = save_receipt(request.files.get("receipt"))
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("treasurer.dashboard"))

    transaction = FinanceTransaction(
        transaction_type=transaction_type,
        income_type=income_type,
        amount=amount,
        category=category,
        description=description,
        reference_number=reference_number or None,
        notes=notes or None,
        transaction_date=parsed_date,
        semester=semester,
        year=academic_year(parsed_date),
        payment_method=payment_method,
        status="pending",
        submitted_by=current_user.id,
    )
    if receipt:
        transaction.receipt_file, transaction.receipt_name, transaction.receipt_mime = receipt
    db.session.add(transaction)
    db.session.commit()
    flash("Transaction submitted to the administrator for approval.", "success")
    return redirect(url_for("treasurer.dashboard", year=transaction.year, semester=semester))


@treasurer_bp.route("/report")
@login_required
@role_required("admin", "treasurer")
def report():
    year, semester = selected_period()
    opening, income, expenses, closing, transactions = period_balances(year, semester)
    budgets = FinanceBudget.query.filter_by(year=year, semester=semester).order_by(FinanceBudget.category).all()
    actual_by_category = {}
    for item in transactions:
        if item.transaction_type == "expense":
            actual_by_category[item.category] = actual_by_category.get(item.category, Decimal("0")) + item.amount
    report_record = FinanceReport.query.filter_by(year=year, semester=semester).first()
    return render_template(
        "treasurer/report.html",
        transactions=transactions,
        year=year,
        semester=semester,
        opening_balance=opening,
        total_income=income,
        total_expenses=expenses,
        balance=closing,
        budgets=budgets,
        actual_by_category=actual_by_category,
        report_record=report_record,
    )


@treasurer_bp.route("/report/export/<fmt>")
@login_required
@role_required("admin", "treasurer")
def export_report(fmt):
    year, semester = selected_period()
    opening, income, expenses, closing, transactions = period_balances(year, semester)
    budgets = FinanceBudget.query.filter_by(year=year, semester=semester).all()
    obligations = FinanceObligation.query.filter_by(year=year, semester=semester, status="outstanding").all()
    assets = FinanceAsset.query.filter(db.extract("year", FinanceAsset.purchase_date) == year).all()
    title = f"{semester} {year} Financial Report"
    if fmt == "pdf":
        content = export_finance_pdf(title, opening, income, expenses, closing, transactions, budgets, obligations, assets)
        return send_file(io.BytesIO(content), as_attachment=True, download_name=f"finance_{year}_{semester.lower().replace(' ', '_')}.pdf", mimetype="application/pdf")
    if fmt in {"xlsx", "excel"}:
        content = export_finance_excel(title, opening, income, expenses, closing, transactions, budgets, obligations, assets)
        return send_file(io.BytesIO(content), as_attachment=True, download_name=f"finance_{year}_{semester.lower().replace(' ', '_')}.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return ("Unsupported export format", 400)


@treasurer_bp.route("/report/submit", methods=["POST"])
@login_required
@role_required("treasurer")
def submit_report():
    year, semester = selected_period()
    opening, _, _, _, _ = period_balances(year, semester)
    report_record = FinanceReport.query.filter_by(year=year, semester=semester).first()
    if not report_record:
        report_record = FinanceReport(year=year, semester=semester, submitted_by=current_user.id)
        db.session.add(report_record)
    report_record.opening_balance = opening
    report_record.explanation = request.form.get("explanation", "").strip() or None
    report_record.status = "submitted"
    report_record.submitted_by = current_user.id
    db.session.commit()
    flash("Semester report submitted to leadership for review.", "success")
    return redirect(url_for("treasurer.report", year=year, semester=semester))


@treasurer_bp.route("/annual-report")
@login_required
@role_required("admin", "treasurer")
def annual_report():
    try:
        year = int(request.args.get("year", academic_year()))
    except (TypeError, ValueError):
        year = date.today().year
    income, expenses, rows = approved_totals(year=year)
    prior_rows = FinanceTransaction.query.filter(
        FinanceTransaction.status == "approved",
        FinanceTransaction.transaction_date < date(year, 9, 1),
    ).all()
    opening_balance = sum((row.amount if row.transaction_type == "income" else -row.amount for row in prior_rows), Decimal("0"))
    budgets = FinanceBudget.query.filter_by(year=year).order_by(FinanceBudget.semester, FinanceBudget.category).all()
    obligations = FinanceObligation.query.filter_by(year=year, status="outstanding").order_by(FinanceObligation.due_date).all()
    assets = FinanceAsset.query.filter(
        FinanceAsset.purchase_date >= date(year, 9, 1),
        FinanceAsset.purchase_date < date(year + 1, 5, 1),
    ).order_by(FinanceAsset.purchase_date).all()
    semester_summaries = []
    for semester in SEMESTERS:
        opening, semester_income, semester_expenses, closing, _ = period_balances(year, semester)
        semester_summaries.append({
            "semester": semester,
            "opening": opening,
            "income": semester_income,
            "expenses": semester_expenses,
            "closing": closing,
        })
    return render_template(
        "treasurer/annual_report.html",
        year=year,
        transactions=rows,
        opening_balance=opening_balance,
        total_income=income,
        total_expenses=expenses,
        closing_balance=opening_balance + income - expenses,
        budgets=budgets,
        obligations=obligations,
        assets=assets,
        semester_summaries=semester_summaries,
    )


@treasurer_bp.route("/annual-report/export/<fmt>")
@login_required
@role_required("admin", "treasurer")
def export_annual_report(fmt):
    try:
        year = int(request.args.get("year", academic_year()))
    except (TypeError, ValueError):
        year = date.today().year
    income, expenses, transactions = approved_totals(year=year)
    prior_rows = FinanceTransaction.query.filter(
        FinanceTransaction.status == "approved",
        FinanceTransaction.transaction_date < date(year, 9, 1),
    ).all()
    opening = sum((row.amount if row.transaction_type == "income" else -row.amount for row in prior_rows), Decimal("0"))
    closing = opening + income - expenses
    budgets = FinanceBudget.query.filter_by(year=year).all()
    obligations = FinanceObligation.query.filter_by(year=year, status="outstanding").all()
    assets = FinanceAsset.query.filter(
        FinanceAsset.purchase_date >= date(year, 9, 1),
        FinanceAsset.purchase_date < date(year + 1, 5, 1),
    ).all()
    title = f"Annual Financial Report {year}"
    if fmt == "pdf":
        content = export_finance_pdf(title, opening, income, expenses, closing, transactions, budgets, obligations, assets)
        return send_file(io.BytesIO(content), as_attachment=True, download_name=f"finance_annual_{year}.pdf", mimetype="application/pdf")
    if fmt in {"xlsx", "excel"}:
        content = export_finance_excel(title, opening, income, expenses, closing, transactions, budgets, obligations, assets)
        return send_file(io.BytesIO(content), as_attachment=True, download_name=f"finance_annual_{year}.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return ("Unsupported export format", 400)


@treasurer_bp.route("/budgets", methods=["POST"])
@login_required
@role_required("treasurer")
def create_budget():
    try:
        amount = Decimal(request.form.get("amount", ""))
        year = int(request.form.get("year", date.today().year))
    except (InvalidOperation, TypeError, ValueError):
        flash("Enter a valid budget amount and year.", "danger")
        return redirect(url_for("treasurer.dashboard"))
    semester = request.form.get("semester", "").strip()
    category = request.form.get("category", "").strip()
    if amount <= 0 or semester not in SEMESTERS or category not in CATEGORIES:
        flash("Choose a valid semester, category, and positive budget amount.", "danger")
        return redirect(url_for("treasurer.dashboard"))
    budget = FinanceBudget.query.filter_by(year=year, semester=semester, category=category).first()
    if not budget:
        budget = FinanceBudget(year=year, semester=semester, category=category, created_by=current_user.id)
        db.session.add(budget)
    budget.amount = amount
    budget.notes = request.form.get("notes", "").strip() or None
    db.session.commit()
    flash("Semester budget saved.", "success")
    return redirect(url_for("treasurer.dashboard", year=year, semester=semester))


@treasurer_bp.route("/obligations", methods=["POST"])
@login_required
@role_required("treasurer")
def create_obligation():
    try:
        amount = Decimal(request.form.get("amount", ""))
        due_date = datetime.strptime(request.form.get("due_date", ""), "%Y-%m-%d").date() if request.form.get("due_date") else None
        year = int(request.form.get("year", date.today().year))
    except (InvalidOperation, TypeError, ValueError):
        flash("Enter valid obligation amount, date, and year.", "danger")
        return redirect(url_for("treasurer.dashboard"))
    semester = request.form.get("semester", "").strip()
    category = request.form.get("category", "").strip()
    obligation_type = request.form.get("obligation_type", "Commitment").strip()
    description = request.form.get("description", "").strip()
    if amount <= 0 or semester not in SEMESTERS or category not in CATEGORIES or obligation_type not in OBLIGATION_TYPES or not description:
        flash("Complete the obligation details with a positive amount.", "danger")
        return redirect(url_for("treasurer.dashboard"))
    db.session.add(FinanceObligation(
        description=description, obligation_type=obligation_type, category=category, amount=amount, due_date=due_date,
        semester=semester, year=year, reference_number=request.form.get("reference_number", "").strip() or None,
        notes=request.form.get("notes", "").strip() or None, created_by=current_user.id,
    ))
    db.session.commit()
    flash("Outstanding obligation recorded.", "success")
    return redirect(url_for("treasurer.dashboard", year=year, semester=semester))


@treasurer_bp.route("/obligations/<int:obligation_id>/paid", methods=["POST"])
@login_required
@role_required("treasurer", "admin")
def mark_obligation_paid(obligation_id):
    obligation = FinanceObligation.query.get_or_404(obligation_id)
    obligation.status = "paid"
    db.session.commit()
    flash("Obligation marked as paid.", "success")
    return redirect(url_for("treasurer.dashboard", year=obligation.year, semester=obligation.semester))


@treasurer_bp.route("/assets", methods=["POST"])
@login_required
@role_required("treasurer")
def create_asset():
    try:
        amount = Decimal(request.form.get("purchase_amount", ""))
        purchase_date = datetime.strptime(request.form.get("purchase_date", ""), "%Y-%m-%d").date()
    except (InvalidOperation, TypeError, ValueError):
        flash("Enter a valid asset amount and purchase date.", "danger")
        return redirect(url_for("treasurer.dashboard"))
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    if not name or category not in CATEGORIES or amount <= 0:
        flash("Complete the asset details with a positive amount.", "danger")
        return redirect(url_for("treasurer.dashboard"))
    db.session.add(FinanceAsset(
        name=name, category=category, purchase_amount=amount, purchase_date=purchase_date,
        condition=request.form.get("condition", "Good").strip() or "Good",
        location=request.form.get("location", "").strip() or None,
        notes=request.form.get("notes", "").strip() or None, created_by=current_user.id,
    ))
    db.session.commit()
    flash("Asset recorded.", "success")
    return redirect(url_for("treasurer.dashboard"))


@treasurer_bp.route("/receipts/<int:transaction_id>")
@login_required
@role_required("admin", "treasurer")
def receipt(transaction_id):
    transaction = FinanceTransaction.query.get_or_404(transaction_id)
    if not transaction.receipt_file:
        return ("Receipt not found", 404)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], transaction.receipt_file, as_attachment=False)


@treasurer_bp.route("/admin/finance")
@login_required
@admin_required
def admin_finance():
    transactions = FinanceTransaction.query.order_by(
        FinanceTransaction.status.asc(),
        FinanceTransaction.transaction_date.desc(),
    ).all()
    reports = FinanceReport.query.order_by(FinanceReport.year.desc(), FinanceReport.semester).all()
    return render_template("admin/finance.html", transactions=transactions, reports=reports)


@treasurer_bp.route("/admin/reports/<int:report_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_report(report_id):
    report_record = FinanceReport.query.get_or_404(report_id)
    report_record.status = "approved"
    report_record.reviewed_by = current_user.id
    report_record.reviewed_at = datetime.utcnow()
    report_record.review_notes = request.form.get("review_notes", "").strip() or None
    db.session.commit()
    flash("Financial report approved and shared with leadership.", "success")
    return redirect(url_for("treasurer.admin_finance"))


@treasurer_bp.route("/admin/reports/<int:report_id>/reject", methods=["POST"])
@login_required
@admin_required
def reject_report(report_id):
    report_record = FinanceReport.query.get_or_404(report_id)
    report_record.status = "rejected"
    report_record.reviewed_by = current_user.id
    report_record.reviewed_at = datetime.utcnow()
    report_record.review_notes = request.form.get("review_notes", "").strip() or "Please revise and resubmit."
    db.session.commit()
    flash("Financial report returned to the treasurer.", "warning")
    return redirect(url_for("treasurer.admin_finance"))


@treasurer_bp.route("/admin/finance/<int:transaction_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_transaction(transaction_id):
    transaction = FinanceTransaction.query.get_or_404(transaction_id)
    transaction.status = "approved"
    transaction.rejection_reason = None
    transaction.approved_by = current_user.id
    transaction.approved_at = datetime.utcnow()
    db.session.commit()
    flash("Financial transaction approved.", "success")
    return redirect(url_for("treasurer.admin_finance"))


@treasurer_bp.route("/admin/finance/<int:transaction_id>/reject", methods=["POST"])
@login_required
@admin_required
def reject_transaction(transaction_id):
    transaction = FinanceTransaction.query.get_or_404(transaction_id)
    transaction.status = "rejected"
    transaction.rejection_reason = request.form.get("reason", "").strip() or "Please review and resubmit."
    transaction.approved_by = current_user.id
    transaction.approved_at = datetime.utcnow()
    db.session.commit()
    flash("Financial transaction rejected and returned to the treasurer.", "warning")
    return redirect(url_for("treasurer.admin_finance"))
