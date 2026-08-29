"""
blueprints/admin.py — Complete and fully editable Admin portal routes for ChimneyCare.

Full CRUD management of:
- Technicians (Add, Edit, Reveal Toggle, Delete)
- AMC Plans (Add, Edit, Toggle Active, Delete)
- Repair Parts (Add, Edit, Stock Toggle, Delete)
- Chimney Marketplace Products (Add, Edit, Toggle Active, Delete)
- Promo Codes (Add, Edit, Toggle Active, Delete)
- Bookings (Status update, Technician assignment, Labour adjustment)
- Repair Jobs (Status update, Technician assignment, Labour & Parts adjustment)
- Marketplace Orders (Status update: placed/processing/shipped/delivered/cancelled)
"""

import os
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from supabase_client import get_admin_client, get_supabase_client
from utils import (
    admin_required, sanitize_string, send_whatsapp_message, generate_whatsapp_url,
    validate_float_range, validate_integer_range, validate_phone_strict,
    validate_name_strict, validate_and_save_upload,
)

logger = logging.getLogger("chimneycare.admin")
admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin")
@admin_required
def dashboard():
    """Admin dashboard with overview stats."""
    sb = get_admin_client()

    try:
        technicians = sb.table("technicians").select("id", count="exact").execute()
        services_data = sb.table("services").select("id", count="exact").execute()
        repair_data = sb.table("repair_jobs").select("id", count="exact").execute()
        orders_data = sb.table("orders").select("id", count="exact").execute()
        products_data = sb.table("chimney_products").select("id", count="exact").execute()

        recent_bookings = (
            sb.table("services")
            .select("*, profiles(name, email)")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        recent_repairs = (
            sb.table("repair_jobs")
            .select("*, profiles(name, email)")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
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
    except Exception:
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


# ═══════════════════════════════════════════════════
#  Technician Management (Full CRUD)
# ═══════════════════════════════════════════════════

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
                pass

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


@admin_bp.route("/admin/technicians/<tech_id>/edit", methods=["POST"])
@admin_required
def edit_technician(tech_id):
    name = sanitize_string(request.form.get("name", ""))
    phone = sanitize_string(request.form.get("phone", ""))
    email = sanitize_string(request.form.get("email", ""))
    specialization = sanitize_string(request.form.get("specialization", ""))
    reveal_status = request.form.get("reveal_status") == "true"

    if not name:
        flash("Name cannot be empty.", "error")
        return redirect(url_for("admin.technicians"))

    try:
        sb = get_admin_client()
        update_data = {
            "name": name,
            "phone": phone,
            "email": email,
            "specialization": specialization,
            "reveal_status": reveal_status,
        }

        if "photo" in request.files and request.files["photo"].filename:
            photo = request.files["photo"]
            file_ext = os.path.splitext(photo.filename)[1]
            file_path = f"technicians/{name.lower().replace(' ', '_')}{file_ext}"
            sb.storage.from_("chimnecare-assets").upload(
                path=file_path,
                file=photo.read(),
                file_options={"content-type": photo.content_type or "image/jpeg", "upsert": "true"},
            )
            update_data["photo_url"] = sb.storage.from_("chimnecare-assets").get_public_url(file_path)

        sb.table("technicians").update(update_data).eq("id", tech_id).execute()
        flash(f"Technician '{name}' updated successfully.", "success")
    except Exception as e:
        flash(f"Error updating technician: {str(e)}", "error")

    return redirect(url_for("admin.technicians"))


@admin_bp.route("/admin/technicians/<tech_id>/reveal", methods=["POST"])
@admin_required
def toggle_reveal(tech_id):
    try:
        sb = get_admin_client()
        current = sb.table("technicians").select("reveal_status").eq("id", tech_id).execute()
        if current.data:
            new_status = not current.data[0]["reveal_status"]
            sb.table("technicians").update({"reveal_status": new_status}).eq("id", tech_id).execute()
            status_text = "revealed (visible to customers)" if new_status else "hidden"
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


# ═══════════════════════════════════════════════════
#  AMC Plan Management (Full CRUD)
# ═══════════════════════════════════════════════════

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
        flash(f"AMC plan '{tier}' created.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("admin.amc_plans"))


@admin_bp.route("/admin/amc-plans/<plan_id>/edit", methods=["POST"])
@admin_required
def edit_amc_plan(plan_id):
    tier = sanitize_string(request.form.get("tier", ""))
    duration = request.form.get("duration_months", "3")
    visits = request.form.get("visits_included", "1")
    price = request.form.get("price", "0")
    description = sanitize_string(request.form.get("description", ""), max_length=1000)
    active = request.form.get("active") == "true"

    try:
        sb = get_admin_client()
        sb.table("amc_plans").update({
            "tier": tier,
            "duration_months": int(duration),
            "visits_included": int(visits),
            "price": float(price),
            "description": description,
            "active": active,
        }).eq("id", plan_id).execute()
        flash(f"AMC plan '{tier}' updated.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("admin.amc_plans"))


@admin_bp.route("/admin/amc-plans/<plan_id>/toggle", methods=["POST"])
@admin_required
def toggle_amc_plan(plan_id):
    try:
        sb = get_admin_client()
        current = sb.table("amc_plans").select("active").eq("id", plan_id).execute()
        if current.data:
            new_active = not current.data[0]["active"]
            sb.table("amc_plans").update({"active": new_active}).eq("id", plan_id).execute()
            flash(f"Plan status updated to {'Active' if new_active else 'Inactive'}.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for("admin.amc_plans"))


@admin_bp.route("/admin/amc-plans/<plan_id>/delete", methods=["POST"])
@admin_required
def delete_amc_plan(plan_id):
    try:
        sb = get_admin_client()
        sb.table("amc_plans").delete().eq("id", plan_id).execute()
        flash("AMC Plan deleted.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for("admin.amc_plans"))


# ═══════════════════════════════════════════════════
#  Repair Parts Management (Full CRUD)
# ═══════════════════════════════════════════════════

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


@admin_bp.route("/admin/parts/<part_id>/edit", methods=["POST"])
@admin_required
def edit_part(part_id):
    name = sanitize_string(request.form.get("name", ""))
    price = request.form.get("price", "0")
    source = sanitize_string(request.form.get("source", ""))
    description = sanitize_string(request.form.get("description", ""), max_length=500)
    category = sanitize_string(request.form.get("category", ""))
    in_stock = request.form.get("in_stock") == "true"

    try:
        sb = get_admin_client()
        sb.table("repair_parts").update({
            "name": name,
            "price": float(price),
            "source": source,
            "description": description,
            "category": category,
            "in_stock": in_stock,
        }).eq("id", part_id).execute()
        flash(f"Part '{name}' updated.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("admin.parts"))


@admin_bp.route("/admin/parts/<part_id>/toggle-stock", methods=["POST"])
@admin_required
def toggle_part_stock(part_id):
    try:
        sb = get_admin_client()
        current = sb.table("repair_parts").select("in_stock").eq("id", part_id).execute()
        if current.data:
            new_stock = not current.data[0]["in_stock"]
            sb.table("repair_parts").update({"in_stock": new_stock}).eq("id", part_id).execute()
            flash(f"Stock status updated to {'In Stock' if new_stock else 'Out of Stock'}.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for("admin.parts"))


@admin_bp.route("/admin/parts/<part_id>/delete", methods=["POST"])
@admin_required
def delete_part(part_id):
    try:
        sb = get_admin_client()
        sb.table("repair_parts").delete().eq("id", part_id).execute()
        flash("Repair part removed from catalogue.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for("admin.parts"))


# ═══════════════════════════════════════════════════
#  Chimney Products Management (Full CRUD)
# ═══════════════════════════════════════════════════

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

    is_valid_price, price_err = validate_float_range(price, 0.0, 1000000.0, "Price")
    if not is_valid_price:
        flash(price_err, "error")
        return redirect(url_for("admin.products"))

    image_url = ""
    if "image" in request.files and request.files["image"].filename:
        image = request.files["image"]
        valid_upload, filename_or_err = validate_and_save_upload(image, target_folder="static/uploads/products", max_size_mb=5.0)
        if valid_upload:
            image_url = url_for("static", filename=f"uploads/products/{filename_or_err}")
        else:
            flash(f"Image upload warning: {filename_or_err}", "warning")

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
        flash(f"Product '{brand} {model}' added to catalogue.", "success")
    except Exception as e:
        logger.error(f"Error adding product: {e}")
        flash("Unable to add product. Please verify fields and try again.", "error")

    return redirect(url_for("admin.products"))


@admin_bp.route("/admin/products/<product_id>/edit", methods=["POST"])
@admin_required
def edit_product(product_id):
    brand = sanitize_string(request.form.get("brand", ""), max_length=100)
    model = sanitize_string(request.form.get("model", ""), max_length=100)
    price = request.form.get("price", "0")
    product_type = sanitize_string(request.form.get("type", ""), max_length=50)
    size = sanitize_string(request.form.get("size", ""), max_length=20)
    suction = sanitize_string(request.form.get("suction_capacity", ""), max_length=30)
    description = sanitize_string(request.form.get("description", ""), max_length=1000)
    active = request.form.get("active") == "true"

    is_valid_price, price_err = validate_float_range(price, 0.0, 1000000.0, "Price")
    if not is_valid_price:
        flash(price_err, "error")
        return redirect(url_for("admin.products"))

    try:
        sb = get_admin_client()
        update_data = {
            "brand": brand,
            "model": model,
            "price": float(price),
            "type": product_type,
            "size": size,
            "suction_capacity": suction,
            "description": description,
            "active": active,
        }

        if "image" in request.files and request.files["image"].filename:
            image = request.files["image"]
            valid_upload, filename_or_err = validate_and_save_upload(image, target_folder="static/uploads/products", max_size_mb=5.0)
            if valid_upload:
                update_data["image_url"] = url_for("static", filename=f"uploads/products/{filename_or_err}")
            else:
                flash(f"Image update note: {filename_or_err}", "warning")

        sb.table("chimney_products").update(update_data).eq("id", product_id).execute()
        flash(f"Product '{brand} {model}' updated.", "success")
    except Exception as e:
        logger.error(f"Error editing product {product_id}: {e}")
        flash("Unable to update product details.", "error")

    return redirect(url_for("admin.products"))


@admin_bp.route("/admin/products/<product_id>/delete", methods=["POST"])
@admin_required
def delete_product(product_id):
    try:
        sb = get_admin_client()
        sb.table("chimney_products").delete().eq("id", product_id).execute()
        flash("Product removed.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for("admin.products"))


# ═══════════════════════════════════════════════════
#  Promo Codes Management (Full CRUD)
# ═══════════════════════════════════════════════════

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


@admin_bp.route("/admin/promo-codes/<promo_id>/edit", methods=["POST"])
@admin_required
def edit_promo_code(promo_id):
    code = sanitize_string(request.form.get("code", "")).upper()
    discount_type = sanitize_string(request.form.get("discount_type", "percentage"))
    value = request.form.get("value", "0")
    min_order = request.form.get("min_order_amount", "0")
    max_uses = request.form.get("max_uses", "")
    active = request.form.get("active") == "true"

    try:
        sb = get_admin_client()
        sb.table("promo_codes").update({
            "code": code,
            "discount_type": discount_type,
            "value": float(value),
            "min_order_amount": float(min_order) if min_order else 0,
            "max_uses": int(max_uses) if max_uses else None,
            "active": active,
        }).eq("id", promo_id).execute()
        flash(f"Promo code '{code}' updated.", "success")
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
            new_status = not current.data[0]["active"]
            sb.table("promo_codes").update({"active": new_status}).eq("id", promo_id).execute()
            flash(f"Promo code is now {'Active' if new_status else 'Inactive'}.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for("admin.promo_codes"))


@admin_bp.route("/admin/promo-codes/<promo_id>/delete", methods=["POST"])
@admin_required
def delete_promo_code(promo_id):
    try:
        sb = get_admin_client()
        sb.table("promo_codes").delete().eq("id", promo_id).execute()
        flash("Promo code deleted.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    return redirect(url_for("admin.promo_codes"))


# ═══════════════════════════════════════════════════
#  Bookings, Repairs & Orders Management (Full Edit)
# ═══════════════════════════════════════════════════

def format_booking_whatsapp(b):
    """Format professional clean WhatsApp confirmation message for booking."""
    cust_name = (b.get("profiles") or {}).get("name") or "Customer"
    order_id = b.get("order_id") or "—"
    service_id = b.get("service_id") or "—"
    stype = str(b.get("type", "Service")).replace("_", " ").title()
    status = str(b.get("status", "Confirmed")).replace("_", " ").title()
    tech_name = (b.get("technicians") or {}).get("name") or "Assigning shortly"
    labour = int(b.get("labour_charge") or 0)

    return (
        f"*CHIMNEYCARE SERVICE CONFIRMATION*\n"
        f"(A unit of Sobhraj Enterprise Pvt Ltd)\n"
        f"========================================\n"
        f"Dear *{cust_name}*,\n\n"
        f"Your kitchen chimney service request has been confirmed!\n\n"
        f"* Service ID: {service_id}\n"
        f"* Order ID: {order_id}\n"
        f"* Service Type: {stype}\n"
        f"* Current Status: {status}\n"
        f"* Assigned Technician: {tech_name}\n"
        f"* Labour Charge: Rs. {labour}\n\n"
        f"========================================\n"
        f"* Live Tracking: http://localhost:5000/dashboard\n"
        f"* Customer Helpline: +91 87340 02200\n"
        f"* Support Email: chimneycare.in@gmail.com\n\n"
        f"_Thank you for choosing ChimneyCare!_"
    )


def format_repair_whatsapp(r):
    """Format professional clean WhatsApp confirmation message for repair job."""
    cust_name = (r.get("profiles") or {}).get("name") or "Customer"
    service_id = r.get("service_id") or "—"
    status = str(r.get("confirmation_status", "Confirmed")).replace("_", " ").title()
    tech_name = (r.get("technicians") or {}).get("name") or "Diagnostic Specialist"
    labour = int(r.get("labour_charge") or 0)
    total = int(r.get("total_cost") or 0)

    return (
        f"*CHIMNEYCARE REPAIR CONFIRMATION*\n"
        f"(A unit of Sobhraj Enterprise Pvt Ltd)\n"
        f"========================================\n"
        f"Dear *{cust_name}*,\n\n"
        f"Your chimney diagnostic & repair job has been scheduled!\n\n"
        f"* Service ID: {service_id}\n"
        f"* Job Status: {status}\n"
        f"* Assigned Technician: {tech_name}\n"
        f"* Diagnostic Labour Fee: Rs. {labour}\n"
        f"* Total Estimated Cost: Rs. {total}\n\n"
        f"========================================\n"
        f"* Live Tracking: http://localhost:5000/dashboard\n"
        f"* Customer Helpline: +91 87340 02200\n"
        f"* Support Email: chimneycare.in@gmail.com\n\n"
        f"_Thank you for choosing ChimneyCare!_"
    )


@admin_bp.route("/admin/bookings")
@admin_required
def bookings():
    sb = get_admin_client()
    try:
        result = (
            sb.table("services")
            .select("*, profiles(name, email, phone, whatsapp_number), technicians(id, name, phone, reveal_status)")
            .order("created_at", desc=True)
            .execute()
        )
        all_bookings = result.data or []
        techs_res = sb.table("technicians").select("id, name").execute()
        techs = techs_res.data or []

        # Enrich each booking with direct WhatsApp message link
        for b in all_bookings:
            cust_phone = (b.get("profiles") or {}).get("whatsapp_number") or (b.get("profiles") or {}).get("phone") or ""
            msg = format_booking_whatsapp(b)
            b["whatsapp_url"] = generate_whatsapp_url(cust_phone, msg) if cust_phone else ""
            b["whatsapp_phone"] = cust_phone

    except Exception:
        all_bookings = []
        techs = []
    return render_template("admin/bookings.html", bookings=all_bookings, technicians=techs)


@admin_bp.route("/admin/bookings/<booking_id>/send-confirmation", methods=["POST"])
@admin_required
def send_booking_confirmation(booking_id):
    sb = get_admin_client()
    try:
        b_res = sb.table("services").select("*, profiles(name, phone, whatsapp_number), technicians(name)").eq("id", booking_id).execute()
        if b_res.data:
            b = b_res.data[0]
            cust_phone = (b.get("profiles") or {}).get("whatsapp_number") or (b.get("profiles") or {}).get("phone")
            if cust_phone:
                msg = format_booking_whatsapp(b)
                send_whatsapp_message(cust_phone, msg)
                flash(f"Confirmation WhatsApp dispatched to {cust_phone}.", "success")
            else:
                flash("Customer has no phone number on file.", "warning")
    except Exception as e:
        flash(f"Error sending WhatsApp: {str(e)}", "error")

    return redirect(url_for("admin.bookings"))


@admin_bp.route("/admin/bookings/<booking_id>/status", methods=["POST"])
@admin_required
def update_booking_status(booking_id):
    new_status = sanitize_string(request.form.get("status", ""))
    technician_id = request.form.get("technician_id")
    labour_charge = request.form.get("labour_charge")
    notes = sanitize_string(request.form.get("notes", ""))

    try:
        sb = get_admin_client()
        update_data = {}
        if new_status in ("pending", "confirmed", "in_progress", "completed", "cancelled"):
            update_data["status"] = new_status
        if "technician_id" in request.form:
            update_data["technician_id"] = technician_id if technician_id else None
        if labour_charge:
            update_data["labour_charge"] = float(labour_charge)
        if notes:
            update_data["notes"] = notes

        if update_data:
            sb.table("services").update(update_data).eq("id", booking_id).execute()
            flash("Booking updated successfully.", "success")
    except Exception as e:
        flash(f"Error updating booking: {str(e)}", "error")

    return redirect(url_for("admin.bookings"))


@admin_bp.route("/admin/repairs")
@admin_required
def repairs():
    sb = get_admin_client()
    try:
        result = (
            sb.table("repair_jobs")
            .select("*, profiles(name, email, phone, whatsapp_number), technicians(id, name, phone, reveal_status)")
            .order("created_at", desc=True)
            .execute()
        )
        all_repairs = result.data or []
        techs_res = sb.table("technicians").select("id, name").execute()
        techs = techs_res.data or []

        # Enrich each repair with direct WhatsApp message link
        for r in all_repairs:
            cust_phone = (r.get("profiles") or {}).get("whatsapp_number") or (r.get("profiles") or {}).get("phone") or ""
            msg = format_repair_whatsapp(r)
            r["whatsapp_url"] = generate_whatsapp_url(cust_phone, msg) if cust_phone else ""
            r["whatsapp_phone"] = cust_phone

    except Exception:
        all_repairs = []
        techs = []
    return render_template("admin/repairs.html", repairs=all_repairs, technicians=techs)


@admin_bp.route("/admin/repairs/<repair_id>/send-confirmation", methods=["POST"])
@admin_required
def send_repair_confirmation(repair_id):
    sb = get_admin_client()
    try:
        r_res = sb.table("repair_jobs").select("*, profiles(name, phone, whatsapp_number), technicians(name)").eq("id", repair_id).execute()
        if r_res.data:
            r = r_res.data[0]
            cust_phone = (r.get("profiles") or {}).get("whatsapp_number") or (r.get("profiles") or {}).get("phone")
            if cust_phone:
                msg = format_repair_whatsapp(r)
                send_whatsapp_message(cust_phone, msg)
                flash(f"Confirmation WhatsApp dispatched to {cust_phone}.", "success")
            else:
                flash("Customer has no phone number on file.", "warning")
    except Exception as e:
        flash(f"Error sending WhatsApp: {str(e)}", "error")

    return redirect(url_for("admin.repairs"))


@admin_bp.route("/admin/repairs/<repair_id>/update", methods=["POST"])
@admin_required
def update_repair(repair_id):
    status = sanitize_string(request.form.get("status", ""))
    technician_id = request.form.get("technician_id")
    labour_charge = request.form.get("labour_charge")
    total_cost = request.form.get("total_cost")

    try:
        sb = get_admin_client()
        update_data = {}
        if status in ("pending", "confirmed", "in_progress", "completed", "cancelled"):
            update_data["confirmation_status"] = status
        if "technician_id" in request.form:
            update_data["technician_id"] = technician_id if technician_id else None
        if labour_charge:
            update_data["labour_charge"] = float(labour_charge)
        if total_cost:
            update_data["total_cost"] = float(total_cost)

        if update_data:
            sb.table("repair_jobs").update(update_data).eq("id", repair_id).execute()
            flash("Repair job updated successfully.", "success")
    except Exception as e:
        flash(f"Error updating repair job: {str(e)}", "error")

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

    try:
        sb = get_admin_client()
        if new_status in ("placed", "processing", "shipped", "delivered", "cancelled"):
            sb.table("orders").update({"status": new_status}).eq("id", order_id).execute()
            flash(f"Order status updated to '{new_status.title()}'.", "success")
    except Exception as e:
        flash(f"Error updating order: {str(e)}", "error")

    return redirect(url_for("admin.orders"))


@admin_bp.route("/admin/2fa-setup")
@admin_required
def setup_2fa():
    """Admin 2FA QR code & Secret key viewer."""
    import io
    import base64
    import pyotp
    import qrcode

    admin_email = os.environ.get("ADMIN_EMAIL", "admin.chimneycare@gmail.com")
    admin_secret = os.environ.get("ADMIN_2FA_SECRET", "PKNZR4SQICIEAKDHYVINE2ASHJXOZFQE")
    backup_codes = [b.strip() for b in os.environ.get("ADMIN_BACKUP_CODES", "CHMN-9281,CARE-4710,SAFE-8392,FIRE-1934").split(",") if b.strip()]

    totp = pyotp.TOTP(admin_secret)
    provisioning_uri = totp.provisioning_uri(name=admin_email, issuer_name="ChimneyCare Admin")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(provisioning_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_img = base64.b64encode(buffer.getvalue()).decode("utf-8")
    qr_data_url = f"data:image/png;base64,{b64_img}"

    return render_template(
        "admin/setup_2fa.html",
        qr_data_url=qr_data_url,
        secret_manual=admin_secret,
        backup_codes=backup_codes,
    )

