"""
blueprints/two_factor.py — Two-Factor Authentication (2FA) Routes for ChimneyCare.

Handles:
- 2FA Setup with QR Code & single-use backup recovery codes
- 2FA Confirmation and encrypted secret key storage
- 2FA Login Challenge verification with brute-force lockout defense
- 2FA Disabling with security validation
"""

import time
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from supabase_client import get_admin_client, get_supabase_client
from utils import sanitize_string, login_required
from totp_utils import (
    generate_totp_secret,
    encrypt_secret,
    decrypt_secret,
    generate_qr_data_url,
    verify_totp_code,
    generate_backup_codes,
    verify_and_consume_backup_code,
)

logger = logging.getLogger("chimneycare.2fa")
two_factor_bp = Blueprint("two_factor", __name__, url_prefix="/2fa")


@two_factor_bp.route("/setup", methods=["GET"])
@login_required
def setup():
    """
    Step 1: Displays QR code, secret key, and backup recovery codes to configure 2FA.
    """
    user = session.get("user")
    user_id = user["id"]

    sb_admin = get_admin_client()
    try:
        existing = sb_admin.table("user_two_factor").select("is_enabled").eq("user_id", user_id).execute()
        if existing.data and existing.data[0].get("is_enabled"):
            flash("Two-Factor Authentication is already active on your account.", "info")
            if user.get("role") == "admin":
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("services.dashboard"))
    except Exception as e:
        logger.warning(f"Could not check 2FA status for user {user_id}: {e}")

    # Generate fresh secret and backup recovery codes
    secret = generate_totp_secret()
    qr_data_url = generate_qr_data_url(secret, user.get("email", "user"), issuer="ChimneyCare")
    plain_backup_codes, hashed_backup_records = generate_backup_codes(count=8)

    # Store pending setup data in session (valid for 10 minutes)
    session["pending_2fa_setup"] = {
        "user_id": user_id,
        "secret": secret,
        "backup_codes": hashed_backup_records,
        "expires_at": time.time() + 600,
    }

    return render_template(
        "auth/setup_2fa.html",
        qr_data_url=qr_data_url,
        secret_manual=secret,
        backup_codes=plain_backup_codes,
    )


@two_factor_bp.route("/confirm", methods=["POST"])
@login_required
def confirm():
    """
    Step 2: Validates the first 6-digit TOTP code and activates 2FA in the database.
    """
    user = session.get("user")
    pending = session.get("pending_2fa_setup")

    if not pending or pending.get("user_id") != user.get("id"):
        flash("2FA setup session expired or invalid. Please start again.", "error")
        return redirect(url_for("two_factor.setup"))

    if time.time() > pending.get("expires_at", 0):
        session.pop("pending_2fa_setup", None)
        flash("2FA setup session timed out. Please try again.", "error")
        return redirect(url_for("two_factor.setup"))

    code = sanitize_string(request.form.get("code", ""), max_length=6)
    secret = pending["secret"]

    if not verify_totp_code(secret, code):
        flash("Invalid 6-digit authentication code. Ensure your device clock is synchronized and try again.", "error")
        return redirect(url_for("two_factor.setup"))

    # Encrypt secret before storing in DB
    encrypted_secret = encrypt_secret(secret)

    try:
        sb_admin = get_admin_client()
        sb_admin.table("user_two_factor").upsert({
            "user_id": user["id"],
            "secret_encrypted": encrypted_secret,
            "is_enabled": True,
            "backup_codes": pending["backup_codes"],
            "updated_at": "now()",
        }).execute()

        session.pop("pending_2fa_setup", None)
        flash("Two-Factor Authentication is now enabled on your account! Save your backup codes in a safe place.", "success")
        logger.info(f"2FA successfully enabled for user {user['id']}")

        if user.get("role") == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("services.dashboard"))

    except Exception as e:
        logger.error(f"Failed to persist 2FA record for user {user['id']}: {e}")
        flash("Unable to save 2FA settings due to a server error. Please try again.", "error")
        return redirect(url_for("two_factor.setup"))


