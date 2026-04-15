from faker import Faker
import pandas as pd
import random
from datetime import datetime, date
import os
import json

fake = Faker()

# Load the CSV files from datasets folder
try:
    products_df = pd.read_csv('../datasets/products.csv')
    users_df = pd.read_csv('../datasets/users.csv')
except FileNotFoundError:
    print("ERROR: Please run products.py and users.py first to generate the data files!")
    exit(1)

# Parse JSON fields in users data
users_df['allergies'] = users_df['allergies'].apply(lambda x: json.loads(x) if pd.notna(x) else [])
users_df['preferred_categories'] = users_df['preferred_categories'].apply(lambda x: json.loads(x))

# Convert date columns
products_df['expiry_date'] = pd.to_datetime(products_df['expiry_date']).dt.date
products_df['packaging_date'] = pd.to_datetime(products_df['packaging_date']).dt.date
users_df['last_purchase_date'] = pd.to_datetime(users_df['last_purchase_date']).dt.date

# Convert allergens to list for easier filtering
products_df['allergens_list'] = products_df['allergens'].apply(lambda x: x.split(',') if pd.notna(x) and x else [])

num_transactions = 1000
transaction_data = []
skipped_diet = 0
skipped_date = 0

print("Generating transactions...")

attempts = 0
max_attempts = num_transactions * 3

while len(transaction_data) < num_transactions and attempts < max_attempts:
    attempts += 1
    
    # Pick a random user
    user = users_df.sample(1).iloc[0]
    user_diet = user['diet_type']
    user_allergies = user['allergies'] if isinstance(user['allergies'], list) else []
    
    # Filter products based on user's diet type
    allowed_products = products_df.copy()
    
    # Diet type filtering
    if user_diet == 'vegan':
        allowed_products = allowed_products[allowed_products['diet_type'] == 'vegan']
    elif user_diet == 'vegetarian':
        allowed_products = allowed_products[allowed_products['diet_type'].isin(['vegan', 'vegetarian'])]
    elif user_diet == 'eggitarian':
        allowed_products = allowed_products[allowed_products['diet_type'].isin(['vegan', 'vegetarian', 'eggitarian'])]
    # non-vegetarian users can buy anything
    
    # Allergy filtering - exclude products with user's allergens
    if user_allergies:
    for allergy in user_allergies:
            allowed_products = allowed_products[~allowed_products['allergens_list'].apply(lambda x: allergy in x)]
    
    if allowed_products.empty:
        skipped_diet += 1
        continue  # skip if no matching products
    
    # Select a product
        product = allowed_products.sample(1).iloc[0]
    
    # Generate purchase date that falls between packaging and expiry
    packaging_date = product['packaging_date']
    expiry_date = product['expiry_date']
    today = date.today()
    
    # Purchase must be between packaging date and min(expiry date, today)
    earliest_purchase = packaging_date
    latest_purchase = min(expiry_date, today)
    
    # Skip if no valid purchase window
    if earliest_purchase > latest_purchase:
        skipped_date += 1
        continue
    
    # Generate valid purchase date
    purchase_date = fake.date_between(start_date=earliest_purchase, end_date=latest_purchase)
    
    # Calculate days to expiry at time of purchase
    days_to_expiry_at_purchase = (expiry_date - purchase_date).days
    
    # Determine quantity based on product type and user preferences
    if product['category'] in ['Dairy', 'Meat', 'Vegetables', 'Fruits']:
        # Perishables - buy less
        quantity = random.choices([1, 2, 3], weights=[50, 35, 15])[0]
    else:
        # Non-perishables - can buy more
        quantity = random.choices([1, 2, 3, 4, 5], weights=[30, 30, 20, 15, 5])[0]
    
    # Apply discount logic
    user_engaged_with_deal = 0
    
    # Users are more likely to buy discounted products if they prefer discounts
    if user['prefers_discount'] and product['current_discount_percent'] > 0:
        if random.random() < 0.7:  # 70% chance to take the discount
            discount = product['current_discount_percent']
            user_engaged_with_deal = 1
        else:
            discount = 0
    # Also apply discount for products close to expiry
    elif days_to_expiry_at_purchase <= 7:
    discount = product['current_discount_percent']
        user_engaged_with_deal = 1 if discount > 0 else 0
    else:
        # Random chance of getting a small discount
        discount = random.choice([0, 0, 0, 5, 10]) if random.random() < 0.3 else 0
    
    # Calculate prices
    mrp = product['price_mrp']
    price_paid = round(mrp * (1 - discount / 100), 2)
    total_price = round(price_paid * quantity, 2)

    transaction_data.append({
        'transaction_id': len(transaction_data) + 1,
        'user_id': user['user_id'],
        'product_id': product['product_id'],
        'purchase_date': purchase_date.strftime('%Y-%m-%d'),
        'quantity': quantity,
        'price_paid_per_unit': price_paid,
        'total_price_paid': total_price,
        'discount_percent': discount,
        'product_diet_type': product['diet_type'],
        'user_diet_type': user_diet,
        'days_to_expiry_at_purchase': days_to_expiry_at_purchase,
        'user_engaged_with_deal': user_engaged_with_deal
    })

transactions_df = pd.DataFrame(transaction_data)

print(f"\nGenerated {len(transactions_df)} transactions after {attempts} attempts")
if skipped_diet > 0:
    print(f"  - Skipped {skipped_diet} due to diet/allergy incompatibility")
if skipped_date > 0:
    print(f"  - Skipped {skipped_date} due to invalid date ranges")

print(f"\nTransactions with discounts: {len(transactions_df[transactions_df['discount_percent'] > 0])}")
print(f"User engagement with deals: {transactions_df['user_engaged_with_deal'].sum()}")
print(f"Total revenue: ₹{transactions_df['total_price_paid'].sum():,.2f}")

# Show diet compliance
diet_compliance = transactions_df.groupby(['user_diet_type', 'product_diet_type']).size().unstack(fill_value=0)
print("\nDiet compliance matrix:")
print(diet_compliance)

print("\nSample transactions:")
print(transactions_df.head())

os.makedirs("../datasets", exist_ok=True)
transactions_df.to_csv('../datasets/transactions.csv', index=False)
print("\nFile saved to ../datasets/transactions.csv") 