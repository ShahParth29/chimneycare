-- ============================================================
--  ChimneyCare — Full Database Schema for Supabase (Idempotent)
--  Run this in the Supabase SQL Editor to create or update all
--  tables, indexes, Row Level Security policies, and Realtime.
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ──────────────────────────────────────────────
--  1. PROFILES
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS profiles (
    id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role            TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer', 'admin')),
    name            TEXT NOT NULL,
    phone           TEXT,
    whatsapp_number TEXT,
    email           TEXT,
    address         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "profiles_select" ON profiles;
DROP POLICY IF EXISTS "profiles_insert" ON profiles;
DROP POLICY IF EXISTS "profiles_update" ON profiles;

CREATE POLICY "profiles_select" ON profiles FOR SELECT USING (
    id = auth.uid()
    OR EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role = 'admin')
);
CREATE POLICY "profiles_insert" ON profiles FOR INSERT WITH CHECK (id = auth.uid());
CREATE POLICY "profiles_update" ON profiles FOR UPDATE USING (id = auth.uid());


-- ──────────────────────────────────────────────
--  2. TECHNICIANS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS technicians (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL,
    phone           TEXT,
    email           TEXT,
    photo_url       TEXT,
    reveal_status   BOOLEAN DEFAULT FALSE,
    specialization  TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE technicians ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "technicians_admin_full" ON technicians;
DROP POLICY IF EXISTS "technicians_customer_revealed" ON technicians;

-- Admin full access
CREATE POLICY "technicians_admin_full" ON technicians FOR ALL USING (
    EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
);

-- Customer can only see full details when reveal_status = TRUE
CREATE POLICY "technicians_customer_revealed" ON technicians FOR SELECT USING (
    reveal_status = TRUE
);


-- ──────────────────────────────────────────────
--  3. AMC PLANS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS amc_plans (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tier             TEXT NOT NULL,
    duration_months  INTEGER NOT NULL CHECK (duration_months IN (3, 6, 12)),
    visits_included  INTEGER NOT NULL,
    price            NUMERIC(10, 2) NOT NULL,
    description      TEXT,
    active           BOOLEAN DEFAULT TRUE,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE amc_plans ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "amc_plans_read" ON amc_plans;
DROP POLICY IF EXISTS "amc_plans_admin" ON amc_plans;

CREATE POLICY "amc_plans_read" ON amc_plans FOR SELECT USING (TRUE);
CREATE POLICY "amc_plans_admin" ON amc_plans FOR ALL USING (
    EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
);


-- ──────────────────────────────────────────────
--  4. SERVICES (bookings)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS services (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id     UUID NOT NULL REFERENCES profiles(id),
    type            TEXT NOT NULL CHECK (type IN ('amc', 'one_time', 'cleaning')),
    plan_id         UUID REFERENCES amc_plans(id),
    status          TEXT NOT NULL DEFAULT 'confirmed'
                        CHECK (status IN ('pending', 'confirmed', 'in_progress', 'completed', 'cancelled')),
    labour_charge   NUMERIC(10, 2) DEFAULT 0,
    order_id        TEXT NOT NULL,
    service_id      TEXT NOT NULL,
    technician_id   UUID REFERENCES technicians(id),
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE services ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "services_customer" ON services;
DROP POLICY IF EXISTS "services_insert" ON services;
DROP POLICY IF EXISTS "services_admin_update" ON services;

CREATE POLICY "services_customer" ON services FOR SELECT USING (
    customer_id = auth.uid()
    OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
);
CREATE POLICY "services_insert" ON services FOR INSERT WITH CHECK (customer_id = auth.uid());
CREATE POLICY "services_admin_update" ON services FOR UPDATE USING (
    EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
);


-- ──────────────────────────────────────────────
--  5. REPAIR PARTS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS repair_parts (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL,
    price       NUMERIC(10, 2) NOT NULL,
    source      TEXT,
    description TEXT,
    category    TEXT,
    in_stock    BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE repair_parts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "repair_parts_read" ON repair_parts;
DROP POLICY IF EXISTS "repair_parts_admin" ON repair_parts;

CREATE POLICY "repair_parts_read" ON repair_parts FOR SELECT USING (TRUE);
CREATE POLICY "repair_parts_admin" ON repair_parts FOR ALL USING (
    EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
);


-- ──────────────────────────────────────────────
--  6. REPAIR JOBS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS repair_jobs (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_id            TEXT NOT NULL,
    customer_id           UUID NOT NULL REFERENCES profiles(id),
    part_ids              JSONB DEFAULT '[]'::jsonb,
    technician_id         UUID REFERENCES technicians(id),
    total_cost            NUMERIC(10, 2) DEFAULT 0,
    labour_charge         NUMERIC(10, 2) DEFAULT 0,
    confirmation_status   TEXT DEFAULT 'pending'
                            CHECK (confirmation_status IN ('pending', 'confirmed', 'in_progress', 'completed', 'cancelled')),
    issue_description     TEXT,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE repair_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "repair_jobs_customer" ON repair_jobs;
DROP POLICY IF EXISTS "repair_jobs_insert" ON repair_jobs;
DROP POLICY IF EXISTS "repair_jobs_admin_update" ON repair_jobs;

CREATE POLICY "repair_jobs_customer" ON repair_jobs FOR SELECT USING (
    customer_id = auth.uid()
    OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
);
CREATE POLICY "repair_jobs_insert" ON repair_jobs FOR INSERT WITH CHECK (customer_id = auth.uid());
CREATE POLICY "repair_jobs_admin_update" ON repair_jobs FOR UPDATE USING (
    EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
);


-- ──────────────────────────────────────────────
--  7. CHIMNEY PRODUCTS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chimney_products (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    brand             TEXT NOT NULL,
    model             TEXT NOT NULL,
    price             NUMERIC(10, 2) NOT NULL,
    type              TEXT,
    size              TEXT,
    suction_capacity  TEXT,
    specs             JSONB DEFAULT '{}'::jsonb,
    image_url         TEXT,
    description       TEXT,
    active            BOOLEAN DEFAULT TRUE,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE chimney_products ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "chimney_products_read" ON chimney_products;
DROP POLICY IF EXISTS "chimney_products_admin" ON chimney_products;

CREATE POLICY "chimney_products_read" ON chimney_products FOR SELECT USING (active = TRUE);
CREATE POLICY "chimney_products_admin" ON chimney_products FOR ALL USING (
    EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
);


-- ──────────────────────────────────────────────
--  8. ORDERS (marketplace purchases)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id     UUID NOT NULL REFERENCES profiles(id),
    product_id      UUID REFERENCES chimney_products(id),
    order_id        TEXT NOT NULL,
    promo_code      TEXT,
    exchange_offer  JSONB DEFAULT NULL,
    total_price     NUMERIC(10, 2) NOT NULL,
    status          TEXT DEFAULT 'placed'
                        CHECK (status IN ('placed', 'processing', 'shipped', 'delivered', 'cancelled')),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "orders_customer" ON orders;
DROP POLICY IF EXISTS "orders_insert" ON orders;
DROP POLICY IF EXISTS "orders_admin_update" ON orders;

CREATE POLICY "orders_customer" ON orders FOR SELECT USING (
    customer_id = auth.uid()
    OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
);
CREATE POLICY "orders_insert" ON orders FOR INSERT WITH CHECK (customer_id = auth.uid());
CREATE POLICY "orders_admin_update" ON orders FOR UPDATE USING (
    EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
);


-- ──────────────────────────────────────────────
--  9. PROMO CODES
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS promo_codes (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code             TEXT NOT NULL UNIQUE,
    discount_type    TEXT NOT NULL CHECK (discount_type IN ('percentage', 'flat')),
    value            NUMERIC(10, 2) NOT NULL,
    active           BOOLEAN DEFAULT TRUE,
    min_order_amount NUMERIC(10, 2) DEFAULT 0,
    max_uses         INTEGER,
    current_uses     INTEGER DEFAULT 0,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE promo_codes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "promo_codes_validate" ON promo_codes;
DROP POLICY IF EXISTS "promo_codes_admin" ON promo_codes;

CREATE POLICY "promo_codes_validate" ON promo_codes FOR SELECT USING (active = TRUE);
CREATE POLICY "promo_codes_admin" ON promo_codes FOR ALL USING (
    EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
);


-- ──────────────────────────────────────────────
--  INDEXES for performance
-- ──────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_services_customer ON services(customer_id);
CREATE INDEX IF NOT EXISTS idx_services_order_id ON services(order_id);
CREATE INDEX IF NOT EXISTS idx_repair_jobs_customer ON repair_jobs(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id);
CREATE INDEX IF NOT EXISTS idx_promo_codes_code ON promo_codes(code);
CREATE INDEX IF NOT EXISTS idx_chimney_products_brand ON chimney_products(brand);
CREATE INDEX IF NOT EXISTS idx_chimney_products_type ON chimney_products(type);


-- ──────────────────────────────────────────────
--  ENABLE REALTIME safely (idempotent)
-- ──────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables 
        WHERE pubname = 'supabase_realtime' AND tablename = 'services'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE services;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables 
        WHERE pubname = 'supabase_realtime' AND tablename = 'repair_jobs'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE repair_jobs;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables 
        WHERE pubname = 'supabase_realtime' AND tablename = 'orders'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE orders;
    END IF;
END $$;
