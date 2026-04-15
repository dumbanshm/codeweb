import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Import the unified system
from unified_waste_reduction_system import (
    UnifiedRecommendationSystem,
    DynamicThresholdCalculator,
    calculate_dead_stock_risk_dynamic
)

def analyze_data(users_df, products_df, transactions_df):
    """Basic data analysis"""
    print("\n" + "="*50)
    print("DATA ANALYSIS")
    print("="*50)
    
    # User analysis
    print("\nUser Demographics:")
    print(f"- Total users: {len(users_df)}")
    print(f"- Diet types: {users_df['diet_type'].value_counts().to_dict()}")
    
    # Product analysis
    print("\nProduct Categories:")
    print(products_df['category'].value_counts())
    
    current_date = pd.Timestamp.now()
    products_df['days_until_expiry'] = (products_df['expiry_date'] - current_date).dt.days
    
    print(f"\nExpiry Status:")
    print(f"- Expired products: {(products_df['days_until_expiry'] <= 0).sum()}")
    print(f"- Expiring in 7 days: {((products_df['days_until_expiry'] > 0) & (products_df['days_until_expiry'] <= 7)).sum()}")
    print(f"- Expiring in 30 days: {((products_df['days_until_expiry'] > 0) & (products_df['days_until_expiry'] <= 30)).sum()}")
    
    # Transaction analysis
    print(f"\nTransaction Summary:")
    print(f"- Total transactions: {len(transactions_df)}")
    print(f"- Unique users who made purchases: {transactions_df['user_id'].nunique()}")
    print(f"- Average discount given: {transactions_df['discount_percent'].mean():.2f}%")
    print(f"- Deal engagement rate: {transactions_df['user_engaged_with_deal'].mean():.2%}")

def calculate_dead_stock_analysis(products_df, transactions_df, threshold_calculator):
    """Analyze dead stock risk using dynamic thresholds"""
    print("\n" + "="*50)
    print("DEAD STOCK RISK ANALYSIS")
    print("="*50)
    
    # Calculate sales velocity for each product
    current_date = pd.Timestamp.now()
    products_df['days_until_expiry'] = (products_df['expiry_date'] - current_date).dt.days

    # Remove already expired products
    products_df = products_df[products_df['days_until_expiry'] > 0].copy()

    sales_velocity = transactions_df.groupby('product_id').agg({
        'quantity': 'sum',
        'purchase_date': ['min', 'max']
    }).reset_index()
    
    sales_velocity.columns = ['product_id', 'total_sold', 'first_sale', 'last_sale']
    sales_velocity['days_on_market'] = (sales_velocity['last_sale'] - sales_velocity['first_sale']).dt.days + 1
    sales_velocity['sales_velocity'] = sales_velocity['total_sold'] / sales_velocity['days_on_market']
    sales_velocity['days_since_last_sale'] = (current_date - sales_velocity['last_sale']).dt.days
    
    # Merge with products, including days_since_last_sale
    products_enhanced = products_df.merge(sales_velocity[['product_id', 'sales_velocity', 'days_since_last_sale']], 
                                         on='product_id', how='left')
    products_enhanced['sales_velocity'].fillna(0, inplace=True)
    products_enhanced['days_since_last_sale'].fillna(999, inplace=True)
    
    # Calculate dead stock risk
    products_enhanced['is_dead_stock_risk'] = products_enhanced.apply(
        lambda row: calculate_dead_stock_risk_dynamic(row, threshold_calculator), axis=1
    )
    
    # Get thresholds for all products
    threshold_df = threshold_calculator.calculate_all_thresholds()
    
    # Debug: Check for expired products before analysis
    expired_debug = products_enhanced[products_enhanced['days_until_expiry'] <= 0]
    if not expired_debug.empty:
        print("[DEBUG] EXPIRED PRODUCTS FOUND IN products_enhanced BEFORE ANALYSIS:")
        print(expired_debug[['product_id', 'name', 'category', 'days_until_expiry']])
        raise ValueError("Expired products present in products_enhanced before analysis!")

    # Analysis
    # Filter out expired products from at_risk_products and products_enhanced
    at_risk_products = products_enhanced[(products_enhanced['is_dead_stock_risk'] == 1) & (products_enhanced['days_until_expiry'] > 0)]
    products_enhanced = products_enhanced[products_enhanced['days_until_expiry'] > 0].copy()

    # Debug: Check for expired products in at_risk_products
    expired_risk_debug = at_risk_products[at_risk_products['days_until_expiry'] <= 0]
    if not expired_risk_debug.empty:
        print("[DEBUG] EXPIRED PRODUCTS FOUND IN at_risk_products:")
        print(expired_risk_debug[['product_id', 'name', 'category', 'days_until_expiry']])
        raise ValueError("Expired products present in at_risk_products!")

    print(f"\nTotal products at risk: {len(at_risk_products)} ({len(at_risk_products)/len(products_enhanced)*100:.1f}%)")
    
    print("\nRisk by Category:")
    risk_by_category = at_risk_products.groupby('category').size()
    for category, count in risk_by_category.items():
        total_in_category = (products_enhanced['category'] == category).sum()
        print(f"- {category}: {count}/{total_in_category} ({count/total_in_category*100:.1f}%)")
    
    # (Moved to demonstrate_waste_reduction_strategies)
    
    return products_enhanced

