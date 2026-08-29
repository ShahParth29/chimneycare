-- ============================================================
--  ChimneyCare — Full Database Schema for Supabase (Production Ready)
--  Run this in the Supabase SQL Editor to create or update all
--  tables, indexes, Row Level Security policies, and Realtime.
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ──────────────────────────────────────────────
--  1. PROFILES
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.profiles (
    id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role            TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer', 'admin')),
    name            TEXT NOT NULL,
    phone           TEXT,
    whatsapp_number TEXT,
    email           TEXT,
    address         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Security Definer helper to prevent infinite RLS recursion
CREATE OR REPLACE FUNCTION public.is_admin() 
RETURNS BOOLEAN 
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM public.profiles 
    WHERE id = auth.uid() AND role = 'admin'
  );
END;
$$;

DROP POLICY IF EXISTS "profiles_select" ON public.profiles;
DROP POLICY IF EXISTS "profiles_insert" ON public.profiles;
DROP POLICY IF EXISTS "profiles_update" ON public.profiles;

CREATE POLICY "profiles_select" ON public.profiles FOR SELECT USING (
    id = auth.uid() OR public.is_admin()
);
CREATE POLICY "profiles_insert" ON public.profiles FOR INSERT WITH CHECK (id = auth.uid());
CREATE POLICY "profiles_update" ON public.profiles FOR UPDATE USING (id = auth.uid() OR public.is_admin());