@two_factor_bp.route("/disable", methods=["POST"])
@login_required
def disable():
    """
    Disables 2FA by verifying the current 6-digit TOTP code.
    """
    user = session.get("user")
    code = sanitize_string(request.form.get("code", ""), max_length=12).strip()

    if not code:
        flash("Please enter your 6-digit 2FA code or a backup code to disable 2FA.", "error")
        if user.get("role") == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("services.dashboard"))

    sb_admin = get_admin_client()
    try:
        res = sb_admin.table("user_two_factor").select("*").eq("user_id", user["id"]).execute()
        if not res.data or not res.data[0].get("is_enabled"):
            flash("2FA is not currently enabled on your account.", "info")
            return redirect(url_for("services.dashboard"))

        record = res.data[0]
        secret = decrypt_secret(record["secret_encrypted"])

        is_valid = False
        if len(code) == 6 and code.isdigit():
            is_valid = verify_totp_code(secret, code)

        # Allow backup code to disable in emergency
        if not is_valid:
            is_valid, _ = verify_and_consume_backup_code(record.get("backup_codes", []), code)

        if not is_valid:
            flash("Invalid security code. 2FA was not disabled.", "error")
            if user.get("role") == "admin":
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("services.dashboard"))

        sb_admin.table("user_two_factor").delete().eq("user_id", user["id"]).execute()
        flash("Two-Factor Authentication has been successfully disabled.", "info")
        logger.info(f"2FA disabled for user {user['id']}")

    except Exception as e:
        logger.error(f"Error disabling 2FA for user {user['id']}: {e}")
        flash("An error occurred while disabling 2FA. Please try again.", "error")

    if user.get("role") == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("services.dashboard"))


@two_factor_bp.route("/challenge", methods=["GET", "POST"])
def challenge():
    """
    Login 2FA Challenge: Verifies 6-digit TOTP code or 8-char backup recovery code.
    Enforces maximum 5 attempts and 5-minute session timeout.
    """
    pending = session.get("pending_2fa_login")
    if not pending:
        flash("No login challenge in progress. Please log in.", "warning")
        return redirect(url_for("auth.login"))

    if time.time() > pending.get("expires_at", 0):
        session.pop("pending_2fa_login", None)
        flash("2FA challenge session expired. Please sign in again.", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "GET":
        return render_template("auth/login_2fa.html", is_admin=(pending.get("role") == "admin"))

    code = sanitize_string(request.form.get("code", ""), max_length=12).strip()
    user_id = pending["user_id"]

    # Rate limiting & attempt tracking
    attempts = pending.get("attempts", 0) + 1
    pending["attempts"] = attempts
    session["pending_2fa_login"] = pending

    if attempts > 5:
        session.pop("pending_2fa_login", None)
        flash("Too many failed 2FA verification attempts. Please log in again.", "error")
        logger.warning(f"2FA brute-force lockout triggered for user {user_id}")
        return redirect(url_for("auth.login"))

    try:
        sb_admin = get_admin_client()
        res = sb_admin.table("user_two_factor").select("*").eq("user_id", user_id).execute()

        if not res.data or not res.data[0].get("is_enabled"):
            # If 2FA record disappeared, allow fallback or prompt login
            session.pop("pending_2fa_login", None)
            flash("2FA configuration error. Please log in again.", "error")
            return redirect(url_for("auth.login"))

        record = res.data[0]
        secret = decrypt_secret(record["secret_encrypted"])

        is_valid = False
        used_backup = False

        # 1. Verify standard 6-digit TOTP code
        if len(code) == 6 and code.isdigit():
            is_valid = verify_totp_code(secret, code)

        # 2. Verify backup recovery code
        if not is_valid:
            backup_list = record.get("backup_codes", [])
            is_valid, updated_list = verify_and_consume_backup_code(backup_list, code)
            if is_valid:
                used_backup = True
                # Persist consumed backup code
                sb_admin.table("user_two_factor").update({
                    "backup_codes": updated_list,
                    "last_verified_at": "now()",
                }).eq("user_id", user_id).execute()

        if not is_valid:
            remaining = 5 - attempts
            flash(f"Invalid verification code. {remaining} attempt(s) remaining.", "error")
            return render_template("auth/login_2fa.html", is_admin=(pending.get("role") == "admin")), 401

        # Successful verification -> Promote to full authenticated session
        session.pop("pending_2fa_login", None)
        session["user"] = {
            "id": user_id,
            "email": pending["email"],
            "name": pending["name"],
            "role": pending["role"],
            "phone": pending.get("phone", ""),
        }
        if pending.get("access_token"):
            session["access_token"] = pending["access_token"]

        if used_backup:
            flash("Logged in using a backup recovery code. Please generate new codes if needed.", "warning")
        else:
            flash(f"Welcome back, {pending['name'] or 'there'}!", "success")

        target_url = pending.get("next_url")
        if not target_url:
            target_url = url_for("admin.dashboard") if pending["role"] == "admin" else url_for("services.dashboard")

        return redirect(target_url)

    except Exception as e:
        logger.error(f"Error during 2FA challenge for user {user_id}: {e}")
        flash("An unexpected error occurred during verification. Please try again.", "error")
        return render_template("auth/login_2fa.html", is_admin=(pending.get("role") == "admin")), 500
