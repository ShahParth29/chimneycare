# ChimneyCare — Kitchen Chimney Service, Repair & Marketplace Platform

ChimneyCare is a full-stack, server-rendered web application built for chimney servicing, annual maintenance contracts (AMC), repair diagnostics, and a chimney marketplace.

## 🛠️ Tech Stack

- **Backend**: Python 3.x with Flask
- **Frontend**: HTML5, Vanilla CSS3, Vanilla JavaScript, Jinja2 templates
- **Database & Auth**: Supabase (PostgreSQL with Row Level Security, Supabase Auth, Supabase Storage, Supabase Realtime)
- **Security**: Flask-WTF (CSRF protection), Flask-Limiter (Rate limiting)

## ✨ Core Features

- **Services Module**:
  - AMC Tier Plans (3-month, 6-month, 12-month)
  - One-time deep chimney cleaning bookings
  - Transparent itemized labour charges
  - Instant booking confirmation via Supabase Realtime
  - Unique human-readable Order ID & Service ID generation
- **Repair Module**:
  - Transparent parts catalogue with human-entered pricing
  - Technician profile protection: contact information remains hidden until telephonic confirmation and admin approval (`reveal_status = true` enforced via database RLS)
  - Automated WhatsApp notification queue stub
- **Chimney Marketplace**:
  - Filter by brand, type, size, and suction capacity
  - Server-side promo code validation with rate limiting
  - Exchange trade-in evaluation
  - Order checkout flow up to "Order Placed" status
- **Admin Portal (`/admin`)**:
  - Centralized operations dashboard
  - Technician management & reveal status toggling
  - AMC plan configuration
  - Repair parts & product catalogue manager
  - Promo code management with usage limits
  - Booking, repair, and order fulfillment status updates

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Supabase Project

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/<your-username>/chimneycare.git
   cd chimneycare
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Supabase Database**:
   - Run the SQL script in `schema.sql` inside the Supabase SQL Editor.
   - Create a public storage bucket named `chimnecare-assets` for technician and product photos.

4. **Configure Environment Variables**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Fill in your Supabase credentials and secret keys:
   ```env
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_ANON_KEY=your-anon-key
   SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
   FLASK_SECRET_KEY=your-flask-secret-key
   ```

5. **Run the Application**:
   ```bash
   python app.py
   ```
   Open `http://localhost:5000` in your browser.

## 🔒 Security & Privacy

- Strict Row Level Security (RLS) on all database tables.
- No plain-text passwords or client-side calculation trusted.
- Zero personal information or secrets committed.
