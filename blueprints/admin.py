"""
blueprints/admin.py — Admin portal routes for ChimneyCare.

Full management of technicians, AMC plans, repair parts,
chimney products, promo codes, bookings, and orders.
"""

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from supabase_client import get_admin_client, get_supabase_client
from utils import admin_required, sanitize_string

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin")
@admin_required
def dashboard():
    """Admin dashboard with overview stats."""
    sb = get_admin_client()

    try:
        # Fetch counts for dashboard cards
        technicians = sb.table("technicians").select("id", count="exact").execute()
        services_data = sb.table("services").select("id", count="exact").execute()
        repair_data = sb.table("repair_jobs").select("id", count="exact").execute()
        orders_data = sb.table("orders").select("id", count="exact").execute()
        products_data = sb.table("chimney_products").select("id", count="exact").execute()

        # Recent bookings
        recent_bookings = (
            sb.table("services")
            .select("*, profiles(name, email)")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        # Recent repair jobs
        recent_repairs = (
            sb.table("repair_jobs")
            .select("*, profiles(name, email)")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        # Recent orders
        recent_orders = (
            sb.table("orders")
            .select("*, profiles(name, email), chimney_products(brand, model)")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )

        stats = {
            "technicians": technicians.count or 0,
            "services": services_data.count or 0,
            "repairs": repair_data.count or 0,
            "orders": orders_data.count or 0,
            "products": products_data.count or 0,
        }
    except Exception as e:
        stats = {"technicians": 0, "services": 0, "repairs": 0, "orders": 0, "products": 0}
        recent_bookings = type("obj", (object,), {"data": []})()
        recent_repairs = type("obj", (object,), {"data": []})()
        recent_orders = type("obj", (object,), {"data": []})()

    return render_template(
        "admin.html",
        stats=stats,
        recent_bookings=recent_bookings.data or [],
        recent_repairs=recent_repairs.data or [],
        recent_orders=recent_orders.data or [],
    )


# ── Technician Management ──────────────────────

@admin_bp.route("/admin/technicians")
@admin_required
def technicians():
    sb = get_admin_client()
    try:
        result = sb.table("technicians").select("*").order("name").execute()
        techs = result.data or []
    except Exception:
        techs = []
    return render_template("admin/technicians.html", technicians=techs)


@admin_bp.route("/admin/technicians/add", methods=["POST"])
@admin_required
def add_technician():
    name = sanitize_string(request.form.get("name", ""))
    phone = sanitize_string(request.form.get("phone", ""))
    email = sanitize_string(request.form.get("email", ""))
    specialization = sanitize_string(request.form.get("specialization", ""))

    if not name:
        flash("Technician name is required.", "error")
        return redirect(url_for("admin.technicians"))

    photo_url = ""
    if "photo" in request.files:
        photo = request.files["photo"]
        if photo.filename:
            try:
                sb = get_admin_client()
                file_ext = os.path.splitext(photo.filename)[1]
                file_path = f"technicians/{name.lower().replace(' ', '_')}{file_ext}"
                sb.storage.from_("chimnecare-assets").upload(
                    path=file_path,
                    file=photo.read(),
                    file_options={"content-type": photo.content_type or "image/jpeg"},
                )
                photo_url = sb.storage.from_("chimnecare-assets").get_public_url(file_path)
            except Exception:
                flash("Photo upload failed, but technician was still added.", "warning")

    try:
        sb = get_admin_client()
        sb.table("technicians").insert({
            "name": name,
            "phone": phone,
            "email": email,
            "photo_url": photo_url,
            "reveal_status": False,
            "specialization": specialization,
        }).execute()
        flash(f"Technician '{name}' added successfully.", "success")
    except Exception as e:
        flash(f"Error adding technician: {str(e)}", "error")

    return redirect(url_for("admin.technicians"))


@admin_bp.route("/admin/technicians/<tech_id>/reveal", methods=["POST"])
@admin_required
def toggle_reveal(tech_id):
    """Toggle technician reveal_status (after telephonic confirmation)."""
    try:
        sb = get_admin_client()
        current = sb.table("technicians").select("reveal_status").eq("id", tech_id).execute()
        if current.data:
            new_status = not current.data[0]["reveal_status"]
            sb.table("technicians").update({"reveal_status": new_status}).eq("id", tech_id).execute()
            status_text = "revealed" if new_status else "hidden"
            flash(f"Technician contact info is now {status_text}.", "success")
    except Exception as e:
        flash(f"Error toggling reveal status: {str(e)}", "error")

    return redirect(url_for("admin.technicians"))


@admin_bp.route("/admin/technicians/<tech_id>/delete", methods=["POST"])
@admin_required
def delete_technician(tech_id):
    try:
        sb = get_admin_client()
        sb.table("technicians").delete().eq("id", tech_id).execute()
        flash("Technician removed.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for("admin.technicians"))


# ── AMC Plan Management ────────────────────────

@admin_bp.route("/admin/amc-plans")
@admin_required
def amc_plans():
    sb = get_admin_client()
    try:
        result = sb.table("amc_plans").select("*").order("duration_months").execute()
        plans = result.data or []
    except Exception:
        plans = []
    return render_template("admin/amc_plans.html", plans=plans)


@admin_bp.route("/admin/amc-plans/add", methods=["POST"])
@admin_required
def add_amc_plan():
    tier = sanitize_string(request.form.get("tier", ""))
    duration = request.form.get("duration_months", "3")
    visits = request.form.get("visits_included", "1")
    price = request.form.get("price", "0")
    description = sanitize_string(request.form.get("description", ""), max_length=1000)

    try:
        sb = get_admin_client()
        sb.table("amc_plans").insert({
            "tier": tier,
            "duration_months": int(duration),
            "visits_included": int(visits),
            "price": float(price),
            "description": description,
            "active": True,
        }).execute()
        flash(f"AMC plan '{tier}' added.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("admin.amc_plans"))


@admin_bp.route("/admin/amc-plans/<plan_id>/delete", methods=["POST"])
@admin_required
def delete_amc_plan(plan_id):
    try:
        sb = get_admin_client()
        sb.table("amc_plans").update({"active": False}).eq("id", plan_id).execute()
        flash("Plan deactivated.", "success")
    except Exception:
        flash("Error deactivating plan.", "error")
    return redirect(url_for("admin.amc_plans"))


# ── Repair Parts Management ────────────────────

@admin_bp.route("/admin/parts")
@admin_required
def parts():
    sb = get_admin_client()
    try:
        result = sb.table("repair_parts").select("*").order("name").execute()
        parts_data = result.data or []
    except Exception:
        parts_data = []
    return render_template("admin/parts.html", parts=parts_data)


@admin_bp.route("/admin/parts/add", methods=["POST"])
@admin_required
def add_part():
    name = sanitize_string(request.form.get("name", ""))
    price = request.form.get("price", "0")
    source = sanitize_string(request.form.get("source", ""))
    description = sanitize_string(request.form.get("description", ""), max_length=500)
    category = sanitize_string(request.form.get("category", ""))

    try:
        sb = get_admin_client()
        sb.table("repair_parts").insert({
            "name": name,
            "price": float(price),
            "source": source,
            "description": description,
            "category": category,
            "in_stock": True,
        }).execute()
        flash(f"Part '{name}' added.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("admin.parts"))


@admin_bp.route("/admin/parts/<part_id>/delete", methods=["POST"])
@admin_required
def delete_part(part_id):
    try:
        sb = get_admin_client()
        sb.table("repair_parts").update({"in_stock": False}).eq("id", part_id).execute()
        flash("Part marked as out of stock.", "success")
    except Exception:
        flash("Error updating part.", "error")
    return redirect(url_for("admin.parts"))


# ── Chimney Product Management ─────────────────

@admin_bp.route("/admin/products")
@admin_required
def products():
    sb = get_admin_client()
    try:
        result = sb.table("chimney_products").select("*").order("brand").execute()
        products_data = result.data or []
    except Exception:
        products_data = []
    return render_template("admin/products.html", products=products_data)


@admin_bp.route("/admin/products/add", methods=["POST"])
@admin_required
def add_product():
    brand = sanitize_string(request.form.get("brand", ""))
    model = sanitize_string(request.form.get("model", ""))
    price = request.form.get("price", "0")
    product_type = sanitize_string(request.form.get("type", ""))
    size = sanitize_string(request.form.get("size", ""))
    suction = sanitize_string(request.form.get("suction_capacity", ""))
    description = sanitize_string(request.form.get("description", ""), max_length=1000)

    if not brand or not model:
        flash("Brand and model are required.", "error")
        return redirect(url_for("admin.products"))

    image_url = ""
    if "image" in request.files:
        image = request.files["image"]
        if image.filename:
            try:
                sb = get_admin_client()
                file_ext = os.path.splitext(image.filename)[1]
                file_path = f"products/{brand}_{model}{file_ext}".lower().replace(" ", "_")
                sb.storage.from_("chimnecare-assets").upload(
                    path=file_path,
                    file=image.read(),
                    file_options={"content-type": image.content_type or "image/jpeg"},
                )
                image_url = sb.storage.from_("chimnecare-assets").get_public_url(file_path)
            except Exception:
                flash("Image upload failed.", "warning")

    try:
        sb = get_admin_client()
        sb.table("chimney_products").insert({
            "brand": brand,
            "model": model,
            "price": float(price),
            "type": product_type,
            "size": size,
            "suction_capacity": suction,
            "description": description,
            "image_url": image_url,
            "active": True,
        }).execute()
        flash(f"Product '{brand} {model}' added.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("admin.products"))


@admin_bp.route("/admin/products/<product_id>/delete", methods=["POST"])
@admin_required
def delete_product(product_id):
    try:
        sb = get_admin_client()
        sb.table("chimney_products").update({"active": False}).eq("id", product_id).execute()
        flash("Product deactivated.", "success")
    except Exception:
        flash("Error deactivating product.", "error")
    return redirect(url_for("admin.products"))


# ── Promo Code Management ──────────────────────

@admin_bp.route("/admin/promo-codes")
@admin_required
def promo_codes():
    sb = get_admin_client()
    try:
        result = sb.table("promo_codes").select("*").order("created_at", desc=True).execute()
        promos = result.data or []
    except Exception:
        promos = []
    return render_template("admin/promo_codes.html", promos=promos)


@admin_bp.route("/admin/promo-codes/add", methods=["POST"])
@admin_required
def add_promo_code():
    code = sanitize_string(request.form.get("code", "")).upper()
    discount_type = sanitize_string(request.form.get("discount_type", "percentage"))
    value = request.form.get("value", "0")
    min_order = request.form.get("min_order_amount", "0")
    max_uses = request.form.get("max_uses", "")

    if not code:
        flash("Promo code is required.", "error")
        return redirect(url_for("admin.promo_codes"))

    try:
        sb = get_admin_client()
        sb.table("promo_codes").insert({
            "code": code,
            "discount_type": discount_type,
            "value": float(value),
            "min_order_amount": float(min_order) if min_order else 0,
            "max_uses": int(max_uses) if max_uses else None,
            "active": True,
        }).execute()
        flash(f"Promo code '{code}' created.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("admin.promo_codes"))


@admin_bp.route("/admin/promo-codes/<promo_id>/toggle", methods=["POST"])
@admin_required
def toggle_promo(promo_id):
    try:
        sb = get_admin_client()
        current = sb.table("promo_codes").select("active").eq("id", promo_id).execute()
        if current.data:
            sb.table("promo_codes").update({"active": not current.data[0]["active"]}).eq("id", promo_id).execute()
            flash("Promo code status toggled.", "success")
    except Exception:
        flash("Error toggling promo code.", "error")
    return redirect(url_for("admin.promo_codes"))


# ── Bookings & Orders Views ───────────────────

@admin_bp.route("/admin/bookings")
@admin_required
def bookings():
    sb = get_admin_client()
    try:
        result = (
            sb.table("services")
            .select("*, profiles(name, email, phone)")
            .order("created_at", desc=True)
            .execute()
        )
        all_bookings = result.data or []
    except Exception:
        all_bookings = []
    return render_template("admin/bookings.html", bookings=all_bookings)


@admin_bp.route("/admin/bookings/<booking_id>/status", methods=["POST"])
@admin_required
def update_booking_status(booking_id):
    new_status = sanitize_string(request.form.get("status", ""))
    technician_id = request.form.get("technician_id") or None

    if new_status not in ("pending", "confirmed", "in_progress", "completed", "cancelled"):
        flash("Invalid status.", "error")
        return redirect(url_for("admin.bookings"))

    try:
        sb = get_admin_client()
        update_data = {"status": new_status}
        if technician_id:
            update_data["technician_id"] = technician_id
        sb.table("services").update(update_data).eq("id", booking_id).execute()
        flash("Booking status updated.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("admin.bookings"))


@admin_bp.route("/admin/repairs")
@admin_required
def repairs():
    sb = get_admin_client()
    try:
        result = (
            sb.table("repair_jobs")
            .select("*, profiles(name, email, phone)")
            .order("created_at", desc=True)
            .execute()
        )
        all_repairs = result.data or []
        technicians_result = sb.table("technicians").select("id, name").execute()
        techs = technicians_result.data or []
    except Exception:
        all_repairs = []
        techs = []
    return render_template("admin/repairs.html", repairs=all_repairs, technicians=techs)


@admin_bp.route("/admin/repairs/<repair_id>/update", methods=["POST"])
@admin_required
def update_repair(repair_id):
    status = sanitize_string(request.form.get("status", ""))
    technician_id = request.form.get("technician_id") or None
    labour_charge = request.form.get("labour_charge", "")

    try:
        sb = get_admin_client()
        update_data = {}
        if status:
            update_data["confirmation_status"] = status
        if technician_id:
            update_data["technician_id"] = technician_id
        if labour_charge:
            update_data["labour_charge"] = float(labour_charge)
        if update_data:
            sb.table("repair_jobs").update(update_data).eq("id", repair_id).execute()
            flash("Repair job updated.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("admin.repairs"))


@admin_bp.route("/admin/orders")
@admin_required
def orders():
    sb = get_admin_client()
    try:
        result = (
            sb.table("orders")
            .select("*, profiles(name, email, phone), chimney_products(brand, model)")
            .order("created_at", desc=True)
            .execute()
        )
        all_orders = result.data or []
    except Exception:
        all_orders = []
    return render_template("admin/orders.html", orders=all_orders)


@admin_bp.route("/admin/orders/<order_id>/status", methods=["POST"])
@admin_required
def update_order_status(order_id):
    new_status = sanitize_string(request.form.get("status", ""))
    if new_status not in ("placed", "processing", "shipped", "delivered", "cancelled"):
        flash("Invalid status.", "error")
        return redirect(url_for("admin.orders"))

    try:
        sb = get_admin_client()
        sb.table("orders").update({"status": new_status}).eq("id", order_id).execute()
        flash("Order status updated.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("admin.orders"))
