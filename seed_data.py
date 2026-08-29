"""
seed_data.py — Populates default AMC plans, repair parts, chimney products,
and promo codes into the live Supabase database.
"""

from supabase_client import get_admin_client

def seed():
    sb = get_admin_client()
    print("Seeding initial data into Supabase...")

    # 1. AMC Plans
    plans = [
        {
            "tier": "Basic Care",
            "duration_months": 3,
            "visits_included": 1,
            "price": 899.00,
            "description": "Essential quarterly deep cleaning and grease filter inspection.",
            "active": True
        },
        {
            "tier": "Standard Protection",
            "duration_months": 6,
            "visits_included": 2,
            "price": 1599.00,
            "description": "Bi-annual comprehensive servicing including motor lubrication and duct check.",
            "active": True
        },
        {
            "tier": "Comprehensive Annual",
            "duration_months": 12,
            "visits_included": 4,
            "price": 2799.00,
            "description": "Quarterly deep cleanings, unlimited emergency support, and 10% discount on spare parts.",
            "active": True
        }
    ]
    for p in plans:
        existing = sb.table("amc_plans").select("id").eq("tier", p["tier"]).execute()
        if not existing.data:
            sb.table("amc_plans").insert(p).execute()
            print(f"  + Added AMC Plan: {p['tier']}")

    # 2. Repair Parts
    parts = [
        {"name": "Baffle Filter (Stainless Steel)", "price": 650.00, "category": "Filters", "source": "OEM Direct", "in_stock": True, "description": "Dual-latch curved stainless steel baffle filter."},
        {"name": "Carbon Filter Set (Charcoal)", "price": 450.00, "category": "Filters", "source": "Universal Fit", "in_stock": True, "description": "High-absorption active carbon odor filters."},
        {"name": "1200 m³/hr Copper Motor", "price": 2800.00, "category": "Motors", "source": "OEM Direct", "in_stock": True, "description": "Heavy-duty thermal overload protected sealed motor."},
        {"name": "Touch Sensor Control Panel PCB", "price": 1200.00, "category": "Electronics", "source": "OEM Direct", "in_stock": True, "description": "Capacitive touch 3-speed speed control module with LED display."},
        {"name": "LED Spotlight Assembly (Warm White)", "price": 350.00, "category": "Lighting", "source": "Standard Fit", "in_stock": True, "description": "Energy-efficient 1.5W recessed LED lamp unit."},
        {"name": "Aluminum Flexible Exhaust Duct (6 Inch)", "price": 550.00, "category": "Ducts", "source": "Heavy Gauge", "in_stock": True, "description": "Expandable 10ft flame-retardant aluminum exhaust pipe."}
    ]
    for part in parts:
        existing = sb.table("repair_parts").select("id").eq("name", part["name"]).execute()
        if not existing.data:
            sb.table("repair_parts").insert(part).execute()
            print(f"  + Added Part: {part['name']}")

    # 3. Chimney Marketplace Products
    products = [
        {
            "brand": "Faber",
            "model": "Hood Primus Plus PB BK 60",
            "price": 12490.00,
            "type": "Wall Mounted",
            "size": "60 cm",
            "suction_capacity": "1200 m³/hr",
            "description": "Curved glass kitchen chimney with baffle filters and push-button controls.",
            "specs": {"filter": "Baffle", "controls": "Push Button", "noise_level": "58 dB", "warranty": "5 Years on Motor"},
            "active": True
        },
        {
            "brand": "Elica",
            "model": "FL 600 HAC MS NERO",
            "price": 14990.00,
            "type": "Wall Mounted",
            "size": "60 cm",
            "suction_capacity": "1350 m³/hr",
            "description": "Filterless auto-clean chimney with motion sensor gesture controls.",
            "specs": {"filter": "Filterless Auto-Clean", "controls": "Motion Sensor", "noise_level": "56 dB", "warranty": "5 Years on Motor"},
            "active": True
        },
        {
            "brand": "Hindware",
            "model": "Nevio 90 Auto-Clean",
            "price": 18490.00,
            "type": "Wall Mounted",
            "size": "90 cm",
            "suction_capacity": "1400 m³/hr",
            "description": "Wide 90cm thermal auto-clean chimney with metallic oil collector cup.",
            "specs": {"filter": "Thermal Auto-Clean", "controls": "Touch Panel", "noise_level": "55 dB", "warranty": "7 Years on Motor"},
            "active": True
        },
        {
            "brand": "Glen",
            "model": "Island Hood GL 1090",
            "price": 32990.00,
            "type": "Island Ceiling",
            "size": "90 cm",
            "suction_capacity": "1250 m³/hr",
            "description": "Ceiling-suspended island chimney with surround suction and Italian motor.",
            "specs": {"filter": "Stainless Steel Baffle", "controls": "Touch with Remote", "noise_level": "58 dB", "warranty": "5 Years on Motor"},
            "active": True
        }
    ]
    for prod in products:
        existing = sb.table("chimney_products").select("id").eq("model", prod["model"]).execute()
        if not existing.data:
            sb.table("chimney_products").insert(prod).execute()
            print(f"  + Added Product: {prod['brand']} {prod['model']}")

    # 4. Promo Codes
    promos = [
        {"code": "WELCOME10", "discount_type": "percentage", "value": 10.0, "min_order_amount": 1000.0, "max_uses": 500, "active": True},
        {"code": "FLAT500", "discount_type": "flat", "value": 500.0, "min_order_amount": 5000.0, "max_uses": 200, "active": True},
        {"code": "FESTIVE20", "discount_type": "percentage", "value": 20.0, "min_order_amount": 10000.0, "max_uses": 100, "active": True}
    ]
    for p in promos:
        existing = sb.table("promo_codes").select("id").eq("code", p["code"]).execute()
        if not existing.data:
            sb.table("promo_codes").insert(p).execute()
            print(f"  + Added Promo Code: {p['code']}")

    print("\n✅ Seed complete! All initial catalogue data is in Supabase.")

if __name__ == "__main__":
    seed()
