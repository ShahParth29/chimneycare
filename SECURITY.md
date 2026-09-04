# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

We take the security and privacy of our software very seriously. If you discover a security vulnerability, please do NOT create a public GitHub issue.

Instead, please send an advisory or contact the project maintainers privately via GitHub Security Advisories or email `chimneycare.in@gmail.com`.

### Security Defenses Implemented

- **Adaptive Threat Defense & Auto-Ban System**: Middleware tracks failed authentication attempts and scanner activity across client IPs. When an IP incurs 5 failed attempts or aggressive honeypot probes within 5 minutes, the IP is automatically banned for 15–30 minutes, preventing scanner DoS and brute-force attacks.
- **Admin Endpoint Camouflage**: The management portal is relocated to `/shobhrajmanager`, while standard probe paths (`/admin`, `/wp-admin`, `/.env`) act as honeypots returning 404 and recording attacker strikes.
- **Admin Form Hardening**: Username/email and password placeholders have been removed to eliminate internal credential exposure.
- **No Hardcoded Secrets**: All keys, URLs, and secrets are exclusively managed through environment variables (`.env`).
- **Row Level Security (RLS)**: Enforced directly at the PostgreSQL database level on all tables.
- **CSRF Defense**: Automatic CSRF token generation and validation on all state-changing requests via `Flask-WTF`.
- **Brute Force Protection**: Dual-keyed rate limiting enabled on authentication and sensitive endpoints via `Flask-Limiter`.
- **Zero Raw SQL**: All database operations use parameterized SDK calls via `supabase-py`.
- **OWASP Compliant Headers**: Enforces `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy`.
