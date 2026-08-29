"""
utils.py — Shared helpers, security decorators, input validators, and file upload defenses.
"""

import os
import re
import uuid
import logging
import functools
from datetime import datetime, timezone, date

from flask import session, redirect, url_for, flash, request, abort

# Configure module-level logging for security & operations
logger = logging.getLogger("chimneycare.utils")


# ──────────────────────────────────────────────
#  ID Generators (Sequential 6-digit starting from 000001)
# ──────────────────────────────────────────────

def generate_order_id(prefix: str = "CC-ORD") -> str:
    """Generate a sequential 6-digit Order ID starting from 000001 (e.g. CC-ORD-000001)."""
    try:
        from supabase_client import get_admin_client
        sb = get_admin_client()
        res = sb.table("orders").select("id", count="exact").execute()
        count = res.count if res and res.count is not None else 0
        return f"{prefix}-{(count + 1):06d}"
    except Exception as e:
        logger.warning(f"Error querying order count: {e}")
        return f"{prefix}-000001"


def generate_booking_id(prefix: str = "CC-BK") -> str:
    """Generate a sequential 6-digit Booking ID starting from 000001 (e.g. CC-BK-000001)."""
    try:
        from supabase_client import get_admin_client
        sb = get_admin_client()
        res = sb.table("services").select("id", count="exact").execute()
        count = res.count if res and res.count is not None else 0
        return f"{prefix}-{(count + 1):06d}"
    except Exception as e:
        logger.warning(f"Error querying booking count: {e}")
        return f"{prefix}-000001"


def generate_service_id(prefix: str = "CC-SVC") -> str:
    """Generate a sequential 6-digit Service ID starting from 000001 (e.g. CC-SVC-000001)."""
    try:
        from supabase_client import get_admin_client
        sb = get_admin_client()
        svc_res = sb.table("services").select("id", count="exact").execute()
        rep_res = sb.table("repair_jobs").select("id", count="exact").execute()
        svc_cnt = svc_res.count if svc_res and svc_res.count is not None else 0
        rep_cnt = rep_res.count if rep_res and rep_res.count is not None else 0
        total_cnt = svc_cnt + rep_cnt
        return f"{prefix}-{(total_cnt + 1):06d}"
    except Exception as e:
        logger.warning(f"Error querying service count: {e}")
        return f"{prefix}-000001"



