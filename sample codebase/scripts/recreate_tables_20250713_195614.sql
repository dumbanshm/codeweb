
-- WARNING: This script will DROP and RECREATE all tables, deleting all existing data!
-- Make sure you have a backup before running this script.

-- Drop existing views first
DROP VIEW IF EXISTS inventory_analytics CASCADE;
DROP VIEW IF EXISTS product_profitability CASCADE;

-- Drop existing triggers
DROP TRIGGER IF EXISTS update_inventory_on_transaction ON transactions;
DROP TRIGGER IF EXISTS update_revenue_on_transaction ON transactions;

-- Drop existing functions
DROP FUNCTION IF EXISTS update_inventory_on_transaction_fn() CASCADE;
DROP FUNCTION IF EXISTS update_revenue_on_transaction_fn() CASCADE;
DROP FUNCTION IF EXISTS get_product_profitability() CASCADE;

-- Drop existing tables
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Create users table
CREATE TABLE users (
    user_id VARCHAR(10) PRIMARY KEY,
    age INTEGER NOT NULL CHECK (age >= 18 AND age <= 100),
    gender VARCHAR(10) NOT NULL CHECK (gender IN ('male', 'female', 'other')),
    diet_type VARCHAR(20) NOT NULL CHECK (diet_type IN ('vegan', 'vegetarian', 'non-vegetarian', 'eggitarian')),
    allergies JSONB DEFAULT '[]',
    prefers_discount BOOLEAN DEFAULT false,
    location_lat DECIMAL(10, 7) NOT NULL,
    location_lon DECIMAL(10, 7) NOT NULL,
    preferred_categories JSONB DEFAULT '[]',
    last_purchase_date DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create products table
CREATE TABLE products (
    product_id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL CHECK (category IN ('Dairy', 'Vegetables', 'Fruits', 'Meat', 'Grains', 'Snacks', 'Beverages', 'Biscuits', 'Sauces', 'Spreads', 'Cheese')),
    brand VARCHAR(100) NOT NULL,
    diet_type VARCHAR(20) NOT NULL CHECK (diet_type IN ('vegan', 'vegetarian', 'non-vegetarian', 'eggitarian')),
    allergens TEXT[] DEFAULT '{}',
    shelf_life_days INTEGER NOT NULL CHECK (shelf_life_days > 0),
    packaging_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    weight_grams INTEGER NOT NULL CHECK (weight_grams > 0),
    price_mrp DECIMAL(10, 2) NOT NULL CHECK (price_mrp > 0),
    cost_price DECIMAL(10, 2) NOT NULL CHECK (cost_price > 0 AND cost_price < price_mrp),
    current_discount_percent DECIMAL(5, 2) DEFAULT 0 CHECK (current_discount_percent >= 0 AND current_discount_percent < 100),
    inventory_quantity INTEGER DEFAULT 200 CHECK (inventory_quantity >= 0),
    initial_inventory_quantity INTEGER NOT NULL CHECK (initial_inventory_quantity > 0),
    total_cost DECIMAL(12, 2) NOT NULL CHECK (total_cost > 0),
    revenue_generated DECIMAL(12, 2) DEFAULT 0 CHECK (revenue_generated >= 0),
    store_location_lat DECIMAL(10, 8) NOT NULL,
    store_location_lon DECIMAL(11, 8) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT expiry_after_packaging CHECK (expiry_date > packaging_date)
);

-- Create transactions table
CREATE TABLE transactions (
    transaction_id SERIAL PRIMARY KEY,
    user_id VARCHAR(10) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    product_id VARCHAR(10) NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    purchase_date DATE NOT NULL DEFAULT CURRENT_DATE,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price_paid_per_unit DECIMAL(10, 2) NOT NULL CHECK (price_paid_per_unit > 0),
    total_price_paid DECIMAL(10, 2) NOT NULL CHECK (total_price_paid > 0),
    discount_percent DECIMAL(5, 2) DEFAULT 0 CHECK (discount_percent >= 0 AND discount_percent < 100),
    product_diet_type VARCHAR(20) NOT NULL,
    user_diet_type VARCHAR(20) NOT NULL,
    days_to_expiry_at_purchase INTEGER NOT NULL,
    user_engaged_with_deal INTEGER DEFAULT 0 CHECK (user_engaged_with_deal IN (0, 1)),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_product_id ON transactions(product_id);
CREATE INDEX idx_transactions_purchase_date ON transactions(purchase_date);
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_products_diet_type ON products(diet_type);
CREATE INDEX idx_products_expiry_date ON products(expiry_date);
CREATE INDEX idx_users_diet_type ON users(diet_type);
CREATE INDEX idx_users_location ON users(location_lat, location_lon);

-- Create function to update inventory on transaction
CREATE OR REPLACE FUNCTION update_inventory_on_transaction_fn()
RETURNS TRIGGER AS $$
BEGIN
    -- Update inventory quantity
    UPDATE products 
    SET inventory_quantity = inventory_quantity - NEW.quantity,
        updated_at = NOW()
    WHERE product_id = NEW.product_id;
    
    -- Check if inventory is negative (shouldn't happen with proper validation)
    IF (SELECT inventory_quantity FROM products WHERE product_id = NEW.product_id) < 0 THEN
        RAISE EXCEPTION 'Insufficient inventory for product %', NEW.product_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create function to update revenue on transaction
CREATE OR REPLACE FUNCTION update_revenue_on_transaction_fn()
RETURNS TRIGGER AS $$
BEGIN
    -- Update revenue_generated
    UPDATE products 
    SET revenue_generated = revenue_generated + NEW.total_price_paid,
        updated_at = NOW()
    WHERE product_id = NEW.product_id;
    
    -- Update user's last purchase date
    UPDATE users 
    SET last_purchase_date = NEW.purchase_date,
        updated_at = NOW()
    WHERE user_id = NEW.user_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers
CREATE TRIGGER update_inventory_on_transaction
AFTER INSERT ON transactions
FOR EACH ROW
EXECUTE FUNCTION update_inventory_on_transaction_fn();

CREATE TRIGGER update_revenue_on_transaction
AFTER INSERT ON transactions
FOR EACH ROW
EXECUTE FUNCTION update_revenue_on_transaction_fn();

-- Create inventory analytics view
CREATE VIEW inventory_analytics AS
SELECT 
    p.product_id,
    p.name,
    p.category,
    p.brand,
    p.initial_inventory_quantity,
    p.inventory_quantity as current_inventory,
    p.initial_inventory_quantity - p.inventory_quantity as units_sold,
    p.cost_price,
    p.price_mrp,
    p.total_cost as initial_investment,
    p.revenue_generated,
    p.revenue_generated - ((p.initial_inventory_quantity - p.inventory_quantity) * p.cost_price) as gross_profit,
    CASE 
        WHEN p.revenue_generated > 0 THEN 
            ROUND(((p.revenue_generated - ((p.initial_inventory_quantity - p.inventory_quantity) * p.cost_price)) / p.revenue_generated * 100)::numeric, 1)
        ELSE 0 
    END as profit_margin,
    DATE_PART('day', p.expiry_date - CURRENT_DATE)::integer as days_until_expiry,
    p.current_discount_percent,
    p.expiry_date,
    p.created_at,
    p.updated_at
FROM products p
WHERE p.initial_inventory_quantity > p.inventory_quantity; -- Only show products with sales

-- Create product profitability function (for compatibility)
CREATE OR REPLACE FUNCTION get_product_profitability()
RETURNS TABLE (
    product_id VARCHAR(10),
    name VARCHAR(200),
    category VARCHAR(50),
    units_sold INTEGER,
    revenue_generated DECIMAL(12, 2),
    cost_of_goods_sold DECIMAL(12, 2),
    gross_profit DECIMAL(12, 2),
    profit_margin DECIMAL(5, 2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.product_id,
        p.name,
        p.category,
        (p.initial_inventory_quantity - p.inventory_quantity)::INTEGER as units_sold,
        p.revenue_generated,
        ((p.initial_inventory_quantity - p.inventory_quantity) * p.cost_price)::DECIMAL(12, 2) as cost_of_goods_sold,
        (p.revenue_generated - ((p.initial_inventory_quantity - p.inventory_quantity) * p.cost_price))::DECIMAL(12, 2) as gross_profit,
        CASE 
            WHEN p.revenue_generated > 0 THEN 
                ((p.revenue_generated - ((p.initial_inventory_quantity - p.inventory_quantity) * p.cost_price)) / p.revenue_generated * 100)::DECIMAL(5, 2)
            ELSE 0::DECIMAL(5, 2)
        END as profit_margin
    FROM products p
    WHERE p.initial_inventory_quantity > p.inventory_quantity
    ORDER BY p.revenue_generated DESC;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions (adjust based on your Supabase settings)
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO anon;

