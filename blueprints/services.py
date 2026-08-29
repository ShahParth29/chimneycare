"""
blueprints/services.py — Service booking routes for ChimneyCare.

Handles AMC plans, one-time cleaning, booking submission (with instant
confirmation), and customer booking history.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from supabase_client import get_supabase_client
from utils import (
    login_required, generate_order_id, generate_service_id, sanitize_string,
    send_whatsapp_message,
)

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
    from supabase_client import get_admin_client
    sb = get_admin_client()

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
            .select("*, chimney_products(brand, model)")
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
    # Fixed server-side labour charges (cannot be manipulated by client)
    if service_type == "amc":
        labour_charge = 0.0
    else:
        labour_charge = 299.0

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
    from supabase_client import get_admin_client
    sb = get_admin_client()

    try:
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


# ──────────────────────────────────────────────
#  Supplementary Informational & Legal Routes
# ──────────────────────────────────────────────

@services_bp.route("/about")
def about():
    """About ChimneyCare & Parent Company Sobharaj Enterprise Pvt Ltd."""
    return render_template("pages/about.html")


@services_bp.route("/contact", methods=["GET", "POST"])
def contact():
    """Contact page with direct WhatsApp, email and inquiry form."""
    if request.method == "POST":
        name = sanitize_string(request.form.get("name", ""))
        email = sanitize_string(request.form.get("email", ""))
        phone = sanitize_string(request.form.get("phone", ""))
        message = sanitize_string(request.form.get("message", ""), max_length=1000)

        if not name or not email or not message:
            flash("Please fill in all required fields.", "error")
            return render_template("pages/contact.html"), 400

        # Send WhatsApp alert to support
        send_whatsapp_message(
            "8734002200",
            f"New Inquiry from {name} ({phone or email}): {message}"
        )
        flash("Thank you for reaching out! Our team will contact you shortly.", "success")
        return redirect(url_for("services.contact"))

    return render_template("pages/contact.html")


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

