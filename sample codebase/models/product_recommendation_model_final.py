import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime, timedelta # Import timedelta for date calculations

# Global DataFrames (will be populated either from CSV or dummy data)
users_df = pd.DataFrame()
products_df = pd.DataFrame()
transactions_df = pd.DataFrame()

# ------------------- Helper Functions (Provided by user, with minor adjustments) ------------------- #

def violates_diet(user_diet, product_diet):
    """Return True if product diet violates user diet preference."""
    # Ensure consistency with our dietary classifications
    if user_diet == "vegetarian" and product_diet in ["non-vegetarian", "eggs"]:
        return True
    if user_diet == "vegan" and product_diet in ["non-vegetarian", "eggs", "dairy"]:
        return True
    return False

def get_discount(days_to_expiry, user_seen_before=False):
    """
    Calculate discount based on days to expiry, optionally penalizing repeat views.
    Adjusted for 3-20 day window.
    """
    min_days_for_discount = 3
    max_days_for_discount = 20 # New threshold

    if days_to_expiry < min_days_for_discount:
        return 0 # Products too close to expiry are not recommended for delivery
    if days_to_expiry > max_days_for_discount:
        return 0 # Products too far from expiry don't get a discount

    # Normalize days_to_expiry within the window [min_days_for_discount, max_days_for_discount]
    # A product expiring in 3 days gets max discount, one in 20 days gets 0%
    if max_days_for_discount - min_days_for_discount > 0:
        normalized_days = (days_to_expiry - min_days_for_discount) / (max_days_for_discount - min_days_for_discount)
    else: # Handle case where window is 0 (e.g., min_days_for_discount == max_days_for_discount)
        normalized_days = 0 if days_to_expiry == min_days_for_discount else 1

    # Non-linear discount curve capped at 50%
    # The formula (1 - normalized_days)**2 ensures higher discount for fewer days left
    base_discount = min(50, int((1 - normalized_days) ** 2 * 50))

    if user_seen_before:
        return min(20, base_discount)  # Max 20% if seen before
    else:
        return base_discount

def days_until_expiry(expiry_date_str):
    """Return days until expiry from today."""
    today = datetime.today().date()
    # Ensure expiry_date_str is a valid date string before parsing
    try:
        expiry = datetime.strptime(str(expiry_date_str), "%Y-%m-%d").date()
    except ValueError:
        return -999 # Indicate invalid date, will be filtered out

    return (expiry - today).days

# ------------------- Data Loading and Preprocessing ------------------- #

