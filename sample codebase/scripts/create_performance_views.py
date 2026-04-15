#!/usr/bin/env python3
"""
Create database views to replace looping logic in API endpoints for better performance.
These views leverage PostgreSQL's parallel processing capabilities.
"""

import os
from datetime import datetime
from supabase import create_client, Client

# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://bwysarrweyooqtjkowzp.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ3eXNhcnJ3ZXlvb3F0amtvd3pwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIzNTIzODEsImV4cCI6MjA2NzkyODM4MX0.cfOrT6MXZ9XHAjYC0K1rri1C4-jGmBbE9q0RQLpR3d8")

def generate_views_sql():
    """Generate SQL for creating performance-optimized views"""
    
    sql = """
-- =====================================================
-- Performance Optimization Views for Waste Reduction API
-- =====================================================

-- 1. Products Enriched View
-- Pre-computes all product metrics to avoid loops in API
CREATE OR REPLACE VIEW products_enriched AS
WITH product_sales AS (
    SELECT 
        product_id,
        COUNT(*) as transaction_count,
        SUM(quantity) as total_quantity_sold,
        SUM(total_price_paid) as total_revenue_generated,
        AVG(discount_percent) as avg_discount_taken,
        SUM(CASE WHEN user_engaged_with_deal = 1 THEN 1 ELSE 0 END)::float / COUNT(*) as deal_engagement_rate,
        MIN(purchase_date) as first_sale_date,
        MAX(purchase_date) as last_sale_date
    FROM transactions
    GROUP BY product_id
),
product_metrics AS (
    SELECT 
        p.*,
        CURRENT_DATE - p.expiry_date as days_past_expiry,
        p.expiry_date - CURRENT_DATE as days_until_expiry,
        ps.transaction_count,
        COALESCE(ps.total_quantity_sold, 0) as total_quantity_sold,
        COALESCE(ps.total_revenue_generated, 0.0) as actual_revenue_generated,
        COALESCE(ps.avg_discount_taken, 0.0) as avg_discount_taken,
        COALESCE(ps.deal_engagement_rate, 0.0) as deal_engagement_rate,
        ps.first_sale_date,
        ps.last_sale_date,
        -- Calculate sales velocity
        CASE 
            WHEN ps.last_sale_date IS NOT NULL AND ps.first_sale_date IS NOT NULL 
            THEN ps.total_quantity_sold::float / NULLIF(ps.last_sale_date - ps.first_sale_date + 1, 0)
            ELSE 0
        END as sales_velocity,
        -- Calculate inventory turnover
        CASE 
            WHEN p.initial_inventory_quantity > 0 
            THEN COALESCE(ps.total_quantity_sold, 0)::float / p.initial_inventory_quantity
            ELSE 0
        END as inventory_turnover_rate
    FROM products p
    LEFT JOIN product_sales ps ON p.product_id = ps.product_id
)
SELECT 
    *,
    -- Dead stock risk calculation
    CASE 
        WHEN days_until_expiry <= 7 AND current_discount_percent < 30 THEN 1
        WHEN days_until_expiry <= 14 AND sales_velocity < 0.5 THEN 1
        WHEN inventory_quantity > 100 AND transaction_count IS NULL THEN 1
        ELSE 0
    END as calculated_dead_stock_risk,
    -- Risk score (0-1 scale)
    CASE
        WHEN days_until_expiry < 0 THEN 1.0
        WHEN days_until_expiry <= 3 THEN 0.9
        WHEN days_until_expiry <= 7 THEN 0.7
        WHEN days_until_expiry <= 14 THEN 0.5
        WHEN sales_velocity < 0.1 AND days_until_expiry <= 30 THEN 0.4
        ELSE LEAST(1.0, GREATEST(0, (30 - days_until_expiry)::float / 30))
    END as risk_score
FROM product_metrics;

-- 2. Weekly Inventory View
-- Pre-calculates weekly inventory metrics for parallel processing
CREATE OR REPLACE VIEW weekly_inventory_metrics AS
WITH RECURSIVE weeks AS (
    -- Generate last 52 weeks
    SELECT 
        0 as week_offset,
        date_trunc('week', CURRENT_DATE)::date as week_start,
        (date_trunc('week', CURRENT_DATE) + interval '6 days')::date as week_end
    UNION ALL
    SELECT 
        week_offset + 1,
        (week_start - interval '7 days')::date,
        (week_end - interval '7 days')::date
    FROM weeks
    WHERE week_offset < 51
),
weekly_data AS (
    SELECT 
        w.week_offset + 1 as week_number,
        w.week_start,
        w.week_end,
        -- Products alive during this week
        COUNT(DISTINCT p.product_id) as alive_products_count,
        -- Quantity metrics
        SUM(p.inventory_quantity) as total_inventory_qty,
        SUM(p.inventory_quantity * p.cost_price) as total_inventory_cost,
        -- Sales during week
        COALESCE(SUM(t.quantity), 0) as sold_inventory_qty,
        COALESCE(SUM(t.quantity * p.cost_price), 0) as sold_inventory_cost,
        COALESCE(SUM(t.total_price_paid), 0) as sold_inventory_revenue
    FROM weeks w
    CROSS JOIN products p
    LEFT JOIN transactions t ON 
        t.product_id = p.product_id AND
        t.purchase_date >= w.week_start AND 
        t.purchase_date <= w.week_end
    WHERE 
        -- Product was alive during this week
        p.packaging_date <= w.week_end AND
        p.expiry_date >= w.week_start
    GROUP BY w.week_offset, w.week_start, w.week_end
)
SELECT 
    week_number,
    week_start::text,
    week_end::text,
    alive_products_count,
    total_inventory_qty,
    total_inventory_cost,
    sold_inventory_qty,
    sold_inventory_cost,
    sold_inventory_revenue,
    -- Utilization rates
    CASE 
        WHEN total_inventory_qty > 0 
        THEN (sold_inventory_qty::float / total_inventory_qty * 100)
        ELSE 0 
    END as inventory_utilization_rate_pct,
    CASE 
        WHEN total_inventory_cost > 0 
        THEN (sold_inventory_cost::float / total_inventory_cost * 100)
        ELSE 0 
    END as cost_utilization_rate_pct
FROM weekly_data
ORDER BY week_number;

-- 3. Weekly Expired Products View
-- Pre-calculates weekly expiration metrics
CREATE OR REPLACE VIEW weekly_expired_metrics AS
WITH RECURSIVE weeks AS (
    -- Generate last 52 weeks
    SELECT 
        0 as week_offset,
        date_trunc('week', CURRENT_DATE)::date as week_start,
        (date_trunc('week', CURRENT_DATE) + interval '6 days')::date as week_end
    UNION ALL
    SELECT 
        week_offset + 1,
        (week_start - interval '7 days')::date,
        (week_end - interval '7 days')::date
    FROM weeks
    WHERE week_offset < 51
),
weekly_expired AS (
    SELECT 
        w.week_offset + 1 as week_number,
        w.week_start,
        w.week_end,
        p.product_id,
        p.category,
        p.inventory_quantity,
        p.price_mrp,
        p.cost_price,
        p.inventory_quantity * p.price_mrp as expired_value_mrp,
        p.inventory_quantity * p.cost_price as expired_value_cost
    FROM weeks w
    INNER JOIN products p ON 
        p.expiry_date >= w.week_start AND 
        p.expiry_date <= w.week_end
),
category_breakdown AS (
    SELECT 
        week_number,
        week_start,
        week_end,
        category,
        COUNT(DISTINCT product_id) as category_count,
        SUM(inventory_quantity) as category_quantity,
        SUM(expired_value_mrp) as category_value_mrp,
        SUM(expired_value_cost) as category_value_cost
    FROM weekly_expired
    GROUP BY week_number, week_start, week_end, category
),
weekly_aggregated AS (
    SELECT 
        we.week_number,
        we.week_start,
        we.week_end,
        COUNT(DISTINCT we.product_id) as expired_count,
        SUM(we.inventory_quantity) as expired_quantity,
        SUM(we.expired_value_mrp) as expired_value_mrp,
        SUM(we.expired_value_cost) as expired_value_cost,
        -- Category breakdown as JSONB
        (
            SELECT jsonb_object_agg(
                cb.category, 
                jsonb_build_object(
                    'count', cb.category_count,
                    'quantity', cb.category_quantity,
                    'value_mrp', cb.category_value_mrp,
                    'value_cost', cb.category_value_cost
                )
            )
            FROM category_breakdown cb
            WHERE cb.week_number = we.week_number
        ) as expired_by_category
    FROM weekly_expired we
    GROUP BY we.week_number, we.week_start, we.week_end
)
SELECT 
    week_number,
    week_start::text,
    week_end::text,
    expired_count,
    expired_quantity,
    expired_value_mrp,
    expired_value_cost,
    expired_by_category,
    -- Calculate waste rate
    (SELECT COUNT(*) FROM products WHERE expiry_date >= week_start AND expiry_date <= week_end) as total_products_in_period,
    CASE 
        WHEN (SELECT COUNT(*) FROM products WHERE expiry_date >= week_start AND expiry_date <= week_end) > 0
        THEN expired_count::float / (SELECT COUNT(*) FROM products WHERE expiry_date >= week_start AND expiry_date <= week_end) * 100
        ELSE 0
    END as waste_rate_pct
FROM weekly_aggregated
ORDER BY week_number;

-- 4. Dead Stock Risk View
-- Real-time dead stock risk calculation
CREATE OR REPLACE VIEW dead_stock_risk_products AS
SELECT 
    product_id,
    name,
    category,
    brand,
    days_until_expiry,
    current_discount_percent,
    price_mrp,
    inventory_quantity,
    expiry_date::text,
    risk_score,
    calculated_dead_stock_risk as is_dead_stock_risk,
    -- Additional risk indicators
    CASE
        WHEN days_until_expiry <= 3 THEN 'CRITICAL'
        WHEN days_until_expiry <= 7 THEN 'HIGH'
        WHEN days_until_expiry <= 14 THEN 'MEDIUM'
        ELSE 'LOW'
    END as risk_level,
    -- Recommended discount based on risk
    CASE
        WHEN days_until_expiry <= 3 THEN GREATEST(current_discount_percent, 50)
        WHEN days_until_expiry <= 7 THEN GREATEST(current_discount_percent, 30)
        WHEN days_until_expiry <= 14 THEN GREATEST(current_discount_percent, 20)
        ELSE current_discount_percent
    END as recommended_discount_percent,
    -- Potential loss if not sold
    inventory_quantity * price_mrp as potential_loss
FROM products_enriched
WHERE days_until_expiry > 0  -- Not yet expired
ORDER BY risk_score DESC, days_until_expiry ASC;

-- 5. User Purchase Patterns View
-- Pre-calculates user metrics for recommendation engine
CREATE OR REPLACE VIEW user_purchase_patterns AS
WITH user_transactions AS (
    SELECT 
        u.user_id,
        u.diet_type,
        u.allergies,
        u.preferred_categories,
        COUNT(DISTINCT t.transaction_id) as total_purchases,
        COUNT(DISTINCT t.product_id) as unique_products_purchased,
        COUNT(DISTINCT p.category) as categories_purchased,
        SUM(t.total_price_paid) as total_spent,
        AVG(t.total_price_paid) as avg_order_value,
        MAX(t.purchase_date) as last_purchase_date,
        AVG(t.discount_percent) as avg_discount_taken,
        SUM(CASE WHEN t.user_engaged_with_deal = 1 THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) as deal_engagement_rate
    FROM users u
    LEFT JOIN transactions t ON u.user_id = t.user_id
    LEFT JOIN products p ON t.product_id = p.product_id
    GROUP BY u.user_id, u.diet_type, u.allergies, u.preferred_categories
),
category_preferences AS (
    SELECT 
        t.user_id,
        p.category,
        COUNT(*) as purchase_count,
        SUM(t.quantity) as total_quantity,
        SUM(t.total_price_paid) as category_spend
    FROM transactions t
    JOIN products p ON t.product_id = p.product_id
    GROUP BY t.user_id, p.category
)
SELECT 
    ut.*,
    -- Most purchased category
    (
        SELECT category 
        FROM category_preferences cp 
        WHERE cp.user_id = ut.user_id 
        ORDER BY purchase_count DESC 
        LIMIT 1
    ) as top_category,
    -- Category distribution as JSONB
    (
        SELECT jsonb_object_agg(category, purchase_count)
        FROM category_preferences cp
        WHERE cp.user_id = ut.user_id
    ) as category_distribution,
    -- Days since last purchase
    CURRENT_DATE - ut.last_purchase_date as days_since_last_purchase,
    -- Purchase frequency (purchases per month)
    CASE 
        WHEN ut.last_purchase_date IS NOT NULL 
        THEN ut.total_purchases::float / NULLIF(CURRENT_DATE - (SELECT MIN(purchase_date) FROM transactions WHERE user_id = ut.user_id), 0) * 30
        ELSE 0
    END as purchase_frequency_per_month
FROM user_transactions ut;

-- 6. Product Performance Summary View
-- Aggregated product performance metrics
CREATE OR REPLACE VIEW product_performance_summary AS
SELECT 
    category,
    COUNT(DISTINCT product_id) as product_count,
    SUM(inventory_quantity) as total_inventory,
    SUM(total_cost) as total_inventory_value,
    SUM(actual_revenue_generated) as total_revenue,
    AVG(inventory_turnover_rate) as avg_turnover_rate,
    AVG(days_until_expiry) as avg_days_until_expiry,
    SUM(CASE WHEN calculated_dead_stock_risk = 1 THEN 1 ELSE 0 END) as at_risk_products,
    SUM(CASE WHEN days_until_expiry < 0 THEN 1 ELSE 0 END) as expired_products,
    AVG(current_discount_percent) as avg_discount,
    AVG(deal_engagement_rate) as avg_deal_engagement
FROM products_enriched
GROUP BY category;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_transactions_product_date ON transactions(product_id, purchase_date);
CREATE INDEX IF NOT EXISTS idx_products_expiry_date ON products(expiry_date);
CREATE INDEX IF NOT EXISTS idx_products_packaging_date ON products(packaging_date);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);

-- Grant permissions
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO authenticated;

-- =====================================================
-- Inventory Summary View
-- =====================================================

-- Create a view that provides real-time inventory summary metrics
CREATE OR REPLACE VIEW inventory_summary AS
WITH categorized_inventory AS (
    SELECT 
        product_id,
        name,
        category,
        inventory_quantity,
        cost_price,
        days_until_expiry,
        calculated_dead_stock_risk,
        -- Calculate cost for each product (qty * cost_price)
        inventory_quantity * cost_price as product_cost,
        -- Categorize products
        CASE 
            WHEN days_until_expiry < 0 THEN 'expired'
            WHEN calculated_dead_stock_risk = 1 THEN 'at_risk'
            ELSE 'alive'
        END as status
    FROM products_enriched
)
SELECT 
    -- Alive inventory metrics (non-expired, not at risk)
    COUNT(CASE WHEN status = 'alive' THEN 1 END) as alive_products_count,
    COALESCE(SUM(CASE WHEN status = 'alive' THEN product_cost END), 0) as alive_inventory_cost,
    COALESCE(SUM(CASE WHEN status = 'alive' THEN inventory_quantity END), 0) as alive_inventory_qty,
    
    -- At risk inventory metrics
    COUNT(CASE WHEN status = 'at_risk' THEN 1 END) as at_risk_products_count,
    COALESCE(SUM(CASE WHEN status = 'at_risk' THEN product_cost END), 0) as at_risk_inventory_cost,
    COALESCE(SUM(CASE WHEN status = 'at_risk' THEN inventory_quantity END), 0) as at_risk_inventory_qty,
    
    -- Expired inventory metrics
    COUNT(CASE WHEN status = 'expired' THEN 1 END) as expired_products_count,
    COALESCE(SUM(CASE WHEN status = 'expired' THEN product_cost END), 0) as expired_inventory_cost,
    COALESCE(SUM(CASE WHEN status = 'expired' THEN inventory_quantity END), 0) as expired_inventory_qty,
    
    -- Total metrics
    COUNT(*) as total_products_count,
    COALESCE(SUM(product_cost), 0) as total_inventory_cost,
    COALESCE(SUM(inventory_quantity), 0) as total_inventory_qty,
    
    -- Additional useful metrics
    COUNT(CASE WHEN days_until_expiry >= 0 AND days_until_expiry <= 7 THEN 1 END) as expiring_within_week_count,
    COALESCE(SUM(CASE WHEN days_until_expiry >= 0 AND days_until_expiry <= 7 THEN product_cost END), 0) as expiring_within_week_cost,
    
    -- Percentage calculations
    CASE 
        WHEN SUM(product_cost) > 0 
        THEN ROUND((SUM(CASE WHEN status = 'at_risk' THEN product_cost END) / SUM(product_cost) * 100)::numeric, 2)
        ELSE 0 
    END as at_risk_cost_percentage,
    
    CASE 
        WHEN SUM(product_cost) > 0 
        THEN ROUND((SUM(CASE WHEN status = 'expired' THEN product_cost END) / SUM(product_cost) * 100)::numeric, 2)
        ELSE 0 
    END as expired_cost_percentage,
    
    -- Timestamp for when this was calculated
    CURRENT_TIMESTAMP as calculated_at
FROM categorized_inventory;

-- Create a more detailed view by category
CREATE OR REPLACE VIEW inventory_summary_by_category AS
WITH categorized_inventory AS (
    SELECT 
        product_id,
        name,
        category,
        inventory_quantity,
        cost_price,
        days_until_expiry,
        calculated_dead_stock_risk,
        inventory_quantity * cost_price as product_cost,
        CASE 
            WHEN days_until_expiry < 0 THEN 'expired'
            WHEN calculated_dead_stock_risk = 1 THEN 'at_risk'
            ELSE 'alive'
        END as status
    FROM products_enriched
)
SELECT 
    category,
    -- Alive inventory metrics
    COUNT(CASE WHEN status = 'alive' THEN 1 END) as alive_products_count,
    COALESCE(SUM(CASE WHEN status = 'alive' THEN product_cost END), 0) as alive_inventory_cost,
    
    -- At risk inventory metrics
    COUNT(CASE WHEN status = 'at_risk' THEN 1 END) as at_risk_products_count,
    COALESCE(SUM(CASE WHEN status = 'at_risk' THEN product_cost END), 0) as at_risk_inventory_cost,
    
    -- Expired inventory metrics
    COUNT(CASE WHEN status = 'expired' THEN 1 END) as expired_products_count,
    COALESCE(SUM(CASE WHEN status = 'expired' THEN product_cost END), 0) as expired_inventory_cost,
    
    -- Total for this category
    COUNT(*) as total_products_count,
    COALESCE(SUM(product_cost), 0) as total_inventory_cost
FROM categorized_inventory
GROUP BY category
ORDER BY total_inventory_cost DESC;

-- Grant permissions for inventory summary views
GRANT SELECT ON inventory_summary TO anon;
GRANT SELECT ON inventory_summary TO authenticated;
GRANT SELECT ON inventory_summary_by_category TO anon;
GRANT SELECT ON inventory_summary_by_category TO authenticated;
"""
    
    return sql

