# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

We take the security and privacy of our software very seriously. If you discover a security vulnerability, please do NOT create a public GitHub issue.

Instead, please send an advisory or contact the project maintainers privately via GitHub Security Advisories.

### Security Best Practices Implemented

- **No Hardcoded Secrets**: All keys, URLs, and secrets are exclusively managed through environment variables (`.env`).
- **Row Level Security (RLS)**: Enforced directly at the PostgreSQL database level on all tables.
- **CSRF Defense**: Automatic CSRF token generation and validation on all state-changing requests via `Flask-WTF`.
- **Brute Force Protection**: Rate limiting enabled on sensitive routes (authentication & promo validation) via `Flask-Limiter`.
- **Zero Raw SQL**: All database operations use parameterized SDK calls via `supabase-py`.
