"""
blueprints/marketplace.py — Chimney product marketplace routes.

Handles product browsing with filters, promo code validation,
exchange offers, and order placement (ends at "Order Placed").
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from supabase_client import get_supabase_client
from utils import (
    login_required, generate_order_id, sanitize_string,
    validate_promo_code, handle_payment,
)

marketplace_bp = Blueprint("marketplace", __name__)


@marketplace_bp.route("/marketplace")
def marketplace_index():
    """Product catalogue with brand, price, type, size, suction capacity filters."""
    brand = request.args.get("brand", "")
    product_type = request.args.get("type", "")
    size = request.args.get("size", "")
    suction = request.args.get("suction", "")
    sort_by = request.args.get("sort", "price_asc")
    min_price = request.args.get("min_price", "")
    max_price = request.args.get("max_price", "")

    try:
        sb = get_supabase_client()
        query = sb.table("chimney_products").select("*").eq("active", True)

        if brand:
            query = query.eq("brand", brand)
        if product_type:
            query = query.eq("type", product_type)
        if size:
            query = query.eq("size", size)
        if suction:
            query = query.eq("suction_capacity", suction)
        if min_price:
            try:
                query = query.gte("price", float(min_price))
            except ValueError:
                pass
        if max_price:
            try:
                query = query.lte("price", float(max_price))
            except ValueError:
                pass

        # Sorting
        if sort_by == "price_desc":
            query = query.order("price", desc=True)
        elif sort_by == "name":
            query = query.order("model")
        elif sort_by == "brand":
            query = query.order("brand")
        else:
            query = query.order("price")

        result = query.execute()
        products = result.data if result.data else []

        # Get filter options (distinct values)
        all_products = sb.table("chimney_products").select("brand, type, size, suction_capacity").eq("active", True).execute()
        all_data = all_products.data or []

        brands = sorted(set(p["brand"] for p in all_data if p.get("brand")))
        types = sorted(set(p["type"] for p in all_data if p.get("type")))
        sizes = sorted(set(p["size"] for p in all_data if p.get("size")))
        suctions = sorted(set(p["suction_capacity"] for p in all_data if p.get("suction_capacity")))

    except Exception:
        products = []
        brands, types, sizes, suctions = [], [], [], []

    return render_template(
        "marketplace/index.html",
        products=products,
        brands=brands,
        types=types,
        sizes=sizes,
        suctions=suctions,
        filters={
            "brand": brand,
            "type": product_type,
            "size": size,
            "suction": suction,
            "sort": sort_by,
            "min_price": min_price,
            "max_price": max_price,
        },
    )


@marketplace_bp.route("/marketplace/product/<product_id>")
def product_detail(product_id):
    """Single product detail page."""
    try:
        sb = get_supabase_client()
        result = sb.table("chimney_products").select("*").eq("id", product_id).execute()

        if not result.data:
            flash("Product not found.", "error")
            return redirect(url_for("marketplace.marketplace_index"))

        product = result.data[0]
    except Exception:
        flash("Error loading product.", "error")
        return redirect(url_for("marketplace.marketplace_index"))

    return render_template("marketplace/product_detail.html", product=product)


@marketplace_bp.route("/marketplace/checkout/<product_id>", methods=["GET", "POST"])
@login_required
def checkout(product_id):
    """Checkout page with promo code and exchange offer."""
    try:
        sb = get_supabase_client()
        result = sb.table("chimney_products").select("*").eq("id", product_id).execute()

        if not result.data:
            flash("Product not found.", "error")
            return redirect(url_for("marketplace.marketplace_index"))

        product = result.data[0]
    except Exception:
        flash("Error loading product.", "error")
        return redirect(url_for("marketplace.marketplace_index"))

    if request.method == "GET":
        return render_template("marketplace/checkout.html", product=product)

    # ── POST: place order ──
    user = session["user"]
    promo_code = sanitize_string(request.form.get("promo_code", ""))
    has_exchange = request.form.get("has_exchange") == "on"
    exchange_brand = sanitize_string(request.form.get("exchange_brand", ""))
    exchange_model = sanitize_string(request.form.get("exchange_model", ""))
    exchange_condition = sanitize_string(request.form.get("exchange_condition", ""))

    total_price = float(product["price"])

    # Apply promo code (server-side validation)
    promo_result = None
    if promo_code:
        promo_result = validate_promo_code(sb, promo_code, total_price)
        if promo_result["valid"]:
            total_price = promo_result["final_total"]
        else:
            flash(promo_result["error"], "warning")

    # Build exchange offer data
    exchange_offer = None
    if has_exchange and exchange_brand:
        exchange_offer = {
            "brand": exchange_brand,
            "model": exchange_model,
            "condition": exchange_condition,
            "status": "pending_evaluation",
        }

    order_id = generate_order_id()

    try:
        from supabase_client import get_admin_client
        admin_sb = get_admin_client()
        order_data = {
            "customer_id": user["id"],
            "product_id": product_id,
            "order_id": order_id,
            "promo_code": promo_code if promo_result and promo_result["valid"] else None,
            "exchange_offer": exchange_offer,
            "total_price": total_price,
            "status": "placed",
        }

        result = admin_sb.table("orders").insert(order_data).execute()

        if result.data:
            # Increment promo code usage
            if promo_result and promo_result.get("valid"):
                sb.rpc("increment_promo_usage", {"promo_id": promo_result["promo_id"]}).execute()

            # Stub payment
            handle_payment(order_id, total_price)

            flash(f"Order placed successfully! Order ID: {order_id}", "success")
            return redirect(url_for("marketplace.my_orders"))

        flash("Order placement failed. Please try again.", "error")
        return render_template("marketplace/checkout.html", product=product)

    except Exception as e:
        flash(f"Error placing order: {str(e)}", "error")
        return render_template("marketplace/checkout.html", product=product)


@marketplace_bp.route("/marketplace/validate-promo", methods=["POST"])
@login_required
def validate_promo():
    """AJAX endpoint for promo code validation (rate limited in app.py)."""
    promo_code = sanitize_string(request.json.get("code", "") if request.is_json else "")
    subtotal = 0

    try:
        subtotal = float(request.json.get("subtotal", 0) if request.is_json else 0)
    except (ValueError, TypeError):
        return jsonify({"valid": False, "error": "Invalid subtotal."}), 400

    sb = get_supabase_client()
    result = validate_promo_code(sb, promo_code, subtotal)
    return jsonify(result)


@marketplace_bp.route("/marketplace/my-orders")
@login_required
def my_orders():
    """View customer's order history."""
    user = session["user"]

    try:
        sb = get_supabase_client()
        result = (
            sb.table("orders")
            .select("*, chimney_products(*)")
            .eq("customer_id", user["id"])
            .order("created_at", desc=True)
            .execute()
        )
        orders = result.data if result.data else []
    except Exception:
        orders = []

    return render_template("marketplace/my_orders.html", orders=orders)
