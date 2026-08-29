# Contributing to ChimneyCare

Thank you for your interest in contributing to ChimneyCare!

## Guidelines

1. **Fork the Repository** and create your branch from `main`.
2. **Environment Variables**: Never commit `.env` files or API keys. Always use `.env.example` as reference.
3. **Database Changes**: If you modify the database schema, update `schema.sql` with idempotent statements (`DROP POLICY IF EXISTS`, `CREATE TABLE IF NOT EXISTS`).
4. **Code Quality**: Ensure server-side validation and CSRF protection are maintained for all new routes.
5. **Pull Requests**: Submit clear pull requests with detailed descriptions of changes made.