def main():
    """Main function to create views"""
    sql = generate_views_sql()
    
    print("=" * 60)
    print("Performance Optimization Views SQL")
    print("=" * 60)
    print("\nThis script generates SQL to create database views that replace")
    print("looping logic in the API with parallel database operations.")
    print("\nBenefits:")
    print("- Leverages PostgreSQL's parallel query execution")
    print("- Reduces API response time significantly")
    print("- Moves computation to the database layer")
    print("- Pre-computes complex aggregations")
    print("\n" + "=" * 60)
    
    # Save to file
    output_file = "create_performance_views.sql"
    with open(output_file, 'w') as f:
        f.write(sql)
    
    print(f"\n✅ SQL script saved to: {output_file}")
    print("\nTo apply these views to your Supabase database:")
    print("1. Go to your Supabase dashboard")
    print("2. Navigate to SQL Editor")
    print("3. Copy and paste the contents of create_performance_views.sql")
    print("4. Execute the script")
    print("\nOr run directly using Supabase client:")
    print(f"python -c \"from scripts.create_performance_views import apply_views; apply_views()\"")

def apply_views():
    """Apply views directly to Supabase"""
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        sql = generate_views_sql()
        
        print("Applying performance views to Supabase...")
        # Note: Supabase doesn't have a direct SQL execution method in the Python client
        # You'll need to use the SQL editor in the dashboard
        print("\n⚠️  The Supabase Python client doesn't support direct SQL execution.")
        print("Please copy the SQL from 'create_performance_views.sql' and run it in the Supabase SQL Editor.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 