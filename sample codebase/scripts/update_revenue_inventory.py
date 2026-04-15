#!/usr/bin/env python3
"""
Script to update product revenue and inventory based on existing transactions
"""

import os
import sys
from supabase import create_client, Client
import pandas as pd
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://bwysarrweyooqtjkowzp.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ3eXNhcnJ3ZXlvb3F0amtvd3pwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIzNTIzODEsImV4cCI6MjA2NzkyODM4MX0.cfOrT6MXZ9XHAjYC0K1rri1C4-jGmBbE9q0RQLpR3d8")

def update_revenue_inventory_method1():
    """Method 1: Update using aggregated data (most efficient)"""
    logger.info("Method 1: Updating revenue and inventory using aggregated data...")
    
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # First, reset all products to initial state if needed
        reset = input("Reset all products to initial state first? (y/n): ").lower() == 'y'
        if reset:
            logger.info("Resetting all products...")
            # Reset revenue to 0
            supabase.table('products').update({'revenue_generated': 0}).neq('product_id', '').execute()
            # Reset inventory to default (you might want to store original inventory somewhere)
            # supabase.table('products').update({'inventory_quantity': 200}).neq('product_id', '').execute()
            logger.info("Reset complete")
        
        # Get all transactions
        transactions_response = supabase.table('transactions').select("*").execute()
        transactions_df = pd.DataFrame(transactions_response.data)
        
        if len(transactions_df) == 0:
            logger.info("No transactions found")
            return
        
        # Group by product_id to calculate totals
        product_stats = transactions_df.groupby('product_id').agg({
            'quantity': 'sum',
            'total_price_paid': 'sum'
        }).reset_index()
        
        logger.info(f"Updating {len(product_stats)} products based on {len(transactions_df)} transactions...")
        
        # Update each product
        for _, row in product_stats.iterrows():
            product_id = row['product_id']
            total_quantity_sold = row['quantity']
            total_revenue = row['total_price_paid']
            
            # Get current product data
            product_response = supabase.table('products').select("inventory_quantity").eq('product_id', product_id).execute()
            
            if product_response.data:
                # Update product with new values
                update_response = supabase.table('products').update({
                    'revenue_generated': float(total_revenue),
                    # Uncomment if you want to update inventory too
                    # 'inventory_quantity': product_response.data[0]['inventory_quantity'] - total_quantity_sold
                }).eq('product_id', product_id).execute()
                
                logger.info(f"Updated {product_id}: Revenue=${total_revenue:.2f}, Quantity Sold={total_quantity_sold}")
        
        logger.info("✅ Update complete!")
        
    except Exception as e:
        logger.error(f"Error: {e}")

def update_revenue_inventory_method2():
    """Method 2: Iterate through each transaction (slower but more control)"""
    logger.info("Method 2: Processing each transaction individually...")
    
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Get all transactions ordered by date
        transactions_response = supabase.table('transactions').select("*").order('purchase_date').execute()
        transactions = transactions_response.data
        
        logger.info(f"Processing {len(transactions)} transactions...")
        
        # Track updates per product
        product_updates = {}
        
        for i, transaction in enumerate(transactions):
            product_id = transaction['product_id']
            quantity = transaction['quantity']
            revenue = transaction['total_price_paid']
            
            # Accumulate updates
            if product_id not in product_updates:
                product_updates[product_id] = {
                    'quantity_sold': 0,
                    'revenue': 0
                }
            
            product_updates[product_id]['quantity_sold'] += quantity
            product_updates[product_id]['revenue'] += revenue
            
            if (i + 1) % 100 == 0:
                logger.info(f"Processed {i + 1} transactions...")
        
        # Apply updates
        logger.info("Applying updates to products...")
        for product_id, updates in product_updates.items():
            supabase.table('products').update({
                'revenue_generated': updates['revenue']
            }).eq('product_id', product_id).execute()
            
            logger.info(f"Updated {product_id}: Revenue=${updates['revenue']:.2f}")
        
        logger.info("✅ Update complete!")
        
    except Exception as e:
        logger.error(f"Error: {e}")