-- ──────────────────────────────────────────────
--  2. TECHNICIANS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.technicians (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL,
    phone           TEXT,
    email           TEXT,
    photo_url       TEXT,
    reveal_status   BOOLEAN DEFAULT FALSE,
    specialization  TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.technicians ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "technicians_admin_full" ON public.technicians;
DROP POLICY IF EXISTS "technicians_customer_revealed" ON public.technicians;

-- Admin full access
CREATE POLICY "technicians_admin_full" ON public.technicians FOR ALL USING (
    public.is_admin()
);

-- Customer can only see full details when reveal_status = TRUE
CREATE POLICY "technicians_customer_revealed" ON public.technicians FOR SELECT USING (
    reveal_status = TRUE
);


-- ──────────────────────────────────────────────
--  3. AMC PLANS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.amc_plans (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tier             TEXT NOT NULL,
    duration_months  INTEGER NOT NULL CHECK (duration_months IN (3, 6, 12)),
    visits_included  INTEGER NOT NULL,
    price            NUMERIC(10, 2) NOT NULL,
    description      TEXT,
    active           BOOLEAN DEFAULT TRUE,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.amc_plans ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "amc_plans_read" ON public.amc_plans;
DROP POLICY IF EXISTS "amc_plans_admin" ON public.amc_plans;

CREATE POLICY "amc_plans_read" ON public.amc_plans FOR SELECT USING (TRUE);
CREATE POLICY "amc_plans_admin" ON public.amc_plans FOR ALL USING (
    public.is_admin()
);


-- ──────────────────────────────────────────────
--  4. SERVICES (bookings)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.services (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id     UUID NOT NULL REFERENCES public.profiles(id),
    type            TEXT NOT NULL CHECK (type IN ('amc', 'one_time', 'cleaning')),
    plan_id         UUID REFERENCES public.amc_plans(id),
    status          TEXT NOT NULL DEFAULT 'confirmed'
                        CHECK (status IN ('pending', 'confirmed', 'in_progress', 'completed', 'cancelled')),
    labour_charge   NUMERIC(10, 2) DEFAULT 0,
    order_id        TEXT NOT NULL,
    service_id      TEXT NOT NULL,
    technician_id   UUID REFERENCES public.technicians(id),
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.services ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "services_customer" ON public.services;
DROP POLICY IF EXISTS "services_insert" ON public.services;
DROP POLICY IF EXISTS "services_admin_update" ON public.services;

CREATE POLICY "services_customer" ON public.services FOR SELECT USING (
    customer_id = auth.uid() OR public.is_admin()
);
CREATE POLICY "services_insert" ON public.services FOR INSERT WITH CHECK (customer_id = auth.uid());
CREATE POLICY "services_admin_update" ON public.services FOR UPDATE USING (
    public.is_admin()
);


-- ──────────────────────────────────────────────
--  5. REPAIR PARTS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.repair_parts (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL,
    price       NUMERIC(10, 2) NOT NULL,
    source      TEXT,
    description TEXT,
    category    TEXT,
    in_stock    BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.repair_parts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "repair_parts_read" ON public.repair_parts;
DROP POLICY IF EXISTS "repair_parts_admin" ON public.repair_parts;

CREATE POLICY "repair_parts_read" ON public.repair_parts FOR SELECT USING (TRUE);
CREATE POLICY "repair_parts_admin" ON public.repair_parts FOR ALL USING (
    public.is_admin()
);


-- ──────────────────────────────────────────────
--  6. REPAIR JOBS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.repair_jobs (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_id            TEXT NOT NULL,
    customer_id           UUID NOT NULL REFERENCES public.profiles(id),
    part_ids              JSONB DEFAULT '[]'::jsonb,
    technician_id         UUID REFERENCES public.technicians(id),
    total_cost            NUMERIC(10, 2) DEFAULT 0,
    labour_charge         NUMERIC(10, 2) DEFAULT 0,
    confirmation_status   TEXT DEFAULT 'pending'
                            CHECK (confirmation_status IN ('pending', 'confirmed', 'in_progress', 'completed', 'cancelled')),
    issue_description     TEXT,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.repair_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "repair_jobs_customer" ON public.repair_jobs;
DROP POLICY IF EXISTS "repair_jobs_insert" ON public.repair_jobs;
DROP POLICY IF EXISTS "repair_jobs_admin_update" ON public.repair_jobs;

CREATE POLICY "repair_jobs_customer" ON public.repair_jobs FOR SELECT USING (
    customer_id = auth.uid() OR public.is_admin()
);
CREATE POLICY "repair_jobs_insert" ON public.repair_jobs FOR INSERT WITH CHECK (customer_id = auth.uid());
CREATE POLICY "repair_jobs_admin_update" ON public.repair_jobs FOR UPDATE USING (
    public.is_admin()
);


-- ──────────────────────────────────────────────
--  7. CHIMNEY PRODUCTS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.chimney_products (
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

ALTER TABLE public.chimney_products ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "chimney_products_read" ON public.chimney_products;
DROP POLICY IF EXISTS "chimney_products_admin" ON public.chimney_products;

CREATE POLICY "chimney_products_read" ON public.chimney_products FOR SELECT USING (active = TRUE);
CREATE POLICY "chimney_products_admin" ON public.chimney_products FOR ALL USING (
    public.is_admin()
);


-- ──────────────────────────────────────────────
--  8. ORDERS (marketplace purchases)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.orders (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id     UUID NOT NULL REFERENCES public.profiles(id),
    product_id      UUID REFERENCES public.chimney_products(id),
    order_id        TEXT NOT NULL,
    promo_code      TEXT,
    exchange_offer  JSONB DEFAULT NULL,
    total_price     NUMERIC(10, 2) NOT NULL,
    status          TEXT DEFAULT 'placed'
                        CHECK (status IN ('placed', 'processing', 'shipped', 'delivered', 'cancelled')),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "orders_customer" ON public.orders;
DROP POLICY IF EXISTS "orders_insert" ON public.orders;
DROP POLICY IF EXISTS "orders_admin_update" ON public.orders;

CREATE POLICY "orders_customer" ON public.orders FOR SELECT USING (
    customer_id = auth.uid() OR public.is_admin()
);
CREATE POLICY "orders_insert" ON public.orders FOR INSERT WITH CHECK (customer_id = auth.uid());
CREATE POLICY "orders_admin_update" ON public.orders FOR UPDATE USING (
    public.is_admin()
);


-- ──────────────────────────────────────────────
--  9. PROMO CODES
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.promo_codes (
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

ALTER TABLE public.promo_codes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "promo_codes_validate" ON public.promo_codes;
DROP POLICY IF EXISTS "promo_codes_admin" ON public.promo_codes;

CREATE POLICY "promo_codes_validate" ON public.promo_codes FOR SELECT USING (active = TRUE);
CREATE POLICY "promo_codes_admin" ON public.promo_codes FOR ALL USING (
    public.is_admin()
);


-- ──────────────────────────────────────────────
--  INDEXES for performance
-- ──────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_services_customer ON public.services(customer_id);
CREATE INDEX IF NOT EXISTS idx_services_order_id ON public.services(order_id);
CREATE INDEX IF NOT EXISTS idx_repair_jobs_customer ON public.repair_jobs(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON public.orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_id ON public.orders(order_id);
CREATE INDEX IF NOT EXISTS idx_promo_codes_code ON public.promo_codes(code);
CREATE INDEX IF NOT EXISTS idx_chimney_products_brand ON public.chimney_products(brand);
CREATE INDEX IF NOT EXISTS idx_chimney_products_type ON public.chimney_products(type);


-- ──────────────────────────────────────────────
--  ENABLE REALTIME safely (idempotent)
-- ──────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables 
        WHERE pubname = 'supabase_realtime' AND tablename = 'services'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.services;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables 
        WHERE pubname = 'supabase_realtime' AND tablename = 'repair_jobs'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.repair_jobs;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables 
        WHERE pubname = 'supabase_realtime' AND tablename = 'orders'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.orders;
    END IF;
END $$;
