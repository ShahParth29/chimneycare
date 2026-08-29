"""
app.py — Flask entry point for ChimneyCare.

Initialises CSRF protection, rate limiting, blueprints, error handlers,
and template context processors.
"""

import os
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, session
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ── App Factory ──────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-fallback-change-me-in-production")

# Session config
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload limit

if os.environ.get("FLASK_ENV") == "production":
    app.config["SESSION_COOKIE_SECURE"] = True

# ── CSRF Protection ─────────────────────────────

csrf = CSRFProtect(app)

# ── Rate Limiter ─────────────────────────────────

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per hour"],
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
)

# ── Register Blueprints ─────────────────────────

from blueprints.auth import auth_bp
from blueprints.services import services_bp
from blueprints.repair import repair_bp
from blueprints.marketplace import marketplace_bp
from blueprints.admin import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(services_bp)
app.register_blueprint(repair_bp)
app.register_blueprint(marketplace_bp)
app.register_blueprint(admin_bp)

# ── Rate limits on specific routes ──────────────

limiter.limit("5 per minute")(app.view_functions["auth.login"])
limiter.limit("5 per minute")(app.view_functions["auth.admin_login"])
limiter.limit("10 per minute")(app.view_functions["marketplace.validate_promo"])

# ── Template Context Processor ──────────────────

@app.context_processor
def inject_user():
    """Make current user available in all templates."""
    return {"current_user": session.get("user")}

# ── Error Handlers ──────────────────────────────

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return render_template("errors/error.html",
        error_code=400,
        error_title="Security Error",
        error_message="Your session has expired or the form token is invalid. Please go back and try again.",
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
    return render_template("errors/error.html",
        error_code=403,
        error_title="Access Denied",
        error_message="You don't have permission to access this page.",
    ), 403

@app.errorhandler(429)
def ratelimit_handler(e):
    return render_template("errors/error.html",
        error_code=429,
        error_title="Too Many Requests",
        error_message="You've made too many requests. Please wait a moment and try again.",
    ), 429

@app.errorhandler(500)
def server_error(e):
    return render_template("errors/error.html",
        error_code=500,
        error_title="Server Error",
        error_message="Something went wrong on our end. Please try again later.",
    ), 500

# ── Security Headers Middleware ─────────────────

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