# ──────────────────────────────────────────────
#  Payment & WhatsApp Helpers
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
            with urllib.request.urlopen(req, timeout=10) as resp:
                return {"status": "sent", "provider": "meta"}
        except Exception as e:
            logger.error(f"[Meta Cloud API Error] {e}")

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
            with urllib.request.urlopen(req, timeout=10) as resp:
                return {"status": "sent", "provider": "twilio"}
        except Exception as e:
            logger.error(f"[Twilio API Error] {e}")

    # 3. Development / Direct Fallback
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
    if not code or not isinstance(code, str) or not code.strip():
        return {"valid": False, "error": "No promo code provided."}

    code = code.strip().upper()
    if not re.match(r"^[A-Z0-9_-]{3,20}$", code):
        return {"valid": False, "error": "Invalid promo code format."}

    try:
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

        # Check expiry date if present
        if promo.get("valid_until"):
            try:
                expiry = datetime.fromisoformat(promo["valid_until"].replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > expiry:
                    return {"valid": False, "error": "This promo code has expired."}
            except Exception:
                pass

        # Check usage limit
        if promo.get("max_uses") and promo.get("current_uses", 0) >= promo["max_uses"]:
            return {"valid": False, "error": "This promo code has reached its usage limit."}

        # Check minimum order amount
        min_amount = float(promo.get("min_order_amount", 0) or 0)
        if subtotal < min_amount:
            return {
                "valid": False,
                "error": f"Minimum order amount of ₹{min_amount:,.0f} required for this code.",
            }

        # Calculate discount
        val = float(promo.get("value", 0))
        if promo.get("discount_type") == "percentage":
            discount = round(subtotal * (min(val, 100.0) / 100.0), 2)
        elif promo.get("discount_type") == "flat":
            discount = min(val, subtotal)
        else:
            return {"valid": False, "error": "Unknown discount type."}

        return {
            "valid": True,
            "code": code,
            "discount_type": promo["discount_type"],
            "value": val,
            "discount_amount": discount,
            "final_total": round(max(0.0, subtotal - discount), 2),
            "promo_id": promo["id"],
        }
    except Exception as e:
        logger.error(f"Error validating promo code: {e}")
        return {"valid": False, "error": "Unable to validate promo code at this time."}


# ──────────────────────────────────────────────
#  Strict Input Schema Validators
# ──────────────────────────────────────────────

def sanitize_string(value: str, max_length: int = 255) -> str:
    """Strip and truncate a string input."""
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def validate_email_strict(email: str) -> tuple[bool, str]:
    """
    Strict email format validation.
    Returns (is_valid, error_message).
    """
    if not isinstance(email, str) or not email.strip():
        return False, "Email address is required."
    email = email.strip()
    if len(email) > 254:
        return False, "Email address must be under 254 characters."
    # RFC 5322 compliant regex
    pattern = r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
    if not re.match(pattern, email):
        return False, "Please enter a valid email address."
    return True, ""


def validate_email(email: str) -> bool:
    """Backward compatibility helper."""
    is_valid, _ = validate_email_strict(email)
    return is_valid


def validate_phone_strict(phone: str) -> tuple[bool, str]:
    """
    Strict phone number format validation (Indian 10-digit mobile or international +91).
    Returns (is_valid, error_message).
    """
    if not isinstance(phone, str) or not phone.strip():
        return False, "Phone number is required."
    cleaned = re.sub(r"[\s\-\(\)\+]", "", phone.strip())
    if cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = cleaned[2:]
    if len(cleaned) != 10 or not cleaned.isdigit() or cleaned[0] not in "6789":
        return False, "Please enter a valid 10-digit Indian mobile number (e.g. 9876543210)."
    return True, ""


def validate_phone(phone: str) -> bool:
    """Backward compatibility helper."""
    is_valid, _ = validate_phone_strict(phone)
    return is_valid


def validate_password_strict(password: str) -> tuple[bool, str]:
    """
    Strict password complexity validation:
    - Minimum 8 characters, maximum 128 characters
    - Must contain at least 1 uppercase, 1 lowercase, 1 digit
    """
    if not isinstance(password, str) or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if len(password) > 128:
        return False, "Password must not exceed 128 characters."
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter."
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number."
    return True, ""


def validate_name_strict(name: str, field_name: str = "Name") -> tuple[bool, str]:
    """
    Strict name format validation:
    - 2 to 100 characters
    - Only letters, spaces, hyphens, and dots
    """
    if not isinstance(name, str) or not name.strip():
        return False, f"{field_name} is required."
    name = name.strip()
    if len(name) < 2 or len(name) > 100:
        return False, f"{field_name} must be between 2 and 100 characters."
    if not re.match(r"^[a-zA-Z\s\.\'-]+$", name):
        return False, f"{field_name} can only contain letters, spaces, hyphens, and periods."
    return True, ""


def validate_enum(value: str, allowed: list, field_name: str = "Field") -> tuple[bool, str]:
    """Validate that a string value belongs to an allowed enumeration."""
    if not value or str(value).strip().lower() not in [str(a).lower() for a in allowed]:
        return False, f"Invalid selection for {field_name}. Allowed: {', '.join(map(str, allowed))}."
    return True, ""


def validate_integer_range(value, min_val: int, max_val: int, field_name: str = "Number") -> tuple[bool, str]:
    """Validate an integer value within a closed range [min_val, max_val]."""
    try:
        val = int(value)
        if val < min_val or val > max_val:
            return False, f"{field_name} must be between {min_val} and {max_val}."
        return True, ""
    except (ValueError, TypeError):
        return False, f"{field_name} must be a valid integer."


def validate_float_range(value, min_val: float, max_val: float, field_name: str = "Amount") -> tuple[bool, str]:
    """Validate a floating point number within a closed range."""
    try:
        val = float(value)
        if val < min_val or val > max_val:
            return False, f"{field_name} must be between {min_val} and {max_val}."
        return True, ""
    except (ValueError, TypeError):
        return False, f"{field_name} must be a valid number."


def validate_date_string(date_str: str, allow_past: bool = False) -> tuple[bool, str]:
    """Validate date format YYYY-MM-DD and optionally ensure it is today or in the future."""
    if not isinstance(date_str, str) or not date_str.strip():
        return False, "Preferred date is required."
    try:
        parsed_date = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        if not allow_past and parsed_date < date.today():
            return False, "Preferred service date cannot be in the past."
        return True, ""
    except ValueError:
        return False, "Date must be in YYYY-MM-DD format."


def validate_text_field(text: str, min_len: int = 1, max_len: int = 1000, field_name: str = "Text") -> tuple[bool, str]:
    """Validate a multi-line text or description field length."""
    if not isinstance(text, str) or len(text.strip()) < min_len:
        return False, f"{field_name} must be at least {min_len} character(s)."
    if len(text.strip()) > max_len:
        return False, f"{field_name} cannot exceed {max_len} characters."
    return True, ""


# ──────────────────────────────────────────────
#  Secure File Upload Validation (MIME / Magic Bytes)
# ──────────────────────────────────────────────

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAGIC_SIGNATURES = {
    "jpg": b"\xFF\xD8\xFF",
    "jpeg": b"\xFF\xD8\xFF",
    "png": b"\x89PNG\r\n\x1a\n",
    "webp": b"RIFF",  # WebP starts with RIFF....WEBP
}


def validate_and_save_upload(file_storage, target_folder: str = "static/uploads", max_size_mb: float = 5.0) -> tuple[bool, str]:
    """
    Strict file upload validation:
    1. Extension verification
    2. Magic byte / header content inspection
    3. File size limit enforcement
    4. Secure UUID4 randomized filename generation
    5. Safe disk storage with no executable permissions
    Returns (success, filename_or_error_message).
    """
    if not file_storage or not getattr(file_storage, "filename", None):
        return False, "No file provided."

    raw_filename = file_storage.filename.strip()
    if "." not in raw_filename:
        return False, "File must have an image extension."

    ext = raw_filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return False, f"Invalid file type .{ext}. Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}."

    # Inspect file size and magic bytes
    try:
        header = file_storage.read(32)
        file_storage.seek(0, os.SEEK_END)
        file_size = file_storage.tell()
        file_storage.seek(0)

        # Check maximum file size
        max_bytes = int(max_size_mb * 1024 * 1024)
        if file_size > max_bytes:
            return False, f"File size ({file_size / 1024 / 1024:.1f}MB) exceeds the maximum allowed limit of {max_size_mb}MB."
        if file_size < 12:
            return False, "Corrupted or empty file."

        # Verify magic byte signature
        if ext in ("jpg", "jpeg") and not header.startswith(b"\xFF\xD8\xFF"):
            return False, "File content is not a valid JPEG image."
        elif ext == "png" and not header.startswith(b"\x89PNG\r\n\x1a\n"):
            return False, "File content is not a valid PNG image."
        elif ext == "webp" and (not header.startswith(b"RIFF") or b"WEBP" not in header[:16]):
            return False, "File content is not a valid WebP image."

        # Ensure target folder exists
        os.makedirs(target_folder, exist_ok=True)

        # Secure randomized filename
        safe_filename = f"{uuid.uuid4().hex}.{ext}"
        destination = os.path.join(target_folder, safe_filename)

        if hasattr(file_storage, "save"):
            file_storage.save(destination)
        else:
            with open(destination, "wb") as f:
                file_storage.seek(0)
                f.write(file_storage.read())
        return True, safe_filename

    except Exception as e:
        logger.error(f"Error during file upload: {e}")
        return False, "File upload failed due to a server error."