def demonstrate_recommendations(system, users_df):
    """Demonstrate different types of recommendations"""
    print("\n" + "="*50)
    print("RECOMMENDATION DEMONSTRATIONS")
    print("="*50)
    
    # Select a few users for demonstration
    demo_users = users_df.sample(min(3, len(users_df)))
    
    for _, user in demo_users.iterrows():
        print(f"\n{'='*30}")
        print(f"Recommendations for User: {user['user_id']}")
        print(f"Diet: {user['diet_type']}, Allergies: {user['allergies']}")
        print(f"{'='*30}")
        
        # Hybrid recommendations
        print("\n1. HYBRID RECOMMENDATIONS (Best Overall):")
        hybrid_recs = system.get_hybrid_recommendations(
            user['user_id'], 
            n_recommendations=5,
            content_weight=0.4,
            collaborative_weight=0.6
        )
        
        if not hybrid_recs.empty:
            for idx, rec in hybrid_recs.iterrows():
                print(f"   - {rec['product_name']} ({rec['category']})")
                print(f"     Score: {rec['hybrid_score']:.3f} (Base: {rec.get('base_score', rec['hybrid_score']):.3f}), "
                      f"Urgency: {rec.get('urgency_score', 0):.2f}")
                print(f"     Days until expiry: {rec['days_until_expiry']}, "
                      f"Price: ₹{rec['price']}, Discount: {rec['discount']}%")
                if rec.get('is_dead_stock_risk', 0) == 1:
                    print(f"     ⚠️  AT RISK OF BECOMING DEAD STOCK")
        else:
            print("   No recommendations available")
        
        # Get user's purchase history
        user_products = system.transactions_df[
            system.transactions_df['user_id'] == user['user_id']
        ]['product_id'].unique()
        
        if len(user_products) > 0:
            # Content-based recommendations
            print("\n2. CONTENT-BASED RECOMMENDATIONS (Similar to your purchases):")
            last_product = user_products[-1]
            product_row = system.all_products_df[system.all_products_df['product_id'] == last_product]
            if not product_row.empty:
                product_name = product_row['name'].iloc[0]
            else:
                product_name = "Unknown Product"
            print(f"   Based on your purchase of: {product_name}")
            
            content_recs = system.get_content_based_recommendations(
                last_product,
                n_recommendations=3,
                urgency_boost=True
            )
            
            for idx, rec in content_recs.iterrows():
                print(f"   - {rec['product_name']} ({rec['category']})")
                print(f"     Similarity: {rec['similarity_score']:.3f}, Days until expiry: {rec['days_until_expiry']}")

