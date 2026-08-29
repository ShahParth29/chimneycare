"""
app.py — Flask entry point for ChimneyCare.

Configures CSRF protection, tiered configurable rate limiting,
security headers, error handling, and template context processors.
"""

import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Configure server-side logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("chimneycare.app")

from flask import Flask, render_template, session, request, jsonify
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ── App Factory ──────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32).hex()

# Session & Upload Security Config
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload limit

if os.environ.get("FLASK_ENV") == "production":
    app.config["SESSION_COOKIE_SECURE"] = True

# ── CSRF Protection ─────────────────────────────

csrf = CSRFProtect(app)

# ── Configurable Rate Limiter ────────────────────

def get_auth_rate_limit_key():
    """Dual-keying function: combines client IP + form identifier (email/phone)."""
    ip = get_remote_address()
    form_id = request.form.get("email") or request.form.get("phone") or ""
    return f"{ip}:{form_id.strip().lower()}" if form_id else ip

RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200 per hour")
RATELIMIT_AUTH = os.environ.get("RATELIMIT_AUTH", "5 per minute, 20 per hour")
RATELIMIT_PUBLIC = os.environ.get("RATELIMIT_PUBLIC", "60 per minute, 1000 per hour")
RATELIMIT_AUTHENTICATED = os.environ.get("RATELIMIT_AUTHENTICATED", "120 per minute, 3000 per hour")
RATELIMIT_API = os.environ.get("RATELIMIT_API", "30 per minute")

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[RATELIMIT_DEFAULT],
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
)

# ── Register Blueprints ─────────────────────────

from blueprints.auth import auth_bp
from blueprints.services import services_bp
from blueprints.repair import repair_bp
from blueprints.marketplace import marketplace_bp
from blueprints.admin import admin_bp
from blueprints.two_factor import two_factor_bp

app.register_blueprint(auth_bp)
app.register_blueprint(services_bp)
app.register_blueprint(repair_bp)
app.register_blueprint(marketplace_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(two_factor_bp)

# ── Apply Configurable Rate Limits ──────────────

# Stricter Dual-Key Auth Limits (Brute-Force & Credential Stuffing Defense)
limiter.limit(RATELIMIT_AUTH, key_func=get_auth_rate_limit_key)(app.view_functions["auth.login"])
limiter.limit(RATELIMIT_AUTH, key_func=get_auth_rate_limit_key)(app.view_functions["auth.register"])
limiter.limit(RATELIMIT_AUTH, key_func=get_auth_rate_limit_key)(app.view_functions["auth.forgot_password"])
limiter.limit(RATELIMIT_AUTH, key_func=get_auth_rate_limit_key)(app.view_functions["auth.admin_login"])
limiter.limit(RATELIMIT_AUTH, key_func=get_auth_rate_limit_key)(app.view_functions["two_factor.challenge"])
limiter.limit(RATELIMIT_AUTH)(app.view_functions["two_factor.confirm"])
limiter.limit(RATELIMIT_AUTH)(app.view_functions["two_factor.disable"])

# API & Interactive Endpoint Limits
limiter.limit(RATELIMIT_API)(app.view_functions["marketplace.validate_promo"])


# ── Health Check Endpoint (UptimeRobot / Keep-Alive) ──

@app.route("/health", methods=["GET", "HEAD"])
@limiter.exempt
def health_check():
    """Lightweight health check endpoint for uptime monitoring."""
    return jsonify({
        "success": True,
        "message": "Server is healthy",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }), 200

# ── Template Context Processor ──────────────────

@app.context_processor
def inject_user():
    """Make current user available in all templates."""
    return {"current_user": session.get("user")}

# ── Error Handlers & Information Leakage Prevention ──

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    logger.warning(f"CSRF Error: {e} from IP {get_remote_address()}")
    return render_template("errors/error.html",
        error_code=400,
        error_title="Security Verification Failed",
        error_message="Your security session token has expired or is invalid. Please refresh the page and try again.",
    ), 400

@app.errorhandler(400)
def bad_request(e):
    return render_template("errors/error.html",
        error_code=400,
        error_title="Invalid Request",
        error_message="The request could not be processed due to invalid parameters or formatting.",
    ), 400

@app.errorhandler(404)
def not_found(e):
    return render_template("errors/error.html",
        error_code=404,
        error_title="Page Not Found",
        error_message="The page you're looking for doesn't exist or has been moved.",
    ), 404

@app.errorhandler(403)
def forbidden(e):
    logger.warning(f"403 Forbidden on {request.path} from IP {get_remote_address()}")
    return render_template("errors/error.html",
        error_code=403,
        error_title="Access Denied",
        error_message="You do not have the required permissions to access this resource.",
    ), 403

@app.errorhandler(429)
def ratelimit_handler(e):
    logger.warning(f"429 Rate limit exceeded on {request.path} from IP {get_remote_address()}")
    return render_template("errors/error.html",
        error_code=429,
        error_title="Too Many Requests",
        error_message="Too many requests have been received. Please wait a moment before trying again.",
    ), 429

@app.errorhandler(500)
def server_error(e):
    # Log full traceback server-side for internal debugging
    logger.error(f"Internal server error at {request.path}: {e}", exc_info=True)
    # Return generic error to end-user without internal stack or paths
    return render_template("errors/error.html",
        error_code=500,
        error_title="Service Temporarily Unavailable",
        error_message="An unexpected error occurred while processing your request. Our technical team has been notified.",
    ), 500

# ── Security Headers Middleware (OWASP Standard) ──

@app.after_request
def add_security_headers(response):
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# ── Run ──────────────────────────────────────────

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=5000)
