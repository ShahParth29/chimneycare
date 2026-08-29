"""
blueprints/repair.py — Repair service and parts catalogue routes.

Handles parts browsing, repair job booking (with WhatsApp stub),
and technician profile viewing (strictly gated by reveal_status).
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from supabase_client import get_supabase_client, get_admin_client
from utils import (
    login_required, generate_service_id, sanitize_string,
    send_whatsapp_message, validate_text_field
)

logger = logging.getLogger("chimneycare.repair")
repair_bp = Blueprint("repair", __name__)


@repair_bp.route("/repair")
def repair_index():
    """Display repair services overview and parts catalogue."""
    try:
        sb = get_supabase_client()
        parts = sb.table("repair_parts").select("*").eq("in_stock", True).order("name").execute()
        parts_data = parts.data if parts.data else []
    except Exception as e:
        logger.error(f"Error loading repair parts: {e}")
        parts_data = []

    # Group parts by category
    categories = {}
    for part in parts_data:
        cat = part.get("category", "General")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(part)

    return render_template("repair/index.html", parts=parts_data, categories=categories)


@repair_bp.route("/repair/parts")
def parts_catalogue():
    """Full parts catalogue with search and filter."""
    search = sanitize_string(request.args.get("search", ""), max_length=100)
    category = sanitize_string(request.args.get("category", ""), max_length=50)

    try:
        sb = get_supabase_client()
        query = sb.table("repair_parts").select("*").eq("in_stock", True)

        if category:
            query = query.eq("category", category)

        result = query.order("name").execute()
        parts = result.data if result.data else []

        # In-memory search filter
        if search:
            search_lower = search.lower()
            parts = [p for p in parts if search_lower in p.get("name", "").lower()
                     or search_lower in p.get("description", "").lower()]

        # Get unique categories for filter
        all_parts = sb.table("repair_parts").select("category").eq("in_stock", True).execute()
        categories_list = sorted(set(p["category"] for p in (all_parts.data or []) if p.get("category")))

    except Exception as e:
        logger.error(f"Error loading parts catalogue: {e}")
        parts = []
        categories_list = []

    return render_template(
        "repair/index.html",
        parts=parts,
        categories={},
        categories_list=categories_list,
        search=search,
        selected_category=category,
    )


@repair_bp.route("/repair/book", methods=["GET", "POST"])
@login_required
def book_repair():
    """Book a repair job with strict description validation."""
    if request.method == "GET":
        try:
            sb = get_supabase_client()
            parts = sb.table("repair_parts").select("*").eq("in_stock", True).order("name").execute()
            parts_data = parts.data if parts.data else []
        except Exception as e:
            logger.error(f"Error fetching parts for booking page: {e}")
            parts_data = []

        return render_template("repair/book.html", parts=parts_data)

    # ── POST: create repair job ──
    user = session["user"]
    selected_parts = request.form.getlist("parts")
    issue_description = sanitize_string(request.form.get("issue_description", ""), max_length=2000)

    is_valid_desc, desc_err = validate_text_field(issue_description, min_len=5, max_len=2000, field_name="Issue Description")
    if not is_valid_desc:
        flash(desc_err, "error")
        return redirect(url_for("repair.book_repair"))

    service_id = generate_service_id()

    try:
        sb = get_admin_client()

        # Calculate total parts cost server-side
        total_parts_cost = 0.0
        if selected_parts:
            parts_result = sb.table("repair_parts").select("id, price").in_("id", selected_parts).execute()
            if parts_result.data:
                total_parts_cost = sum(float(p["price"]) for p in parts_result.data)

        # Fixed standard diagnostic & visit inspection fee
        labour_charge = 350.0
        total_cost = total_parts_cost + labour_charge

        repair_data = {
            "service_id": service_id,
            "customer_id": user["id"],
            "part_ids": selected_parts,
            "total_cost": total_cost,
            "labour_charge": labour_charge,
            "confirmation_status": "pending",
            "issue_description": issue_description,
        }

        result = sb.table("repair_jobs").insert(repair_data).execute()

        if result.data:
            whatsapp_number = user.get("phone", "")
            if whatsapp_number:
                send_whatsapp_message(
                    whatsapp_number,
                    "Thank you for your ChimneyCare repair request. "
                    "We will contact you within 24 hours for telephonic confirmation."
                )

            flash(
                f"Repair request submitted! Service ID: {service_id}. "
                "Our team will contact you within 24 hours for telephonic confirmation.",
                "success",
            )
            return redirect(url_for("services.dashboard"))
        else:
            flash("Repair request failed. Please try again.", "error")
            return redirect(url_for("repair.book_repair"))

    except Exception as e:
        logger.error(f"Error submitting repair job: {e}")
        flash("An unexpected error occurred while booking your repair. Please try again.", "error")
        return redirect(url_for("repair.book_repair"))


@repair_bp.route("/repair/technician/<tech_id>")
@login_required
def technician_profile(tech_id):
    """
    View technician profile — STRICTLY gated by reveal_status.
    Only accessible if the customer has a confirmed booking with this technician
    AND the admin has revealed the technician's details.
    """
    user = session["user"]
    tech_id = sanitize_string(tech_id, max_length=50)

    try:
        sb = get_admin_client()

        # Check if customer has a confirmed service booking with this technician
        service_check = (
            sb.table("services")
            .select("id, status")
            .eq("customer_id", user["id"])
            .eq("technician_id", tech_id)
            .in_("status", ["confirmed", "in_progress", "completed"])
            .execute()
        )

        # Check repair jobs
        repair_check = (
            sb.table("repair_jobs")
            .select("id, confirmation_status")
            .eq("customer_id", user["id"])
            .eq("technician_id", tech_id)
            .in_("confirmation_status", ["confirmed", "in_progress", "completed"])
            .execute()
        )

        has_access = bool(service_check.data or repair_check.data)

        if not has_access:
            flash("Technician details are only available for confirmed bookings after telephonic verification.", "warning")
            return redirect(url_for("services.dashboard"))

        # Fetch technician record
        tech_result = sb.table("technicians").select("*").eq("id", tech_id).execute()

        if not tech_result.data:
            flash("Technician not found.", "error")
            return redirect(url_for("services.dashboard"))

        technician = tech_result.data[0]

        # Double check reveal status
        if not technician.get("reveal_status"):
            flash("Technician details are pending confirmation by our operations desk.", "info")
            return redirect(url_for("services.dashboard"))

        return render_template("repair/technician_profile.html", technician=technician)

    except Exception as e:
        logger.error(f"Error viewing technician profile {tech_id}: {e}")
        flash("Unable to load technician profile.", "error")
        return redirect(url_for("services.dashboard"))