def demonstrate_waste_reduction_strategies(products_enhanced, system):
    """Show waste reduction strategies with dynamic pricing"""
    print("\n" + "="*50)
    print("DYNAMIC WASTE REDUCTION STRATEGIES")
    print("="*50)
    
    # Debug: Check for expired products before analysis
    expired_debug = products_enhanced[products_enhanced['days_until_expiry'] <= 0]
    if not expired_debug.empty:
        print("[DEBUG] EXPIRED PRODUCTS FOUND IN products_enhanced BEFORE STRATEGY ANALYSIS:")
        print(expired_debug[['product_id', 'name', 'category', 'days_until_expiry']])
        raise ValueError("Expired products present in products_enhanced before strategy analysis!")

    # Filter out expired products before analysis
    products_enhanced_filtered = products_enhanced[products_enhanced['days_until_expiry'] > 0].copy()
    
    # Get dynamic pricing recommendations
    pricing_recommendations = system.get_dynamic_pricing_recommendations(min_urgency=0.4, limit=10)
    
    if not pricing_recommendations.empty:
        print(f"\n1. DYNAMIC PRICING RECOMMENDATIONS (Top {len(pricing_recommendations)} products):")
        print("-" * 80)
        
        for idx, rec in pricing_recommendations.iterrows():
            print(f"\n   Product: {rec['product_name']} ({rec['category']})")
            print(f"   Days until expiry: {rec['days_until_expiry']}")
            print(f"   Urgency Score: {rec['urgency_score']:.2f}")
            print(f"   Current Discount: {rec['current_discount']}%")
            print(f"   Recommended Discount: {rec['recommended_discount']}%")
            print(f"   Price Change: ₹{rec['current_price']:.2f} → ₹{rec['recommended_price']:.2f}")
            print(f"   Customer Savings: ₹{rec['potential_savings']:.2f}")
            print(f"   Reasoning: {rec['reasoning']}")
            
            if idx >= 4:  # Show only top 5
                break
    
    # Category-wise urgency analysis
    print("\n\n2. CATEGORY-WISE URGENCY ANALYSIS:")
    print("-" * 80)
    
    category_urgency = {}
    for category in products_enhanced_filtered['category'].unique():
        category_products = products_enhanced_filtered[products_enhanced_filtered['category'] == category]
        
        # Calculate average urgency for category
        urgency_scores = []
        for _, product in category_products.iterrows():
            if product['days_until_expiry'] > 0:  # Skip expired
                urgency = system.pricing_engine.calculate_dynamic_urgency_score(product)
                urgency_scores.append(urgency)
        
        if urgency_scores:
            avg_urgency = np.mean(urgency_scores)
            high_urgency_count = sum(1 for u in urgency_scores if u > 0.5)
            
            category_urgency[category] = {
                'avg_urgency': avg_urgency,
                'high_urgency_count': high_urgency_count,
                'total_products': len(category_products)
            }
    
    # Sort by average urgency
    for category, stats in sorted(category_urgency.items(), key=lambda x: x[1]['avg_urgency'], reverse=True):
        print(f"\n   {category}:")
        print(f"   - Average urgency score: {stats['avg_urgency']:.2f}")
        print(f"   - High urgency products: {stats['high_urgency_count']}/{stats['total_products']}")
        
        # Show urgency distribution
        if stats['avg_urgency'] > 0.4:
            print(f"   - Status: ⚠️  NEEDS ATTENTION")
    
    # Products needing immediate action
    urgent_products = products_enhanced_filtered[
        (products_enhanced_filtered['days_until_expiry'] > 0) & 
        (products_enhanced_filtered['days_until_expiry'] <= 7) &
        (products_enhanced_filtered['is_dead_stock_risk'] == 1)
    ].sort_values('days_until_expiry')
    
    print(f"\n\n3. URGENT ACTION REQUIRED ({len(urgent_products)} products):")
    for idx, product in urgent_products.head(5).iterrows():
        threshold = system.threshold_calculator.get_threshold(product['product_id'])
        suggested_discount = min(50, product['current_discount_percent'] + 20)
        print(f"\n   Product: {product['name']}")
        print(f"   - Days until expiry: {product['days_until_expiry']}")
        print(f"   - Current discount: {product['current_discount_percent']}%")
        print(f"   - Suggested discount: {suggested_discount}%")
        print(f"   - Dynamic threshold: {threshold} days")

    # Print Top 10 Products at Risk (with lowest days until expiry) with updated discounts
    at_risk_products = products_enhanced_filtered[(products_enhanced_filtered['is_dead_stock_risk'] == 1) & (products_enhanced_filtered['days_until_expiry'] > 0)]
    print("\n\n4. TOP 10 PRODUCTS AT RISK (with lowest days until expiry):")
    top_risk = at_risk_products.nsmallest(10, 'days_until_expiry')[
        ['product_id', 'name', 'category', 'days_until_expiry', 'current_discount_percent']
    ]
    for idx, row in top_risk.iterrows():
        threshold = system.threshold_calculator.get_threshold(row['product_id'])
        print(f"- {row['name']} ({row['category']}): {row['days_until_expiry']} days left, "
              f"threshold: {threshold} days, current discount: {row['current_discount_percent']}%")

