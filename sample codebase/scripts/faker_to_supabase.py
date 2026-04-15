#!/usr/bin/env python3
"""
Faker script to generate and insert data directly into Supabase.
This script creates users, products, and transactions data.
"""

from faker import Faker
import random
from datetime import timedelta, datetime, date
import os
import sys
from supabase import create_client, Client
import logging
from typing import List, Dict, Any
import json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://bwysarrweyooqtjkowzp.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ3eXNhcnJ3ZXlvb3F0amtvd3pwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIzNTIzODEsImV4cCI6MjA2NzkyODM4MX0.cfOrT6MXZ9XHAjYC0K1rri1C4-jGmBbE9q0RQLpR3d8")

# Initialize Faker
fake = Faker()

# Configuration
NUM_USERS = 200
NUM_PRODUCTS = 300
NUM_TRANSACTIONS = 1000

# Categories and brands
CATEGORIES = ['Dairy', 'Vegetables', 'Fruits', 'Meat', 'Grains', 'Snacks', 'Beverages', 
              'Biscuits', 'Sauces', 'Spreads', 'Cheese']

BRANDS_BY_CATEGORY = {
    'Dairy': ['Amul', 'Mother Dairy', 'Nestle', 'Britannia', 'Danone'],
    'Vegetables': ['Fresh Farm', 'Green Valley', 'Organic Plus', 'Nature Fresh', 'Farm Direct'],
    'Fruits': ['Sweet Harvest', 'Garden Fresh', 'Tropical Delight', 'Pure Fruit', 'Orchard Select'],
    'Meat': ['Fresh Cuts', 'Premium Meats', 'Farm Fresh', 'Quality Cuts', 'Organic Meat Co'],
    'Grains': ['Golden Harvest', 'Farm Pride', 'Healthy Grains', 'Nature Mills', 'Whole Grain Co'],
    'Snacks': ['Lay\'s', 'Haldiram\'s', 'Bikano', 'Kurkure', 'Pringles', 'Doritos'],
    'Beverages': ['Coca Cola', 'Pepsi', 'Tropicana', 'Real', 'Minute Maid', 'Mountain Dew'],
    'Biscuits': ['Parle', 'Britannia', 'Sunfeast', 'McVities', 'Oreo'],
    'Sauces': ['Kissan', 'Maggi', 'Del Monte', 'Heinz', 'Knorr'],
    'Spreads': ['Nutella', 'Kissan', 'Sundrop', 'Amul', 'Skippy'],
    'Cheese': ['Amul', 'Britannia', 'Go', 'La Vache Qui Rit', 'President']
}

# Product name templates by category
PRODUCT_TEMPLATES = {
    'Dairy': ['Fresh {adjective} Milk', '{adjective} Yogurt', 'Premium {adjective} Butter', '{adjective} Paneer'],
    'Vegetables': ['{adjective} Tomatoes', 'Fresh {adjective} Onions', '{adjective} Potatoes', 'Organic {adjective} Carrots'],
    'Fruits': ['{adjective} Apples', 'Fresh {adjective} Bananas', '{adjective} Oranges', 'Premium {adjective} Mangoes'],
    'Meat': ['{adjective} Chicken Breast', 'Fresh {adjective} Mutton', '{adjective} Fish Fillet', 'Premium {adjective} Prawns'],
    'Grains': ['{adjective} Basmati Rice', 'Whole {adjective} Wheat', '{adjective} Oats', 'Organic {adjective} Quinoa'],
    'Snacks': ['{adjective} Chips', 'Crispy {adjective} Namkeen', '{adjective} Mixture', 'Spicy {adjective} Puffs'],
    'Beverages': ['{adjective} Cola', 'Fresh {adjective} Juice', '{adjective} Energy Drink', 'Sparkling {adjective} Water'],
    'Biscuits': ['{adjective} Cream Biscuits', 'Crunchy {adjective} Cookies', '{adjective} Digestive', 'Chocolate {adjective} Wafers'],
    'Sauces': ['{adjective} Tomato Sauce', 'Spicy {adjective} Chili Sauce', '{adjective} Soy Sauce', 'Tangy {adjective} Mustard'],
    'Spreads': ['{adjective} Peanut Butter', 'Creamy {adjective} Jam', '{adjective} Honey', 'Rich {adjective} Chocolate Spread'],
    'Cheese': ['{adjective} Cheddar', 'Fresh {adjective} Mozzarella', '{adjective} Processed Cheese', 'Premium {adjective} Gouda']
}

