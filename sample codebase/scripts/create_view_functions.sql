-- =====================================================
-- Helper Functions for Optimized Views
-- =====================================================

-- Function to get current total inventory quantity
CREATE OR REPLACE FUNCTION get_current_inventory_qty()
RETURNS numeric AS $$
BEGIN
    RETURN (
        SELECT COALESCE(SUM(inventory_quantity), 0)
        FROM products
        WHERE expiry_date >= CURRENT_DATE
    );
END;
$$ LANGUAGE plpgsql;

-- Function to get current total inventory cost
CREATE OR REPLACE FUNCTION get_current_inventory_cost()
RETURNS numeric AS $$
BEGIN
    RETURN (
        SELECT COALESCE(SUM(inventory_quantity * cost_price), 0)
        FROM products
        WHERE expiry_date >= CURRENT_DATE
    );
END;
$$ LANGUAGE plpgsql;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION get_current_inventory_qty() TO anon;
GRANT EXECUTE ON FUNCTION get_current_inventory_qty() TO authenticated;
GRANT EXECUTE ON FUNCTION get_current_inventory_cost() TO anon;
GRANT EXECUTE ON FUNCTION get_current_inventory_cost() TO authenticated; 