def test_all_users_recommendations(system, users_df, n_recommendations=5):
    """Test recommendation system for all users to find corner cases and debug issues"""
    print("\n" + "="*50)
    print("COMPREHENSIVE RECOMMENDATION TESTING")
    print("="*50)
    
    # Track different types of issues
    issues = {
        'no_recommendations': [],
        'errors': [],
        'no_purchase_history': [],
        'all_expired': [],
        'insufficient_recommendations': [],
        'diet_allergy_conflicts': []
    }
    
    success_count = 0
    total_users = len(users_df)
    
    print(f"\nTesting recommendations for all {total_users} users...")
    print("-" * 50)
    
    for idx, (_, user) in enumerate(users_df.iterrows()):
        user_id = user['user_id']
        
        try:
            # Check if user has purchase history
            user_purchases = system.transactions_df[
                system.transactions_df['user_id'] == user_id
            ]
            
            if len(user_purchases) == 0:
                issues['no_purchase_history'].append({
                    'user_id': user_id,
                    'diet': user['diet_type'],
                    'allergies': user['allergies']
                })
            
            # Get recommendations
            recommendations = system.get_hybrid_recommendations(
                user_id, 
                n_recommendations=n_recommendations
            )
            
            # Check various edge cases
            if recommendations.empty:
                issues['no_recommendations'].append({
                    'user_id': user_id,
                    'diet': user['diet_type'],
                    'allergies': user['allergies'],
                    'purchase_count': len(user_purchases)
                })
            elif len(recommendations) < n_recommendations:
                issues['insufficient_recommendations'].append({
                    'user_id': user_id,
                    'requested': n_recommendations,
                    'received': len(recommendations),
                    'diet': user['diet_type'],
                    'allergies': user['allergies']
                })
            else:
                # Check if all recommended products are close to expiry
                avg_days_to_expiry = recommendations['days_until_expiry'].mean()
                if avg_days_to_expiry < 7:
                    issues['all_expired'].append({
                        'user_id': user_id,
                        'avg_days_to_expiry': avg_days_to_expiry,
                        'products': recommendations[['product_name', 'days_until_expiry']].to_dict('records')
                    })
                
                success_count += 1
            
            # Progress indicator
            if (idx + 1) % 50 == 0:
                print(f"Processed {idx + 1}/{total_users} users...")
                
        except Exception as e:
            issues['errors'].append({
                'user_id': user_id,
                'error': str(e),
                'error_type': type(e).__name__
            })
    
    # Print comprehensive report
    print("\n" + "="*50)
    print("TESTING RESULTS SUMMARY")
    print("="*50)
    
    print(f"\nOverall Statistics:")
    print(f"- Total users tested: {total_users}")
    print(f"- Successful recommendations: {success_count} ({success_count/total_users*100:.1f}%)")
    print(f"- Users with issues: {total_users - success_count} ({(total_users - success_count)/total_users*100:.1f}%)")
    
    # Detailed issue breakdown
    print("\nIssue Breakdown:")
    
    if issues['no_purchase_history']:
        print(f"\n1. Users with NO PURCHASE HISTORY: {len(issues['no_purchase_history'])}")
        diet_breakdown = pd.DataFrame(issues['no_purchase_history'])['diet'].value_counts()
        print("   Diet type distribution:")
        for diet, count in diet_breakdown.items():
            print(f"   - {diet}: {count}")
    
    if issues['no_recommendations']:
        print(f"\n2. Users with NO RECOMMENDATIONS: {len(issues['no_recommendations'])}")
        for case in issues['no_recommendations'][:3]:
            print(f"   - User {case['user_id']}: {case['diet']} diet, allergies: {case['allergies']}")
    
    if issues['insufficient_recommendations']:
        print(f"\n3. Users with INSUFFICIENT RECOMMENDATIONS: {len(issues['insufficient_recommendations'])}")
        for case in issues['insufficient_recommendations'][:3]:
            print(f"   - User {case['user_id']}: Got {case['received']}/{case['requested']} recommendations")
    
    if issues['all_expired']:
        print(f"\n4. Users getting mostly EXPIRED/EXPIRING products: {len(issues['all_expired'])}")
        for case in issues['all_expired'][:2]:
            print(f"   - User {case['user_id']}: Avg days to expiry = {case['avg_days_to_expiry']:.1f}")
    
    if issues['errors']:
        print(f"\n5. ERRORS encountered: {len(issues['errors'])}")
        error_types = pd.DataFrame(issues['errors'])['error_type'].value_counts()
        for error_type, count in error_types.items():
            print(f"   - {error_type}: {count} occurrences")
    
    # Test specific corner cases
    print("\n" + "="*50)
    print("SPECIFIC CORNER CASE TESTING")
    print("="*50)
    
    # Test 1: User with strict allergies
    print("\n1. Testing user with multiple allergies:")
    strict_allergy_users = users_df[
        users_df['allergies'].apply(lambda x: len(str(x).split(',')) > 2 if pd.notna(x) else False)
    ]
    if not strict_allergy_users.empty:
        test_user = strict_allergy_users.iloc[0]
        print(f"   User {test_user['user_id']}: Allergies = {test_user['allergies']}")
        try:
            recs = system.get_hybrid_recommendations(test_user['user_id'], n_recommendations=10)
            print(f"   - Got {len(recs)} recommendations")
            if not recs.empty:
                print(f"   - Categories: {recs['category'].value_counts().to_dict()}")
        except Exception as e:
            print(f"   - ERROR: {e}")
    
    # Test 2: Vegan users
    print("\n2. Testing vegan users:")
    vegan_users = users_df[users_df['diet_type'] == 'vegan']
    if not vegan_users.empty:
        vegan_success = 0
        for _, vegan in vegan_users.iterrows():
            try:
                recs = system.get_hybrid_recommendations(vegan['user_id'], n_recommendations=5)
                if not recs.empty:
                    vegan_success += 1
            except:
                pass
        print(f"   - {vegan_success}/{len(vegan_users)} vegan users got recommendations")
    
    # Test 3: Products with high dead stock risk
    print("\n3. Dead stock recommendation distribution:")
    dead_stock_count = 0
    total_recs = 0
    
    sample_users = users_df.sample(min(20, len(users_df)))
    for _, user in sample_users.iterrows():
        try:
            recs = system.get_hybrid_recommendations(user['user_id'], n_recommendations=5)
            if not recs.empty:
                dead_stock_count += recs['is_dead_stock_risk'].sum()
                total_recs += len(recs)
        except:
            pass
    
    if total_recs > 0:
        print(f"   - {dead_stock_count}/{total_recs} ({dead_stock_count/total_recs*100:.1f}%) recommendations are dead stock risk items")
    
    return issues