ADJECTIVES = ['Delicious', 'Fresh', 'Premium', 'Organic', 'Natural', 'Healthy', 'Tasty', 
              'Special', 'Classic', 'Traditional', 'Homestyle', 'Gourmet']

# Allergens
COMMON_ALLERGENS = ['nuts', 'dairy', 'gluten', 'soy', 'eggs', 'shellfish', 'sesame', 'mustard']

# Diet types
DIET_TYPES = ['vegan', 'vegetarian', 'non-vegetarian', 'eggitarian']

class SupabaseFaker:
    def __init__(self):
        """Initialize Supabase client"""
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Connected to Supabase")
        
    def clear_tables(self):
        """Clear existing data from tables (optional)"""
        try:
            # Delete in reverse order due to foreign key constraints
            self.supabase.table('transactions').delete().neq('transaction_id', -1).execute()
            self.supabase.table('products').delete().neq('product_id', 'NONE').execute()
            self.supabase.table('users').delete().neq('user_id', 'NONE').execute()
            logger.info("Cleared existing data from tables")
        except Exception as e:
            logger.warning(f"Could not clear tables: {e}")
    
    def get_allowed_categories(self, diet_type: str) -> List[str]:
        """Get categories that are appropriate for a given diet type"""
        # Categories that contain animal products
        meat_categories = ['Meat']
        dairy_categories = ['Dairy', 'Cheese']
        
        if diet_type == 'vegan':
            # Vegans avoid all animal products
            return [cat for cat in CATEGORIES if cat not in meat_categories + dairy_categories]
        elif diet_type == 'vegetarian':
            # Vegetarians avoid meat but can have dairy
            return [cat for cat in CATEGORIES if cat not in meat_categories]
        elif diet_type == 'eggitarian':
            # Eggitarians avoid meat but can have dairy and eggs
            return [cat for cat in CATEGORIES if cat not in meat_categories]
        else:  # non-vegetarian
            # Non-vegetarians can have any category
            return CATEGORIES
    
    def generate_users(self) -> List[Dict[str, Any]]:
        """Generate fake user data"""
        logger.info(f"Generating {NUM_USERS} users...")
        
        users = []
        for i in range(NUM_USERS):
            # Generate allergies
            num_allergies = random.choices([0, 1, 2, 3], weights=[50, 30, 15, 5])[0]
            allergies = random.sample(COMMON_ALLERGENS, num_allergies) if num_allergies > 0 else []
            
            # Diet type distribution (similar to old faker)
            diet_type = random.choices(
                DIET_TYPES,
                weights=[15, 40, 35, 10]  # vegan, vegetarian, non-veg, eggitarian
            )[0]
            
            # Generate preferred categories based on diet type
            allowed_categories = self.get_allowed_categories(diet_type)
            num_categories = random.randint(2, min(5, len(allowed_categories)))
            preferred_categories = random.sample(allowed_categories, num_categories)
            
            # Generate gender
            gender = random.choice(['male', 'female', 'other'])
            
            user = {
                'user_id': f'U{i:04d}',
                'age': random.randint(18, 70),
                'gender': gender,
                'diet_type': diet_type,
                'allergies': allergies,
                'prefers_discount': random.choice([True, False]),
                'location_lat': round(float(fake.latitude()), 7),
                'location_lon': round(float(fake.longitude()), 7),
                'preferred_categories': preferred_categories,
                'last_purchase_date': fake.date_between(start_date='-60d', end_date='today').isoformat()
            }
            users.append(user)
        
        return users
    
    def generate_products(self) -> List[Dict[str, Any]]:
        """Generate fake product data"""
        logger.info(f"Generating {NUM_PRODUCTS} products...")
        
        products = []
        product_counter = 0
        
        # Distribute products across categories
        products_per_category = NUM_PRODUCTS // len(CATEGORIES)
        extra_products = NUM_PRODUCTS % len(CATEGORIES)
        
        for category_idx, category in enumerate(CATEGORIES):
            # Add extra products to first few categories
            num_products_in_category = products_per_category + (1 if category_idx < extra_products else 0)
            
            for _ in range(num_products_in_category):
                product_id = f'P{product_counter:04d}'
                product_counter += 1
                
                # Select brand and generate name
                brand = random.choice(BRANDS_BY_CATEGORY[category])
                template = random.choice(PRODUCT_TEMPLATES[category])
                adjective = random.choice(ADJECTIVES)
                name = f"{brand} {template.format(adjective=adjective)}"
                
                # Generate shelf life based on category
                if category in ['Dairy', 'Meat', 'Vegetables', 'Fruits']:
                    shelf_life = random.randint(3, 14)  # Perishable
                elif category in ['Beverages']:
                    shelf_life = random.randint(30, 365)  # Beverages
                elif category in ['Cheese', 'Spreads']:
                    shelf_life = random.randint(30, 180)  # Medium shelf life
                else:  # Grains, Snacks, Biscuits, Sauces
                    shelf_life = random.randint(60, 730)  # Non-perishable
                
                # Generate dates
                packaging_date = fake.date_between(start_date='-60d', end_date='today')
                expiry_date = packaging_date + timedelta(days=shelf_life)
                days_until_expiry = (expiry_date - date.today()).days
                
                # Set diet type based on category
                if category == 'Meat':
                    diet_type = 'non-vegetarian'
                elif category in ['Dairy', 'Cheese']:
                    # Dairy products can be vegetarian or eggitarian
                    diet_type = random.choice(['vegetarian', 'eggitarian'])
                else:
                    # Other categories can be vegan or vegetarian
                    diet_type = random.choice(['vegan', 'vegetarian'])
                
                # Generate allergens based on category
                category_allergens = []
                if category in ['Dairy', 'Cheese']:
                    category_allergens.append('dairy')
                if category in ['Grains', 'Biscuits']:
                    if random.random() < 0.3:
                        category_allergens.append('gluten')
                if category in ['Snacks', 'Spreads']:
                    if random.random() < 0.4:
                        category_allergens.append('nuts')
                if category == 'Sauces':
                    if random.random() < 0.2:
                        category_allergens.append('soy')
                
                # Add random additional allergens
                if random.random() < 0.15:
                    additional_allergen = random.choice([a for a in COMMON_ALLERGENS if a not in category_allergens])
                    category_allergens.append(additional_allergen)
                
                # Pricing
                price_mrp = round(random.uniform(20, 500), 2)
                cost_price = round(price_mrp * random.uniform(0.40, 0.45), 2)
                
                # Inventory (some items have low inventory)
                if random.random() < 0.1:  # 10% have low inventory
                    inventory_quantity = random.randint(5, 50)
                else:
                    inventory_quantity = random.randint(100, 500)
                
                initial_inventory_quantity = inventory_quantity
                
                # Higher discount for items close to expiry
                if days_until_expiry <= 3:
                    current_discount = random.choice([30, 40, 50, 60])
                elif days_until_expiry <= 7:
                    current_discount = random.choice([20, 30, 40])
                elif days_until_expiry <= 14:
                    current_discount = random.choice([10, 15, 20])
                else:
                    current_discount = random.choice([0, 0, 0, 5, 10])  # Most items have no discount
                
                # Calculate total cost
                total_cost = round(initial_inventory_quantity * cost_price, 2)
                
                product = {
                    'product_id': product_id,
                    'name': name,
                    'category': category,
                    'brand': brand,
                    'diet_type': diet_type,
                    'allergens': category_allergens,
                    'shelf_life_days': shelf_life,
                    'packaging_date': packaging_date.isoformat(),
                    'expiry_date': expiry_date.isoformat(),
                    'weight_grams': random.choice([100, 250, 500, 750, 1000, 1500, 2000]),
                    'price_mrp': price_mrp,
                    'cost_price': cost_price,
                    'current_discount_percent': current_discount,
                    'inventory_quantity': inventory_quantity,
                    'initial_inventory_quantity': initial_inventory_quantity,
                    'total_cost': total_cost,
                    'revenue_generated': 0.0,
                    'store_location_lat': round(float(fake.latitude()), 8),
                    'store_location_lon': round(float(fake.longitude()), 8)
                }
                products.append(product)
        
        return products
    
    def filter_products_for_user(self, products: List[Dict], user: Dict) -> List[Dict]:
        """Filter products based on user's diet type and allergies"""
        allowed_products = []
        
        for product in products:
            # Check diet compatibility
            if user['diet_type'] == 'vegan':
                if product['diet_type'] not in ['vegan']:
                    continue
            elif user['diet_type'] == 'vegetarian':
                if product['diet_type'] not in ['vegan', 'vegetarian']:
                    continue
            elif user['diet_type'] == 'eggitarian':
                if product['diet_type'] not in ['vegan', 'vegetarian', 'eggitarian']:
                    continue
            # non-vegetarians can buy anything
            
            # Check allergies
            product_allergens = product.get('allergens', [])
            user_allergies = user.get('allergies', [])
            if any(allergen in product_allergens for allergen in user_allergies):
                continue
            
            allowed_products.append(product)
        
        return allowed_products
    
    def generate_transactions(self, users: List[Dict], products: List[Dict]) -> List[Dict[str, Any]]:
        """Generate fake transaction data"""
        logger.info(f"Generating {NUM_TRANSACTIONS} transactions...")
        
        transactions = []
        
        # Create user and product lookups
        user_ids = [u['user_id'] for u in users]
        product_lookup = {p['product_id']: p for p in products}
        user_lookup = {u['user_id']: u for u in users}
        
        attempts = 0
        max_attempts = NUM_TRANSACTIONS * 3  # Allow more attempts to reach target
        skipped_date_issues = 0
        skipped_diet_issues = 0
        
        while len(transactions) < NUM_TRANSACTIONS and attempts < max_attempts:
            attempts += 1
            
            # Select random user
            user_id = random.choice(user_ids)
            user = user_lookup[user_id]
            
            # Filter products based on user's diet and allergies
            allowed_products = self.filter_products_for_user(list(product_lookup.values()), user)
            
            if not allowed_products:
                skipped_diet_issues += 1
                continue  # Skip if no compatible products
            
            # Select a product from allowed products
            product = random.choice(allowed_products)
            
            # Parse product dates
            packaging_date = datetime.fromisoformat(product['packaging_date']).date()
            expiry_date = datetime.fromisoformat(product['expiry_date']).date()
            today = date.today()
            
            # Determine valid purchase date range
            # Purchase must be between packaging date and min(expiry date, today)
            earliest_purchase = packaging_date
            latest_purchase = min(expiry_date, today)
            
            # Skip if no valid purchase window (product not yet packaged or already expired)
            if earliest_purchase > latest_purchase:
                skipped_date_issues += 1
                continue
            
            # Generate purchase date within valid range
            purchase_date = fake.date_between(start_date=earliest_purchase, end_date=latest_purchase)
            
            # Calculate days to expiry at purchase
            days_to_expiry = (expiry_date - purchase_date).days
            
            # Quantity (higher for non-perishables)
            if product['category'] in ['Dairy', 'Meat', 'Vegetables', 'Fruits']:
                quantity = random.choices([1, 2, 3], weights=[50, 35, 15])[0]
            else:
                quantity = random.choices([1, 2, 3, 4, 5], weights=[30, 30, 20, 15, 5])[0]
            
            # Apply discount (higher chance if close to expiry or user prefers discount)
            if days_to_expiry <= 7 or (user['prefers_discount'] and random.random() < 0.7):
                discount_percent = product['current_discount_percent']
                user_engaged_with_deal = 1
            elif user['prefers_discount'] and product['current_discount_percent'] > 20:
                # Discount-preferring users might still buy high-discount items
                discount_percent = product['current_discount_percent'] if random.random() < 0.4 else 0
                user_engaged_with_deal = 1 if discount_percent > 0 else 0
            else:
                discount_percent = random.choice([0, 0, 0, 5, 10])  # Mostly no discount
                user_engaged_with_deal = 0
            
            # Calculate prices
            price_paid_per_unit = round(product['price_mrp'] * (1 - discount_percent / 100), 2)
            total_price_paid = round(price_paid_per_unit * quantity, 2)
            
            transaction = {
                'user_id': user_id,
                'product_id': product['product_id'],
                'purchase_date': purchase_date.isoformat(),
                'quantity': quantity,
                'price_paid_per_unit': price_paid_per_unit,
                'total_price_paid': total_price_paid,
                'discount_percent': discount_percent,
                'product_diet_type': product['diet_type'],
                'user_diet_type': user['diet_type'],
                'days_to_expiry_at_purchase': days_to_expiry,
                'user_engaged_with_deal': user_engaged_with_deal
            }
            transactions.append(transaction)
        
        logger.info(f"Generated {len(transactions)} valid transactions after {attempts} attempts")
        if skipped_diet_issues > 0:
            logger.info(f"  - Skipped {skipped_diet_issues} due to diet/allergy incompatibility")
        if skipped_date_issues > 0:
            logger.info(f"  - Skipped {skipped_date_issues} due to invalid date ranges")
        return transactions
    
    def insert_data(self, table_name: str, data: List[Dict], batch_size: int = 100):
        """Insert data into Supabase table in batches"""
        logger.info(f"Inserting {len(data)} records into {table_name}...")
        
        try:
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                response = self.supabase.table(table_name).insert(batch).execute()
                logger.info(f"Inserted batch {i//batch_size + 1} of {len(data)//batch_size + 1} into {table_name}")
            
            logger.info(f"Successfully inserted all records into {table_name}")
            return True
        except Exception as e:
            logger.error(f"Error inserting into {table_name}: {e}")
            return False
    
    def verify_data(self):
        """Verify that data was inserted successfully"""
        logger.info("\nVerifying data insertion...")
        
        try:
            # Count records in each table
            users_count = len(self.supabase.table('users').select("user_id").execute().data)
            products_count = len(self.supabase.table('products').select("product_id").execute().data)
            transactions_count = len(self.supabase.table('transactions').select("transaction_id").execute().data)
            
            logger.info(f"\nData Summary:")
            logger.info(f"Users: {users_count}")
            logger.info(f"Products: {products_count}")
            logger.info(f"Transactions: {transactions_count}")
            
            # Get category distribution
            products_data = self.supabase.table('products').select("category").execute().data
            category_counts = {}
            for p in products_data:
                category = p['category']
                category_counts[category] = category_counts.get(category, 0) + 1
            
            logger.info(f"\nProducts by Category:")
            for category, count in sorted(category_counts.items()):
                logger.info(f"  {category}: {count}")
            
            # Get some expired products
            expired_products = self.supabase.table('products').select("product_id, name, expiry_date").lt('expiry_date', date.today().isoformat()).limit(5).execute()
            logger.info(f"\nFound {len(expired_products.data)} expired products (showing up to 5)")
            
            return True
            
        except Exception as e:
            logger.error(f"Error verifying data: {e}")
            return False

