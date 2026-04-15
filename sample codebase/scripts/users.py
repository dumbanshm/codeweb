from faker import Faker
import pandas as pd
import random
from datetime import datetime, timedelta
import json

fake = Faker()
num_users = 200

# Categories that match your products
categories = ['Dairy', 'Vegetables', 'Fruits', 'Meat', 'Grains', 'Snacks', 'Beverages', 
              'Biscuits', 'Sauces', 'Spreads', 'Cheese']
common_allergens = ['nuts', 'dairy', 'gluten', 'soy', 'eggs', 'shellfish', 'sesame', 'mustard']

def get_allowed_categories(diet_type):
    """Get categories that are appropriate for a given diet type"""
    # Categories that contain animal products
    meat_categories = ['Meat']
    dairy_categories = ['Dairy', 'Cheese']
    
    # All available categories
    all_categories = categories
    
    if diet_type == 'vegan':
        # Vegans avoid all animal products
        return [cat for cat in all_categories if cat not in meat_categories + dairy_categories]
    elif diet_type == 'vegetarian':
        # Vegetarians avoid meat
        return [cat for cat in all_categories if cat not in meat_categories]
    elif diet_type == 'eggitarian':
        # Eggitarians avoid meat but can have dairy and eggs
        return [cat for cat in all_categories if cat not in meat_categories]
    else:  # non-vegetarian
        # Non-vegetarians can have any category
        return all_categories

user_data = []
for i in range(num_users):
    uid = f"U{i:04d}"
    
    # Gender with balanced distribution
    gender = random.choice(['male', 'female', 'other'])
    
    # Age distribution (18-70)
    age = random.randint(18, 70)
    
    # Use diet types that match your model
    # vegan(15%), vegetarian(40%), non-vegetarian(35%), eggitarian(10%)
    diet_type = random.choices(
        ['vegan', 'vegetarian', 'non-vegetarian', 'eggitarian'], 
        weights=[15, 40, 35, 10], 
        k=1
    )[0]
    
    # Generate allergies (some users have none)
    user_allergies = []
    if random.random() < 0.3:  # 30% of users have allergies
        num_allergies = random.randint(1, 2)
        user_allergies = random.sample(common_allergens, num_allergies)
    
    # Generate preferred categories based on diet type
    allowed_categories = get_allowed_categories(diet_type)
    num_preferred = min(len(allowed_categories), random.randint(2, 5))
    preferred_categories = random.sample(allowed_categories, num_preferred)
    
    # Last purchase date (within last 60 days)
    last_purchase = fake.date_between(start_date='-60d', end_date='today')
    
    # Location (Indian cities coordinates)
    # Using some major Indian city coordinates for more realistic data
    city_coords = [
        (28.6139, 77.2090),  # Delhi
        (19.0760, 72.8777),  # Mumbai
        (13.0827, 80.2707),  # Chennai
        (22.5726, 88.3639),  # Kolkata
        (12.9716, 77.5946),  # Bangalore
        (17.3850, 78.4867),  # Hyderabad
        (23.0225, 72.5714),  # Ahmedabad
        (18.5204, 73.8567),  # Pune
    ]
    base_lat, base_lon = random.choice(city_coords)
    # Add some random variation around the city center
    location_lat = round(base_lat + random.uniform(-0.5, 0.5), 7)
    location_lon = round(base_lon + random.uniform(-0.5, 0.5), 7)

    user_data.append({
        'user_id': uid,
        'age': age,
        'gender': gender,
        'diet_type': diet_type,
        'allergies': user_allergies,  # Store as list for Supabase JSONB
        'prefers_discount': random.choice([True, False]),
        'location_lat': location_lat,
        'location_lon': location_lon,
        'preferred_categories': preferred_categories,  # Store as list for Supabase JSONB
        'last_purchase_date': last_purchase.strftime('%Y-%m-%d')
    })

users_df = pd.DataFrame(user_data)

# Convert lists to JSON strings for CSV storage
users_df['allergies'] = users_df['allergies'].apply(lambda x: json.dumps(x))
users_df['preferred_categories'] = users_df['preferred_categories'].apply(lambda x: json.dumps(x))

print(f"Generated {len(users_df)} users")
print(f"\nDiet types distribution:")
print(users_df['diet_type'].value_counts())
print(f"\nUsers with allergies: {len(users_df[users_df['allergies'] != '[]'])}")
print(f"\nGender distribution:")
print(users_df['gender'].value_counts())
print("\nSample users:")
print(users_df.head())

import os
os.makedirs("../datasets", exist_ok=True)
users_df.to_csv("../datasets/users.csv", index=False)
print("\nFile saved to ../datasets/users.csv")