def run_system(users_df, products_df, transactions_df):
    """Main function to run the unified waste reduction system"""
    print("="*50)
    print("UNIFIED WASTE REDUCTION SYSTEM")
    print("="*50)
    
    # Basic data analysis
    analyze_data(users_df, products_df, transactions_df)
    
    # Initialize the unified recommendation system
    print("\nInitializing Unified Recommendation System...")
    system = UnifiedRecommendationSystem(users_df, products_df, transactions_df)
    
    # Build models
    print("Building content similarity matrix...")
    system.build_content_similarity_matrix()
    
    print("Building collaborative filtering model...")
    system.build_collaborative_filtering_model(n_factors=50)
    
    # Dead stock analysis
    products_enhanced = calculate_dead_stock_analysis(
        products_df, transactions_df, system.threshold_calculator
    )
    
    # Update products_df in system with enhanced data
    system.products_df = products_enhanced
    
    # Update discounts for at-risk products AFTER dead stock analysis
    system.update_discounts_for_at_risk_products()
    
    # Rebuild content similarity matrix with updated discounts
    system.build_content_similarity_matrix()
    
    # Build product risk DataFrame for fast API/export
    system.build_product_risk_df()
    
    # Demonstrate recommendations
    demonstrate_recommendations(system, users_df)
    
    # Show waste reduction strategies with dynamic pricing and updated discounts
    demonstrate_waste_reduction_strategies(products_enhanced, system)
    
    # Test all users' recommendations
    issues = test_all_users_recommendations(system, users_df)
    
    print("\n" + "="*50)
    print("SYSTEM READY FOR USE")
    print("="*50)
    print("\nThe unified waste reduction system is now initialized and ready.")
    print("You can use the 'system' object to generate recommendations for any user.")
    print("\nExample usage:")
    print("  recommendations = system.get_hybrid_recommendations('U0001', n_recommendations=10)")
    
    
    return system, products_enhanced

