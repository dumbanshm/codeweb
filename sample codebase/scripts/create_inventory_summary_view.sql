-- =====================================================
-- Inventory Summary View for Dashboard
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

-- Grant permissions
GRANT SELECT ON inventory_summary TO anon;
GRANT SELECT ON inventory_summary TO authenticated;
GRANT SELECT ON inventory_summary_by_category TO anon;
GRANT SELECT ON inventory_summary_by_category TO authenticated; 