def create_sql_based_update():
    """Generate SQL to update all products based on transactions"""
    sql_update = """
-- SQL to update all products revenue and inventory based on transactions
-- Run this directly in Supabase SQL Editor

-- Method 1: Update revenue for all products in one query
UPDATE products p
SET revenue_generated = COALESCE((
    SELECT SUM(t.total_price_paid)
    FROM transactions t
    WHERE t.product_id = p.product_id
), 0);

-- Method 2: Update both revenue and adjust inventory
UPDATE products p
SET 
    revenue_generated = COALESCE(subquery.total_revenue, 0),
    inventory_quantity = p.inventory_quantity - COALESCE(subquery.total_quantity, 0)
FROM (
    SELECT 
        product_id,
        SUM(total_price_paid) as total_revenue,
        SUM(quantity) as total_quantity
    FROM transactions
    GROUP BY product_id
) as subquery
WHERE p.product_id = subquery.product_id;

-- Verify the updates
SELECT 
    p.product_id,
    p.name,
    p.category,
    p.inventory_quantity,
    p.revenue_generated,
    COALESCE(t.transaction_count, 0) as transaction_count,
    COALESCE(t.total_quantity_sold, 0) as total_quantity_sold
FROM products p
LEFT JOIN (
    SELECT 
        product_id,
        COUNT(*) as transaction_count,
        SUM(quantity) as total_quantity_sold
    FROM transactions
    GROUP BY product_id
) t ON p.product_id = t.product_id
WHERE p.revenue_generated > 0
ORDER BY p.revenue_generated DESC
LIMIT 20;
"""
    
    print("\n" + "="*60)
    print("SQL-BASED UPDATE")
    print("="*60)
    print("Run this SQL directly in Supabase SQL Editor:")
    print("\n--- START SQL ---")
    print(sql_update)
    print("--- END SQL ---\n")

def show_current_stats():
    """Show current statistics"""
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Get products with revenue
        products_with_revenue = supabase.table('products').select("*").gt('revenue_generated', 0).execute()
        
        # Get all products count
        all_products = supabase.table('products').select("count", count="exact").execute()
        
        # Get transaction count
        transactions = supabase.table('transactions').select("count", count="exact").execute()
        
        print("\n" + "="*60)
        print("CURRENT STATISTICS")
        print("="*60)
        print(f"Total Products: {all_products.count}")
        print(f"Products with Revenue: {len(products_with_revenue.data)}")
        print(f"Total Transactions: {transactions.count}")
        
        if len(products_with_revenue.data) > 0:
            df = pd.DataFrame(products_with_revenue.data)
            total_revenue = df['revenue_generated'].sum()
            print(f"Total Revenue: ${total_revenue:,.2f}")
            
            print("\nTop 5 Revenue Generating Products:")
            top_products = df.nlargest(5, 'revenue_generated')[['product_id', 'name', 'category', 'revenue_generated']]
            for _, product in top_products.iterrows():
                print(f"  {product['product_id']}: {product['name']} - ${product['revenue_generated']:,.2f}")
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Update product revenue and inventory from transactions')
    parser.add_argument('--method', choices=['1', '2', 'sql'], default='1',
                       help='Method to use: 1=aggregated (fast), 2=iterate (slow), sql=show SQL')
    parser.add_argument('--stats', action='store_true', help='Show current statistics only')
    
    args = parser.parse_args()
    
    if args.stats:
        show_current_stats()
    elif args.method == '1':
        update_revenue_inventory_method1()
    elif args.method == '2':
        update_revenue_inventory_method2()
    elif args.method == 'sql':
        create_sql_based_update()
    
    # Always show stats at the end
    if not args.stats:
        show_current_stats() 