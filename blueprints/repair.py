"""
blueprints/repair.py — Repair service and parts catalogue routes.

Handles parts browsing, repair job booking (with WhatsApp stub),
and technician profile viewing (gated by reveal_status).
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from supabase_client import get_supabase_client
from utils import (
    login_required, generate_order_id, generate_service_id,
    sanitize_string, send_whatsapp_message,
)

repair_bp = Blueprint("repair", __name__)


@repair_bp.route("/repair")
def repair_index():
    """Display repair services overview and parts catalogue."""
    try:
        sb = get_supabase_client()
        parts = sb.table("repair_parts").select("*").eq("in_stock", True).order("name").execute()
        parts_data = parts.data if parts.data else []
    except Exception:
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
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "")

    try:
        sb = get_supabase_client()
        query = sb.table("repair_parts").select("*").eq("in_stock", True)

        if category:
            query = query.eq("category", category)

        result = query.order("name").execute()
        parts = result.data if result.data else []

        # Client-side search filter (Supabase free tier doesn't have full-text search)
        if search:
            search_lower = search.lower()
            parts = [p for p in parts if search_lower in p.get("name", "").lower()
                     or search_lower in p.get("description", "").lower()]

        # Get unique categories for filter
        all_parts = sb.table("repair_parts").select("category").eq("in_stock", True).execute()
        categories_list = sorted(set(p["category"] for p in (all_parts.data or []) if p.get("category")))

    except Exception:
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
    """Book a repair job."""
    if request.method == "GET":
        try:
            sb = get_supabase_client()
            parts = sb.table("repair_parts").select("*").eq("in_stock", True).order("name").execute()
            parts_data = parts.data if parts.data else []
        except Exception:
            parts_data = []

        return render_template("repair/book.html", parts=parts_data)

    # ── POST: create repair job ──
    user = session["user"]
    selected_parts = request.form.getlist("parts")
    issue_description = sanitize_string(request.form.get("issue_description", ""), max_length=2000)

    if not issue_description:
        flash("Please describe the issue you're experiencing.", "error")
        return redirect(url_for("repair.book_repair"))

    service_id = generate_service_id()

    try:
        sb = get_supabase_client()

        # Calculate total parts cost
        total_parts_cost = 0
        if selected_parts:
            parts_result = sb.table("repair_parts").select("id, price").in_("id", selected_parts).execute()
            if parts_result.data:
                total_parts_cost = sum(float(p["price"]) for p in parts_result.data)

        # Labour charge (entered by admin later, default estimate)
        labour_charge_raw = request.form.get("labour_charge", "500")
        try:
            labour_charge = float(labour_charge_raw)
        except ValueError:
            labour_charge = 500.0

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
            # Send generic WhatsApp message (NEVER mention technician)
            whatsapp_number = user.get("phone", "")
            send_whatsapp_message(
                whatsapp_number,
                "Thank you for your ChimneyCare repair request. "
                "We will contact you within 24 hours for telephonic confirmation."
            )

            flash(
                f"Repair request submitted! Service ID: {service_id}. "
                "We will contact you within 24 hours for telephonic confirmation.",
                "success",
            )
            return redirect(url_for("repair.job_detail", job_id=result.data[0]["id"]))

        flash("Failed to submit repair request. Please try again.", "error")
        return redirect(url_for("repair.book_repair"))

    except Exception as e:
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for("repair.book_repair"))


@repair_bp.route("/repair/job/<job_id>")
@login_required
def job_detail(job_id):
    """View repair job details. Technician info shown only if reveal_status = true."""
    user = session["user"]

    try:
        sb = get_supabase_client()

        job = sb.table("repair_jobs").select("*").eq("id", job_id).execute()
        if not job.data:
            flash("Repair job not found.", "error")
            return redirect(url_for("services.dashboard"))

        job_data = job.data[0]

        # Security: ensure customer can only see their own jobs
        if job_data["customer_id"] != user["id"] and user.get("role") != "admin":
            flash("Access denied.", "error")
            return redirect(url_for("services.dashboard"))

        # Fetch parts details
        parts_data = []
        if job_data.get("part_ids"):
            parts = sb.table("repair_parts").select("*").in_("id", job_data["part_ids"]).execute()
            parts_data = parts.data if parts.data else []

        # Fetch technician (RLS will hide contact info if reveal_status = false)
        technician = None
        if job_data.get("technician_id"):
            tech = sb.table("technicians").select("*").eq("id", job_data["technician_id"]).execute()
            if tech.data:
                technician = tech.data[0]

    except Exception:
        flash("Error loading repair job details.", "error")
        return redirect(url_for("services.dashboard"))

    return render_template(
        "repair/job_detail.html",
        job=job_data,
        parts=parts_data,
        technician=technician,
    )
