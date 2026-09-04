"""
security_defense.py — Adaptive Threat Defense & Automated IP Rate Limiter / Auto-Ban System for ChimneyCare.

Defends against:
1. Brute-force & credential stuffing attacks
2. Aggressive scanner tools (e.g. Feroxbuster, Burp Suite, Gobuster, Nikto)
3. Denial of Service (DoS) by early-dropping abusive IPs in before_request middleware
4. Reconnaissance / Honeypot probing (/admin, /.env, /wp-admin, etc.)
"""

import os
import time
import logging
import threading
from collections import defaultdict
from flask import request, render_template, jsonify

logger = logging.getLogger("chimneycare.security")

# ── Configuration Defaults ──────────────────────────────
# Ban after 5 failed authentication attempts within 5 minutes (300s)
MAX_AUTH_FAILURES = int(os.environ.get("SEC_MAX_AUTH_FAILURES", "5"))
AUTH_FAILURE_WINDOW = int(os.environ.get("SEC_AUTH_WINDOW_SECONDS", "300"))  # 5 minutes

# Ban after 5 honeypot / aggressive scan triggers within 5 minutes
MAX_SCAN_STRIKES = int(os.environ.get("SEC_MAX_SCAN_STRIKES", "5"))
SCAN_STRIKE_WINDOW = int(os.environ.get("SEC_SCAN_WINDOW_SECONDS", "300"))  # 5 minutes

# Ban duration: default 15 minutes (900 seconds) or 30 minutes (1800 seconds)
DEFAULT_BAN_DURATION = int(os.environ.get("SEC_BAN_DURATION_SECONDS", "900"))

# Known reconnaissance / probe paths for honeypot traps
HONEYPOT_PATHS = {
    "/admin",
    "/admin/",
    "/wp-admin",
    "/wp-login.php",
    "/administrator",
    "/phpmyadmin",
    "/pma",
    "/.env",
    "/.git",
    "/.git/config",
    "/config.json",
    "/config.yaml",
    "/xmlrpc.php",
    "/actuator",
    "/actuator/health",
    "/api/v1/admin",
    "/cpanel",
}


def get_real_client_ip() -> str:
    """
    Extract the real client IP address safely considering reverse proxies
    (Cloudflare, Render, AWS ALB, Nginx).
    """
    # 1. Cloudflare header
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip and cf_ip.strip():
        return cf_ip.strip()

    # 2. X-Forwarded-For header (take the first non-private client IP)
    x_forwarded = request.headers.get("X-Forwarded-For")
    if x_forwarded:
        ips = [ip.strip() for ip in x_forwarded.split(",") if ip.strip()]
        if ips:
            return ips[0]

    # 3. X-Real-IP header
    x_real = request.headers.get("X-Real-IP")
    if x_real and x_real.strip():
        return x_real.strip()

    # 4. Standard remote address fallback
    return request.remote_addr or "127.0.0.1"


