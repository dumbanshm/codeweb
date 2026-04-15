from faker import Faker
import pandas as pd
import random
from datetime import timedelta, datetime

fake = Faker()
num_products = 300

# Define categories that match your frontend
categories = ['Dairy', 'Vegetables', 'Fruits', 'Meat', 'Grains', 'Snacks', 'Beverages', 
              'Biscuits', 'Sauces', 'Spreads', 'Cheese']

# Define brands for each category
brands_by_category = {
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
product_templates = {
    'Dairy': ['Fresh {adj} Milk', '{adj} Yogurt', 'Premium {adj} Butter', '{adj} Paneer'],
    'Vegetables': ['{adj} Tomatoes', 'Fresh {adj} Onions', '{adj} Potatoes', 'Organic {adj} Carrots'],
    'Fruits': ['{adj} Apples', 'Fresh {adj} Bananas', '{adj} Oranges', 'Premium {adj} Mangoes'],
    'Meat': ['{adj} Chicken Breast', 'Fresh {adj} Mutton', '{adj} Fish Fillet', 'Premium {adj} Prawns'],
    'Grains': ['{adj} Basmati Rice', 'Whole {adj} Wheat', '{adj} Oats', 'Organic {adj} Quinoa'],
    'Snacks': ['{adj} Chips', 'Crispy {adj} Namkeen', '{adj} Mixture', 'Spicy {adj} Puffs'],
    'Beverages': ['{adj} Cola', 'Fresh {adj} Juice', '{adj} Energy Drink', 'Sparkling {adj} Water'],
    'Biscuits': ['{adj} Cream Biscuits', 'Crunchy {adj} Cookies', '{adj} Digestive', 'Chocolate {adj} Wafers'],
    'Sauces': ['{adj} Tomato Sauce', 'Spicy {adj} Chili Sauce', '{adj} Soy Sauce', 'Tangy {adj} Mustard'],
    'Spreads': ['{adj} Peanut Butter', 'Creamy {adj} Jam', '{adj} Honey', 'Rich {adj} Chocolate Spread'],
    'Cheese': ['{adj} Cheddar', 'Fresh {adj} Mozzarella', '{adj} Processed Cheese', 'Premium {adj} Gouda']
}

adjectives = ['Delicious', 'Fresh', 'Premium', 'Organic', 'Natural', 'Healthy', 'Tasty', 
              'Special', 'Classic', 'Traditional', 'Homestyle', 'Gourmet']

# Define allergens
common_allergens = ['nuts', 'dairy', 'gluten', 'soy', 'eggs', 'shellfish', 'sesame', 'mustard']

product_data = []
for i in range(num_products):
    pid = f"P{i:04d}"
    category = random.choice(categories)
    brand = random.choice(brands_by_category[category])
    
    # Generate product name using template
    template = random.choice(product_templates[category])
    adj = random.choice(adjectives)
    name = f"{brand} {template.format(adj=adj)}"
    
    # Generate appropriate shelf life based on category
    if category in ['Dairy', 'Meat', 'Vegetables', 'Fruits']:
        shelf_life = random.randint(3, 14)  # Perishable items: 3-14 days
    elif category in ['Beverages']:
        shelf_life = random.randint(30, 365)  # Beverages: 1 month to 1 year
    elif category in ['Cheese', 'Spreads']:
        shelf_life = random.randint(30, 180)  # Medium shelf life
    else:  # Grains, Snacks, Biscuits, Sauces
        shelf_life = random.randint(60, 730)  # Non-perishable: 2 months to 2 years
    
    packaging_date = fake.date_between(start_date='-60d', end_date='today')
    expiry_date = packaging_date + timedelta(days=shelf_life)
    
    # Calculate days until expiry
    days_until_expiry = (expiry_date - datetime.today().date()).days
    
    # Set diet type based on category
    if category == 'Meat':
        diet_type = 'non-vegetarian'
    elif category in ['Dairy', 'Cheese']:
        diet_type = random.choice(['vegetarian', 'eggitarian'])
    else:
        diet_type = random.choice(['vegan', 'vegetarian'])
    
    # Generate allergens based on category
    category_allergens = []
    if category in ['Dairy', 'Cheese']:
        category_allergens.append('dairy')
    if category in ['Grains', 'Biscuits']:
        if random.random() < 0.3:  # 30% chance of gluten
            category_allergens.append('gluten')
    if category in ['Snacks', 'Spreads']:
        if random.random() < 0.4:  # 40% chance of nuts
            category_allergens.append('nuts')
    if category == 'Sauces':
        if random.random() < 0.2:  # 20% chance of soy
            category_allergens.append('soy')
    
    # Add random additional allergens
    if random.random() < 0.15:  # 15% chance of additional allergen
        additional_allergen = random.choice([a for a in common_allergens if a not in category_allergens])
        category_allergens.append(additional_allergen)
    
    # Generate price_mrp first
    price_mrp = round(random.uniform(20, 500), 2)
    
    # Calculate cost price (40-45% of MRP)
    cost_price_percentage = random.uniform(0.40, 0.45)
    cost_price = round(price_mrp * cost_price_percentage, 2)
    
    # Higher discount for items close to expiry
    if days_until_expiry <= 3:
        current_discount = random.choice([30, 40, 50, 60])
    elif days_until_expiry <= 7:
        current_discount = random.choice([20, 30, 40])
    elif days_until_expiry <= 14:
        current_discount = random.choice([10, 15, 20])
    else:
        current_discount = random.choice([0, 0, 0, 5, 10])  # Most items have no discount
    
    # Inventory quantity (some items have low inventory)
    if random.random() < 0.1:  # 10% have low inventory
        inventory_quantity = random.randint(5, 50)
    else:
        inventory_quantity = random.randint(100, 500)
    
    initial_inventory_quantity = inventory_quantity  # For new products, these are the same
    
    # Calculate total cost (initial inventory * cost price)
    total_cost = round(initial_inventory_quantity * cost_price, 2)

    product_data.append({
        'product_id': pid,
        'name': name,
        'category': category,
        'brand': brand,
        'diet_type': diet_type,
        'allergens': ','.join(category_allergens) if category_allergens else '',
        'shelf_life_days': shelf_life,
        'packaging_date': packaging_date.strftime('%Y-%m-%d'),
        'expiry_date': expiry_date.strftime('%Y-%m-%d'),
        'days_until_expiry': days_until_expiry,
        'weight_grams': random.choice([100, 250, 500, 750, 1000, 1500, 2000]),
        'price_mrp': price_mrp,
        'cost_price': cost_price,
        'current_discount_percent': current_discount,
        'inventory_quantity': inventory_quantity,
        'initial_inventory_quantity': initial_inventory_quantity,
        'total_cost': total_cost,
        'revenue_generated': 0.0,  # Initialize to 0
        'is_dead_stock_risk': 1 if days_until_expiry <= 7 and current_discount < 30 else 0,
        'store_location_lat': round(fake.latitude(), 8),
        'store_location_lon': round(fake.longitude(), 8)
    })

products_df = pd.DataFrame(product_data)
print(f"Generated {len(products_df)} products")
print(f"Categories: {products_df['category'].value_counts().to_dict()}")
print(f"At-risk products: {products_df['is_dead_stock_risk'].sum()}")
print(f"Total inventory value: ₹{products_df['total_cost'].sum():,.2f}")
print("\nSample products:")
print(products_df.head())

import os
os.makedirs("../datasets", exist_ok=True)
products_df.to_csv("../datasets/products.csv", index=False)
print("\nFile saved to ../datasets/products.csv")