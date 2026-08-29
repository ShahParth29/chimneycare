"""
utils.py — Shared helpers, decorators, and stub functions for ChimneyCare.
"""

import os
import uuid
import functools
from datetime import datetime, timezone

from flask import session, redirect, url_for, flash, request, abort


# ──────────────────────────────────────────────
#  ID Generators
# ──────────────────────────────────────────────

def generate_order_id() -> str:
    """Generate a human-readable Order ID like CC-ORD-20260829-A3F7."""
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    unique_part = uuid.uuid4().hex[:4].upper()
    return f"CC-ORD-{date_part}-{unique_part}"


def generate_service_id() -> str:
    """Generate a human-readable Service ID like CC-SVC-B2E9."""
    unique_part = uuid.uuid4().hex[:6].upper()
    return f"CC-SVC-{unique_part}"


# ──────────────────────────────────────────────
#  Stub Functions (future integration points)
# ──────────────────────────────────────────────

def handle_payment(order_id: str, amount: float, currency: str = "INR") -> dict:
    """
    STUB — future payment gateway integration.
    Returns a mock success response so the rest of the flow can proceed.
    """
    return {
        "status": "stub_success",
        "order_id": order_id,
        "amount": amount,
        "currency": currency,
        "message": "Payment integration pending — order placed without charge.",
        "transaction_id": f"TXN-STUB-{uuid.uuid4().hex[:8].upper()}",
    }


OFFICIAL_WHATSAPP_NUMBER = "8734002200"
OFFICIAL_CONTACT_EMAIL = "chimneycare.in@gmail.com"
OFFICIAL_ADMIN_EMAIL = "admin.chimneycare@gmail.com"
PARENT_COMPANY = "Sobhraj Enterprise Pvt Ltd"


def generate_whatsapp_url(phone: str = OFFICIAL_WHATSAPP_NUMBER, message: str = "") -> str:
    """Generate a direct WhatsApp click-to-chat URL."""
    import urllib.parse
    cleaned_phone = "".join(filter(str.isdigit, str(phone)))
    if len(cleaned_phone) == 10:
        cleaned_phone = "91" + cleaned_phone
    encoded_message = urllib.parse.quote(str(message).encode("utf-8")) if message else ""
    return f"https://wa.me/{cleaned_phone}?text={encoded_message}" if encoded_message else f"https://wa.me/{cleaned_phone}"


def send_whatsapp_message(phone: str, message: str) -> dict:
    """
    Send a WhatsApp message via Meta Cloud API or Twilio API if keys exist,
    otherwise log in development and prepare click-to-chat payload.
    """
    cleaned_phone = "".join(filter(str.isdigit, str(phone)))
    if len(cleaned_phone) == 10:
        cleaned_phone = "91" + cleaned_phone

    meta_token = os.environ.get("WHATSAPP_API_KEY")
    meta_phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")

    twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
    twilio_from = os.environ.get("TWILIO_WHATSAPP_NUMBER", "+14155238886")

    # 1. Meta WhatsApp Cloud API
    if meta_token and meta_phone_id and meta_token not in ("placeholder", "placeholder-not-active"):
        try:
            import json, urllib.request
            url = f"https://graph.facebook.com/v18.0/{meta_phone_id}/messages"
            payload = json.dumps({
                "messaging_product": "whatsapp",
                "to": cleaned_phone,
                "type": "text",
                "text": {"body": message}
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={
                "Authorization": f"Bearer {meta_token}",
                "Content-Type": "application/json"
            })
            with urllib.request.urlopen(req) as resp:
                return {"status": "sent", "provider": "meta"}
        except Exception as e:
            print(f"[Meta Cloud API Error] {e}")

    # 2. Twilio WhatsApp API
    if twilio_sid and twilio_token and twilio_sid not in ("placeholder", "placeholder-not-active"):
        try:
            import urllib.request, urllib.parse, base64
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            data = urllib.parse.urlencode({
                "From": f"whatsapp:{twilio_from}",
                "To": f"whatsapp:+{cleaned_phone}",
                "Body": message
            }).encode("utf-8")
            auth_header = base64.b64encode(f"{twilio_sid}:{twilio_token}".encode("utf-8")).decode("ascii")
            req = urllib.request.Request(url, data=data, headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded"
            })
            with urllib.request.urlopen(req) as resp:
                return {"status": "sent", "provider": "twilio"}
        except Exception as e:
            print(f"[Twilio API Error] {e}")

    # 3. Development / Local Environment
    return {
        "status": "sent_direct",
        "phone": f"+{cleaned_phone}",
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ──────────────────────────────────────────────
#  Auth Decorators
# ──────────────────────────────────────────────

def login_required(f):
    """Redirect to login if no valid session exists."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Restrict access to users with role == 'admin'."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user = session.get("user")
        if not user:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.admin_login"))
        if user.get("role") != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ──────────────────────────────────────────────
#  Promo Code Validation (server-side only)
# ──────────────────────────────────────────────

def validate_promo_code(supabase_client, code: str, subtotal: float) -> dict:
    """
    Validate a promo code against the database.
    Returns discount info or an error dict.
    ALL discount math happens here — never trust client-side calculations.
    """
    if not code or not code.strip():
        return {"valid": False, "error": "No promo code provided."}

    code = code.strip().upper()

    result = (
        supabase_client.table("promo_codes")
        .select("*")
        .eq("code", code)
        .eq("active", True)
        .execute()
    )

    if not result.data:
        return {"valid": False, "error": "Invalid or expired promo code."}

    promo = result.data[0]

    # Check usage limit
    if promo.get("max_uses") and promo["current_uses"] >= promo["max_uses"]:
        return {"valid": False, "error": "This promo code has reached its usage limit."}

    # Check minimum order amount
    min_amount = promo.get("min_order_amount", 0) or 0
    if subtotal < min_amount:
        return {
            "valid": False,
            "error": f"Minimum order amount of ₹{min_amount:,.0f} required for this code.",
        }

    # Calculate discount
    if promo["discount_type"] == "percentage":
        discount = round(subtotal * (promo["value"] / 100), 2)
    elif promo["discount_type"] == "flat":
        discount = min(promo["value"], subtotal)
    else:
        return {"valid": False, "error": "Unknown discount type."}

    return {
        "valid": True,
        "code": code,
        "discount_type": promo["discount_type"],
        "value": promo["value"],
        "discount_amount": discount,
        "final_total": round(subtotal - discount, 2),
        "promo_id": promo["id"],
    }


# ──────────────────────────────────────────────
#  Input Validation Helpers
# ──────────────────────────────────────────────

def sanitize_string(value: str, max_length: int = 255) -> str:
    """Strip and truncate a string input."""
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def validate_email(email: str) -> bool:
    """Basic email format check."""
    import re
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """Phone number format check (supports standard international and national numbers 7-15 digits)."""
    import re
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    return bool(re.match(r"^\+?[0-9]{7,15}$", cleaned))

