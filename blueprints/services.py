"""
blueprints/services.py — Service booking routes for ChimneyCare.

Handles AMC plans, one-time cleaning, booking submission (with instant
confirmation), and customer booking history.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from supabase_client import get_supabase_client
from utils import login_required, generate_order_id, generate_service_id, sanitize_string

services_bp = Blueprint("services", __name__)


@services_bp.route("/")
def landing():
    """Public landing page."""
    try:
        sb = get_supabase_client()
        plans = sb.table("amc_plans").select("*").eq("active", True).order("duration_months").execute()
        amc_plans = plans.data if plans.data else []
    except Exception:
        amc_plans = []

    return render_template("index.html", amc_plans=amc_plans)


@services_bp.route("/dashboard")
@login_required
def dashboard():
    """Customer dashboard — overview of bookings, repair jobs, orders."""
    user = session["user"]
    sb = get_supabase_client()

    try:
        bookings = (
            sb.table("services")
            .select("*")
            .eq("customer_id", user["id"])
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        repair_jobs = (
            sb.table("repair_jobs")
            .select("*")
            .eq("customer_id", user["id"])
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        orders = (
            sb.table("orders")
            .select("*")
            .eq("customer_id", user["id"])
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
    except Exception:
        bookings = type("obj", (object,), {"data": []})()
        repair_jobs = type("obj", (object,), {"data": []})()
        orders = type("obj", (object,), {"data": []})()

    return render_template(
        "dashboard.html",
        bookings=bookings.data or [],
        repair_jobs=repair_jobs.data or [],
        orders=orders.data or [],
    )


@services_bp.route("/services")
def services_index():
    """Display all available services — AMC plans and one-time cleaning."""
    try:
        sb = get_supabase_client()
        plans = sb.table("amc_plans").select("*").eq("active", True).order("duration_months").execute()
        amc_plans = plans.data if plans.data else []
    except Exception:
        amc_plans = []

    return render_template("services/index.html", amc_plans=amc_plans)


@services_bp.route("/services/amc")
def amc_plans():
    """Detailed AMC plan comparison page."""
    try:
        sb = get_supabase_client()
        plans = sb.table("amc_plans").select("*").eq("active", True).order("duration_months").execute()
        amc_plans = plans.data if plans.data else []
    except Exception:
        amc_plans = []

    return render_template("services/amc.html", amc_plans=amc_plans)


@services_bp.route("/services/book", methods=["GET", "POST"])
@login_required
def book_service():
    """Book an AMC plan or one-time cleaning service."""
    if request.method == "GET":
        try:
            sb = get_supabase_client()
            plans = sb.table("amc_plans").select("*").eq("active", True).order("duration_months").execute()
            amc_plans = plans.data if plans.data else []
        except Exception:
            amc_plans = []

        service_type = request.args.get("type", "one_time")
        plan_id = request.args.get("plan_id", "")
        return render_template("services/book.html", amc_plans=amc_plans, service_type=service_type, plan_id=plan_id)

    # ── POST: process booking ──
    user = session["user"]
    service_type = sanitize_string(request.form.get("service_type", "one_time"))
    plan_id = request.form.get("plan_id") or None
    notes = sanitize_string(request.form.get("notes", ""), max_length=1000)
    labour_charge = 0

    # Validation
    if service_type not in ("amc", "one_time", "cleaning"):
        flash("Invalid service type.", "error")
        return redirect(url_for("services.book_service"))

    try:
        labour_charge_raw = request.form.get("labour_charge", "0")
        labour_charge = float(labour_charge_raw) if labour_charge_raw else 0
    except ValueError:
        labour_charge = 0

    if service_type == "amc" and not plan_id:
        flash("Please select an AMC plan.", "error")
        return redirect(url_for("services.book_service", type="amc"))

    order_id = generate_order_id()
    service_id = generate_service_id()

    try:
        from supabase_client import get_admin_client
        sb = get_admin_client()

        booking_data = {
            "customer_id": user["id"],
            "type": service_type,
            "plan_id": plan_id,
            "status": "confirmed",  # Instant confirmation
            "labour_charge": labour_charge,
            "order_id": order_id,
            "service_id": service_id,
            "notes": notes,
        }

        result = sb.table("services").insert(booking_data).execute()

        if result.data:
            flash(f"Booking confirmed! Order ID: {order_id} | Service ID: {service_id}", "success")
            return redirect(url_for("services.my_bookings"))
        else:
            flash("Booking failed. Please try again.", "error")
            return redirect(url_for("services.book_service"))

    except Exception as e:
        flash(f"Error creating booking: {str(e)}", "error")
        return redirect(url_for("services.book_service"))


@services_bp.route("/services/my-bookings")
@login_required
def my_bookings():
    """View all customer bookings."""
    user = session["user"]

    try:
        sb = get_supabase_client()
        result = (
            sb.table("services")
            .select("*, amc_plans(*)")
            .eq("customer_id", user["id"])
            .order("created_at", desc=True)
            .execute()
        )
        bookings = result.data if result.data else []
    except Exception:
        bookings = []

    return render_template("services/my_bookings.html", bookings=bookings)