# Example usage when data is already loaded
if __name__ == "__main__":
    print("Loading data files...")
    
    try:
        # Load the data from CSV files
        users_df = pd.read_csv('datasets/fake_users.csv')
        products_df = pd.read_csv('datasets/fake_products.csv')
        transactions_df = pd.read_csv('datasets/fake_transactions.csv')
        
        # Convert date columns to datetime
        products_df['expiry_date'] = pd.to_datetime(products_df['expiry_date'])
        transactions_df['purchase_date'] = pd.to_datetime(transactions_df['purchase_date'])
        
        print("Data loaded successfully!")
        print(f"- Users: {len(users_df)} records")
        print(f"- Products: {len(products_df)} records")
        print(f"- Transactions: {len(transactions_df)} records")
        
        # Run the system
        system, products_enhanced = run_system(users_df, products_df, transactions_df)

        # Try to pickle the model and provide clear feedback
        import pickle
        import os
        try:
            with open('model.pkl', 'wb') as f:
                pickle.dump(system, f)
            print("Model pickled and saved as model.pkl in:", os.getcwd())
        except Exception as e:
            print("Failed to pickle model:", e)
            import traceback
            traceback.print_exc()
        with open('products_enhanced.pkl', 'wb') as f:
            pickle.dump(products_enhanced, f)
            print("Products enhanced pickled and saved as products_enhanced.pkl")
        
    except FileNotFoundError as e:
        print(f"Error: Could not find data files. {e}")
        print("Please ensure the following files exist:")
        print("- datasets/fake_users.csv")
        print("- datasets/fake_products.csv")
        print("- datasets/fake_transactions.csv")
    except Exception as e:
        print(f"Error loading or processing data: {e}")
        import traceback
        traceback.print_exc() 