def load_and_preprocess_data():
    """
    Loads data from CSV files or creates dummy dataframes if files are not found.
    Performs initial data cleaning and merging.
    Includes handling for 'allergies' and 'allergens_present' columns.
    """
    global users_df, products_df, transactions_df

    try:
        users_df = pd.read_csv('fake_users.csv')
        products_df = pd.read_csv('fake_products.csv')
        transactions_df = pd.read_csv('fake_transactions.csv')
        print("Data loaded successfully from CSVs.")
    except FileNotFoundError as e:
        print(f"Error loading file: {e}. Creating dummy dataframes for demonstration.")
        # Create dummy dataframes if files are not found
        # Dummy Users - Added 'allergies' column
        users_data = {
            'user_id': [f'U{i:04d}' for i in range(5)], # Corrected dummy user IDs
            'diet_type': ['non-vegetarian', 'vegetarian', 'vegan', 'non-vegetarian', 'vegetarian'],
            'allergies': ['', 'nuts,gluten', 'dairy,nuts', '', 'gluten'] # Example allergies
        }
        users_df = pd.DataFrame(users_data)

        # Dummy Products - Added 'allergens_present' column
        products_data = {
            'product_id': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
            'product_name': ['Chicken Breast', 'Tofu', 'Milk', 'Eggs (Dozen)', 'Spinach',
                             'Ground Beef', 'Vegan Cheese', 'Yogurt', 'Salmon Fillet', 'Lentils',
                             'Almond Butter', 'Wheat Bread', 'Gluten-Free Oats', 'Soy Milk'],
            'category': ['Meat', 'Proteins', 'Dairy', 'Eggs', 'Vegetables',
                         'Meat', 'Dairy Alternative', 'Dairy', 'Seafood', 'Legumes',
                         'Spreads', 'Bakery', 'Grains', 'Dairy Alternative'],
            'dietary_classification': ['non-vegetarian', 'vegetarian', 'dairy', 'eggs', 'vegetarian',
                                       'non-vegetarian', 'vegan', 'dairy', 'non-vegetarian', 'vegetarian',
                                       'vegan', 'vegetarian', 'vegan', 'vegan'],
            'expiration_date': [
                (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d'),
                (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d'), # Too close, won't be recommended
                (datetime.now() + timedelta(days=8)).strftime('%Y-%m-%d'),
                (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'), # Too close, won't be recommended
                (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d'),
                (datetime.now() + timedelta(days=6)).strftime('%Y-%m-%d'),
                (datetime.now() + timedelta(days=4)).strftime('%Y-%m-%d'),
                (datetime.now() + timedelta(days=9)).strftime('%Y-%m-%d'),
                (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'), # Exactly 3 days
                (datetime.now() + timedelta(days=15)).strftime('%Y-%m-%d'),
                (datetime.now() + timedelta(days=20)).strftime('%Y-%m-%d'), # Almond Butter (max threshold)
                (datetime.now() + timedelta(days=4)).strftime('%Y-%m-%d'),  # Wheat Bread
                (datetime.now() + timedelta(days=12)).strftime('%Y-%m-%d'), # Gluten-Free Oats
                (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'), # Soy Milk
            ],
            'allergens_present': [
                '', '', 'dairy', 'eggs', '',
                '', '', 'dairy', '', '',
                'nuts', 'gluten', '', '' # Example allergens
            ]
        }
        products_df = pd.DataFrame(products_data)

        # Dummy Transactions (some users buying some products)
        transactions_data = {
            'transaction_id': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
            'user_id': [f'U{i:04d}' for i in [0, 1, 0, 2, 1, 3, 0, 4, 2, 1, 0, 4, 1, 2]], # Corrected dummy user IDs
            'product_id': [101, 102, 104, 106, 101, 103, 105, 102, 107, 104, 111, 112, 113, 114],
            'quantity': [1, 2, 1, 1, 1, 2, 3, 1, 1, 1, 1, 1, 1, 1],
            'purchase_date': [
                (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
                (datetime.now() - timedelta(days=25)).strftime('%Y-%m-%d'),
                (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d'),
                (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d'),
                (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'),
                (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'),
                (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d'),
                (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                (datetime.now() - timedelta(days=0)).strftime('%Y-%m-%d'),
                (datetime.now() - timedelta(days=0)).strftime('%Y-%m-%d'),
                (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'), # Almond Butter
                (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d'), # Wheat Bread
                (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d'), # Gluten-Free Oats - Corrected expiry to be within 3-20 days
                (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'), # Soy Milk - Corrected expiry to be within 3-20 days
            ],
            'price': [10.0, 5.0, 3.0, 4.0, 10.0, 10.0, 2.0, 6.0, 8.0, 4.0, 7.0, 3.5, 6.0, 4.5]
        }
        transactions_df = pd.DataFrame(transactions_data)
        print("Dummy dataframes created.")

    # --- Data Preprocessing ---
    # 1. Users DataFrame: Ensure dietary_preference and allergies are clean
    users_df['diet'] = users_df['diet_type'].str.lower().fillna('unknown')
    # Convert allergies string to a set of individual allergens for efficient lookup
    users_df['allergies'] = users_df['allergies'].apply(
        lambda x: set(item.strip() for item in x.lower().split(',')) if pd.notnull(x) and x.strip() != '' else set()
    )
    users_df.set_index('user_id', inplace=True) # Set user_id as index for direct lookup

    # 2. Products DataFrame:
    #    - Ensure 'expiration_date' is in datetime format.
    products_df['expiry_date'] = pd.to_datetime(products_df['expiry_date'], errors='coerce').dt.strftime('%Y-%m-%d')
    # Check for NaT values that might cause issues and drop rows with them
    if products_df['expiry_date'].isnull().any():
        print("Warning: Some 'expiration_date' values could not be parsed and are NaT. Dropping these rows.")
        products_df.dropna(subset=['expiry_date'], inplace=True)

    products_df['diet_type'] = products_df['diet_type'].str.lower().fillna('unknown')
    # Convert allergens_present string to a set of individual allergens
    products_df['allergens_present'] = products_df['allergens'].apply(
        lambda x: set(item.strip() for item in x.lower().split(',')) if pd.notnull(x) and x.strip() != '' else set()
    )
    products_df.set_index('product_id', inplace=True) # Set product_id as index for direct lookup

    # 3. Transactions DataFrame:
    #    - Ensure 'purchase_date' is in datetime format.
    transactions_df['purchase_date'] = pd.to_datetime(transactions_df['purchase_date'])

    print("\nDataFrames after preprocessing (head):")
    print("Users_df:\n", users_df.head())
    print("Products_df:\n", products_df.head())
    print("Transactions_df:\n", transactions_df.head())


def create_interaction_matrix():
    """
    Creates a user-product interaction matrix from transactions_df.
    Rows are users, columns are products, values are purchase counts.
    """
    # Use pivot_table to create the interaction matrix
    # Fill NaN with 0 for products not purchased by a user
    interaction_matrix = transactions_df.pivot_table(
        index='user_id', columns='product_id', values='quantity', fill_value=0
    )

    # Ensure all users from users_df are present in the matrix
    # And all products from products_df are present as columns
    all_users = users_df.index
    all_products = products_df.index

    # Add missing users/products with 0 interactions
    missing_users = all_users.difference(interaction_matrix.index)
    for user in missing_users:
        interaction_matrix.loc[user] = 0

    missing_products = all_products.difference(interaction_matrix.columns)
    for product in missing_products:
        interaction_matrix[product] = 0

    # Reindex to ensure consistent order for similarity calculations
    interaction_matrix = interaction_matrix.loc[all_users, all_products]

    print("\nInteraction Matrix (head):")
    print(interaction_matrix.head())
    return interaction_matrix

# ------------------- Main Recommendation Function ------------------- #

def recommend_products(user_id, user_data, product_data, interaction_matrix, user_history):
    """
    Recommend products to a user based on similarity and expiry,
    considering dietary preferences and allergies.

    user_id: str/int - User identifier
    user_data: DataFrame - contains 'user_id' (index) and 'diet', 'allergies'
    product_data: DataFrame - contains 'product_id' (index), 'name', 'diet_type', 'expiry_date', 'allergens_present'
    interaction_matrix: DataFrame - user-product interaction matrix (user_id as index, product_id as columns)
    user_history: dict - user_id -> {product_id -> last_seen_timestamp}
    """

    if user_id not in user_data.index:
        print(f"User ID {user_id} not found in user data.")
        return []

    # Get user's vector from the interaction matrix
    user_vector = interaction_matrix.loc[user_id].values.reshape(1, -1)

    # Calculate cosine similarity with all other users
    similarities = cosine_similarity(user_vector, interaction_matrix.values)[0]

    # Get indices of similar users, excluding the user themselves
    # The interaction_matrix.index gives us the actual user_ids in order
    similar_users_indices = similarities.argsort()[::-1]
    similar_users_ids = [interaction_matrix.index[i] for i in similar_users_indices if interaction_matrix.index[i] != user_id]

    recommended = []
    user_diet = user_data.loc[user_id, 'diet']
    user_allergies = user_data.loc[user_id, 'allergies']

    # Keep track of products already considered to avoid duplicates in recommendations
    # This is important because multiple similar users might recommend the same product
    already_recommended_pids = set()

    for sim_user_id in similar_users_ids:
        # Get products purchased by the similar user
        # Filter for products with positive interaction score (purchased)
        sim_user_products = interaction_matrix.loc[sim_user_id][interaction_matrix.loc[sim_user_id] > 0]

        for product_col_idx, score in sim_user_products.items(): # product_col_idx is the actual product_id
            pid = product_col_idx # The column name is the product_id

            if pid in already_recommended_pids:
                continue # Skip if already processed

            if pid not in product_data.index:
                # This should ideally not happen if create_interaction_matrix is robust
                print(f"Warning: Product ID {pid} not found in product data.")
                continue

            product = product_data.loc[pid]
            product_diet = product['diet_type']
            product_allergens = product['allergens_present']
            expiry = product['expiry_date']

            # 1. Apply dietary filters
            if violates_diet(user_diet, product_diet):
                continue

            # 2. Apply allergy filters
            if user_allergies and bool(user_allergies.intersection(product_allergens)):
                continue

            # 3. Check expiry and get discount
            days_left = days_until_expiry(expiry)
            # get_discount function already handles the 3-20 day window
            discount = get_discount(days_left, user_seen_before=pid in user_history.get(user_id, {}))

            if discount == 0 and (days_left < 3 or days_left > 20):
                continue # Product not eligible for recommendation based on expiry/discount logic

            recommended.append({
                'product_id': pid,
                'name': product['name'],
                'discount': discount,
                'days_to_expiry': days_left
            })
            already_recommended_pids.add(pid) # Mark as processed

    # Sort by discount descending, then by days_to_expiry ascending
    recommended.sort(key=lambda x: (-x['discount'], x['days_to_expiry']))
    return recommended

# ------------------- Test Example ------------------- #

if __name__ == "__main__":
    # Load and preprocess data (will create dummy if CSVs not found)
    load_and_preprocess_data()

    # Create the interaction matrix from the loaded/dummy transactions
    interaction_matrix = create_interaction_matrix()

    # Sample user history (user 1 has seen product 104 before)
    # This should ideally come from a persistent store or more robust tracking
    user_history = {
        'U0000': {104: "2025-07-05"}, # Corrected dummy user ID format
        'U0001': {101: "2025-07-01"}, # Corrected dummy user ID format
        'U0002': {107: "2025-07-04"}, # Corrected dummy user ID format
        'U0004': {112: "2025-07-03"}  # Corrected dummy user ID format
    }

    print("\n--- Running Recommendations ---")

    # Run recommendations for user 1 (non-vegetarian, no allergies)
    user_id_1 = 'U0000' # Corrected user ID format
    print(f"\nRecommendations for User {user_id_1} (Non-Vegetarian, No Allergies):")
    recs_1 = recommend_products(user_id_1, users_df, products_df, interaction_matrix, user_history)
    if recs_1:
        for rec in recs_1:
            print(f"  Recommend: {rec['name']} (ID: {rec['product_id']}) | Discount: {rec['discount']}% | Expires in {rec['days_to_expiry']} day(s)")
    else:
        print("  No recommendations found.")

    # Run recommendations for user 2 (vegetarian, nuts & gluten allergies)
    user_id_2 = 'U0001' # Corrected user ID format
    print(f"\nRecommendations for User {user_id_2} (Vegetarian, Nuts & Gluten Allergies):")
    recs_2 = recommend_products(user_id_2, users_df, products_df, interaction_matrix, user_history)
    if recs_2:
        for rec in recs_2:
            print(f"  Recommend: {rec['name']} (ID: {rec['product_id']}) | Discount: {rec['discount']}% | Expires in {rec['days_to_expiry']} day(s)")
    else:
        print("  No recommendations found.")

    # Run recommendations for user 3 (vegan, dairy & nuts allergies)
    user_id_3 = 'U0002' # Corrected user ID format
    print(f"\nRecommendations for User {user_id_3} (Vegan, Dairy & Nuts Allergies):")
    recs_3 = recommend_products(user_id_3, users_df, products_df, interaction_matrix, user_history)
    if recs_3:
        for rec in recs_3:
            print(f"  Recommend: {rec['name']} (ID: {rec['product_id']}) | Discount: {rec['discount']}% | Expires in {rec['days_to_expiry']} day(s)")
    else:
        print("  No recommendations found.")

    # Run recommendations for user 5 (vegetarian, gluten allergy)
    user_id_5 = 'U0004' # Corrected user ID format
    print(f"\nRecommendations for User {user_id_5} (Vegetarian, Gluten Allergy):")
    recs_5 = recommend_products(user_id_5, users_df, products_df, interaction_matrix, user_history)
    if recs_5:
        for rec in recs_5:
            print(f"  Recommend: {rec['name']} (ID: {rec['product_id']}) | Discount: {rec['discount']}% | Expires in {rec['days_to_expiry']} day(s)")
    else:
        print("  No recommendations found.")

    # Example: User with no expiring products or all filtered out (using a non-existent user ID)
    user_id_non_existent = 'U9999' # Corrected user ID format
    print(f"\nRecommendations for User {user_id_non_existent} (Non-existent or no suitable products):")
    recs_non_existent = recommend_products(user_id_non_existent, users_df, products_df, interaction_matrix, user_history)
    if recs_non_existent:
        for rec in recs_non_existent:
            print(f"  Recommend: {rec['name']} (ID: {rec['product_id']}) | Discount: {rec['discount']}% | Expires in {rec['days_to_expiry']} day(s)")
    else:
        print("  No recommendations found.")