def main():
    """Main function to generate and insert fake data"""
    
    print("\n" + "="*80)
    print("SUPABASE FAKER DATA GENERATOR")
    print("="*80)
    print(f"\nThis script will generate and insert:")
    print(f"- {NUM_USERS} users")
    print(f"- {NUM_PRODUCTS} products")
    print(f"- {NUM_TRANSACTIONS} transactions")
    print("\n" + "="*80 + "\n")
    
    # Confirm with user
    confirm = input("Do you want to proceed? (yes/no): ").lower()
    if confirm != 'yes':
        print("Operation cancelled.")
        return
    
    # Initialize faker
    faker = SupabaseFaker()
    
    # Optional: Clear existing data
    clear_data = input("\nDo you want to clear existing data first? (yes/no): ").lower()
    if clear_data == 'yes':
        faker.clear_tables()
    
    # Generate data
    logger.info("\nGenerating fake data...")
    users = faker.generate_users()
    products = faker.generate_products()
    transactions = faker.generate_transactions(users, products)
    
    # Insert data
    logger.info("\nInserting data into Supabase...")
    success = True
    success &= faker.insert_data('users', users)
    success &= faker.insert_data('products', products)
    success &= faker.insert_data('transactions', transactions)
    
    if success:
        logger.info("\n✅ All data inserted successfully!")
        faker.verify_data()
    else:
        logger.error("\n❌ Some errors occurred during insertion.")
    
    print("\n" + "="*80)
    print("OPERATION COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    main() 