class ThreatDefenseManager:
    """
    Thread-safe in-memory security manager tracking failed logins,
    scanner infractions, and active IP bans.
    """
    def __init__(self):
        self._lock = threading.Lock()
        # ip -> list of timestamps of failed auth attempts
        self._auth_failures = defaultdict(list)
        # ip -> list of timestamps of scanner / honeypot strikes
        self._scanner_strikes = defaultdict(list)
        # ip -> ban_expiry_timestamp
        self._banned_ips = {}
        # Whitelisted IPs (e.g. localhost, monitoring services)
        self._whitelist = set(
            ip.strip() for ip in os.environ.get("SEC_IP_WHITELIST", "127.0.0.1,::1").split(",") if ip.strip()
        )

    def is_whitelisted(self, ip: str) -> bool:
        return ip in self._whitelist

    def is_ip_banned(self, ip: str) -> tuple[bool, int]:
        """
        Check if an IP is currently banned.
        Returns (is_banned, remaining_seconds).
        """
        if self.is_whitelisted(ip):
            return False, 0

        now = time.time()
        with self._lock:
            expiry = self._banned_ips.get(ip)
            if not expiry:
                return False, 0
            if now < expiry:
                return True, int(expiry - now)
            # Ban expired — clean up
            del self._banned_ips[ip]
            return False, 0

    def ban_ip(self, ip: str, duration: int = DEFAULT_BAN_DURATION, reason: str = "security_violations"):
        """Ban an IP address immediately for a specified duration."""
        if self.is_whitelisted(ip):
            return
        now = time.time()
        expiry = now + duration
        with self._lock:
            self._banned_ips[ip] = expiry
        logger.critical(
            f"[AUTO-BAN TRIGGERED] IP {ip} has been BANNED for {duration} seconds ({duration // 60} mins). Reason: {reason}"
        )

    def record_auth_failure(self, ip: str) -> bool:
        """
        Record a failed login / 2FA attempt.
        Returns True if the IP was banned as a result.
        """
        if self.is_whitelisted(ip):
            return False

        now = time.time()
        with self._lock:
            # Prune old timestamps outside sliding window
            cutoff = now - AUTH_FAILURE_WINDOW
            self._auth_failures[ip] = [t for t in self._auth_failures[ip] if t > cutoff]
            self._auth_failures[ip].append(now)

            failures = len(self._auth_failures[ip])
            logger.warning(
                f"[SECURITY] Failed auth attempt from IP {ip} ({failures}/{MAX_AUTH_FAILURES} in {AUTH_FAILURE_WINDOW // 60}m)"
            )

            if failures >= MAX_AUTH_FAILURES:
                self._banned_ips[ip] = now + DEFAULT_BAN_DURATION
                self._auth_failures[ip] = []
                logger.critical(
                    f"[AUTO-BAN] IP {ip} banned for {DEFAULT_BAN_DURATION // 60} minutes due to {failures} failed login attempts."
                )
                return True
        return False

    def record_honeypot_hit(self, ip: str, path: str) -> bool:
        """
        Record a probe on a sensitive honeypot / restricted path (e.g. /admin, /.env).
        Returns True if the IP was banned as a result.
        """
        if self.is_whitelisted(ip):
            return False

        now = time.time()
        with self._lock:
            cutoff = now - SCAN_STRIKE_WINDOW
            self._scanner_strikes[ip] = [t for t in self._scanner_strikes[ip] if t > cutoff]
            self._scanner_strikes[ip].append(now)

            strikes = len(self._scanner_strikes[ip])
            logger.warning(
                f"[HONEYPOT PROBE DETECTED] IP {ip} probed '{path}' ({strikes}/{MAX_SCAN_STRIKES} strikes in {SCAN_STRIKE_WINDOW // 60}m)"
            )

            if strikes >= MAX_SCAN_STRIKES:
                self._banned_ips[ip] = now + DEFAULT_BAN_DURATION
                self._scanner_strikes[ip] = []
                logger.critical(
                    f"[AUTO-BAN] IP {ip} banned for {DEFAULT_BAN_DURATION // 60} minutes due to aggressive scanner probing."
                )
                return True
        return False

    def record_auth_success(self, ip: str):
        """Clear failed auth counter on successful login."""
        with self._lock:
            self._auth_failures.pop(ip, None)

    def unban_ip(self, ip: str):
        """Unban an IP address manually."""
        with self._lock:
            self._banned_ips.pop(ip, None)
            self._auth_failures.pop(ip, None)
            self._scanner_strikes.pop(ip, None)

    def reset_all(self):
        """Reset all tracking and bans (for test suites)."""
        with self._lock:
            self._banned_ips.clear()
            self._auth_failures.clear()
            self._scanner_strikes.clear()


# Global Singleton
defense_manager = ThreatDefenseManager()


def init_security_defense(app):
    """
    Attach defense middleware, honeypot handlers, and security headers to Flask app.
    """

    @app.before_request
    def check_ip_ban_middleware():
        # Exempt static assets and health check endpoint so monitors never get locked out
        path = request.path
        if path == "/health" or path.startswith("/static/"):
            return None

        client_ip = get_real_client_ip()
        is_banned, remaining_sec = defense_manager.is_ip_banned(client_ip)
        if is_banned:
            mins = max(1, remaining_sec // 60)
            logger.warning(
                f"[BLOCKED REQUEST] Blocked banned IP {client_ip} attempting to access {path}. Cooldown remaining: {remaining_sec}s"
            )
            
            if request.is_json or path.startswith("/api/"):
                return jsonify({
                    "error": "Too Many Requests / IP Banned",
                    "message": f"Your IP address has been temporarily blocked due to repeated security policy violations. Please retry after {mins} minute(s).",
                    "cooldown_seconds": remaining_sec,
                }), 429

            return render_template(
                "errors/error.html",
                error_code=429,
                error_title="Access Temporarily Blocked",
                error_message=f"Your IP address has been temporarily restricted due to suspicious activity or too many failed attempts. Access will automatically restore in approximately {mins} minute(s).",
            ), 429

        # Detect Honeypot Probes
        clean_path = path.rstrip("/").lower()
        if clean_path in [p.rstrip("/").lower() for p in HONEYPOT_PATHS] or path.startswith("/admin/") or path.startswith("/.env") or path.startswith("/.git"):
            defense_manager.record_honeypot_hit(client_ip, path)
            # Return generic 404 to avoid leaking existence
            return render_template(
                "errors/error.html",
                error_code=404,
                error_title="Page Not Found",
                error_message="The requested resource could not be found.",
            ), 404

        return None
