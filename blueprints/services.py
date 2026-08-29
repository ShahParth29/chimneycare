"""
blueprints/services.py — Service booking routes for ChimneyCare.

Handles AMC plans, one-time cleaning, booking submission (with instant
confirmation), customer booking history, and contact/informational pages.
"""

import os
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from supabase_client import get_supabase_client, get_admin_client
from utils import (
    login_required, generate_order_id, generate_booking_id, generate_service_id, sanitize_string,
    send_whatsapp_message, validate_email_strict, validate_phone_strict,
    validate_name_strict, validate_enum, validate_text_field
)

logger = logging.getLogger("chimneycare.services")
services_bp = Blueprint("services", __name__)


@services_bp.route("/")
def landing():
    """Public landing page."""
    try:
        sb = get_supabase_client()
        plans = sb.table("amc_plans").select("*").eq("active", True).order("duration_months").execute()
        amc_plans = plans.data if plans.data else []
    except Exception as e:
        logger.error(f"Error fetching AMC plans for landing: {e}")
        amc_plans = []

    return render_template("index.html", amc_plans=amc_plans)


@services_bp.route("/dashboard")
@login_required
def dashboard():
    """Customer Dashboard — overview of active bookings, repairs, and orders."""
    user = session["user"]
    sb = get_admin_client()

    try:
        bookings = (
            sb.table("services")
            .select("*, amc_plans(*), technicians(*)")
            .eq("customer_id", user["id"])
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        repair_jobs = (
            sb.table("repair_jobs")
            .select("*, technicians(*)")
            .eq("customer_id", user["id"])
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        orders = (
            sb.table("orders")
            .select("*, chimney_products(brand, model)")
            .eq("customer_id", user["id"])
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
    except Exception as e:
        logger.error(f"Error loading dashboard for user {user.get('id')}: {e}")
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
    except Exception as e:
        logger.error(f"Error fetching AMC plans for services index: {e}")
        amc_plans = []

    return render_template("services/index.html", amc_plans=amc_plans)


@services_bp.route("/services/amc")
def amc_plans():
    """Detailed AMC plan comparison page."""
    try:
        sb = get_supabase_client()
        plans = sb.table("amc_plans").select("*").eq("active", True).order("duration_months").execute()
        amc_plans = plans.data if plans.data else []
    except Exception as e:
        logger.error(f"Error fetching AMC plans: {e}")
        amc_plans = []

    return render_template("services/amc.html", amc_plans=amc_plans)


@services_bp.route("/services/book", methods=["GET", "POST"])
@login_required
def book_service():
    """Book an AMC plan or one-time cleaning service with strict input schema validation."""
    if request.method == "GET":
        try:
            sb = get_supabase_client()
            plans = sb.table("amc_plans").select("*").eq("active", True).order("duration_months").execute()
            amc_plans = plans.data if plans.data else []
        except Exception as e:
            logger.error(f"Error fetching plans for book page: {e}")
            amc_plans = []

        service_type = request.args.get("type", "one_time")
        plan_id = request.args.get("plan_id", "")
        return render_template("services/book.html", amc_plans=amc_plans, service_type=service_type, plan_id=plan_id)

    # ── POST: process booking ──
    user = session["user"]
    service_type = sanitize_string(request.form.get("service_type", "one_time"), max_length=20)
    plan_id = request.form.get("plan_id") or None
    notes = sanitize_string(request.form.get("notes", ""), max_length=1000)

    # Validate service type enum
    is_valid_type, type_err = validate_enum(service_type, ["one_time", "amc"], "Service Type")
    if not is_valid_type:
        flash(type_err, "error")
        return redirect(url_for("services.book_service"))

    # Fixed server-side labour charges (cannot be manipulated by client)
    if service_type == "amc":
        labour_charge = 0.0
        if not plan_id:
            flash("Please select an AMC subscription plan.", "error")
            return redirect(url_for("services.book_service", type="amc"))
    else:
        labour_charge = 299.0

    order_id = generate_booking_id()
    service_id = generate_service_id()

    try:
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
            # Trigger WhatsApp confirmation message
            whatsapp_number = user.get("phone", "")
            if whatsapp_number:
                send_whatsapp_message(
                    whatsapp_number,
                    f"ChimneyCare Booking Confirmed! Order ID: {order_id} | Service ID: {service_id}. "
                    "We will contact you within 24 hours to schedule your service visit."
                )

            flash(f"Booking confirmed! Order ID: {order_id} | Service ID: {service_id}", "success")
            return redirect(url_for("services.my_bookings"))
        else:
            flash("Unable to create booking at this time. Please try again.", "error")
            return redirect(url_for("services.book_service"))

    except Exception as e:
        logger.error(f"Error creating booking for user {user.get('id')}: {e}")
        flash("An error occurred while creating your booking. Please try again.", "error")
        return redirect(url_for("services.book_service"))


@services_bp.route("/services/my-bookings")
@login_required
def my_bookings():
    """View all customer bookings."""
    user = session["user"]
    sb = get_admin_client()

    try:
        result = (
            sb.table("services")
            .select("*, amc_plans(*), technicians(*)")
            .eq("customer_id", user["id"])
            .order("created_at", desc=True)
            .execute()
        )
        bookings = result.data if result.data else []
    except Exception as e:
        logger.error(f"Error fetching bookings for user {user.get('id')}: {e}")
        bookings = []

    return render_template("services/my_bookings.html", bookings=bookings)


# ──────────────────────────────────────────────
#  Informational & Contact Routes
# ──────────────────────────────────────────────

@services_bp.route("/about")
def about():
    """About ChimneyCare & Parent Company Sobhraj Enterprise Pvt Ltd."""
    return render_template("pages/about.html")


@services_bp.route("/contact", methods=["GET", "POST"])
def contact():
    """Contact page with direct WhatsApp, email and Web3Forms inquiry form."""
    if request.args.get("status") == "success":
        flash("Thank you for reaching out! Your message has been sent successfully. Our team will contact you shortly.", "success")
        return redirect(url_for("services.contact"))

    web3forms_key = os.environ.get("WEB3FORMS_ACCESS_KEY") or "07fac542-1cfc-4794-bcd7-1a9a11ae9b2a"
    return render_template("pages/contact.html", web3forms_key=web3forms_key)


@services_bp.route("/service-areas")
def service_areas():
    """List of coverage cities, pincodes and operational zones."""
    return render_template("pages/service_areas.html")


@services_bp.route("/faq")
def faq():
    """Frequently asked questions."""
    return render_template("pages/faq.html")


@services_bp.route("/terms")
def terms():
    """Terms of Service."""
    return render_template("pages/terms.html")


@services_bp.route("/privacy")
def privacy():
    """Privacy Policy."""
    return render_template("pages/privacy.html")
