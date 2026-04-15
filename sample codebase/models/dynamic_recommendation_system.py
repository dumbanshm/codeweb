import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD
from scipy.sparse import csr_matrix
from sklearn.preprocessing import StandardScaler, LabelEncoder
import warnings
warnings.filterwarnings('ignore')


class DynamicRecommendationSystem:
    """
    Advanced recommendation system combining content-based and collaborative filtering
    """
    
    def __init__(self, users_df, products_df, transactions_df):
        self.users_df = users_df
        self.products_df = products_df
        self.transactions_df = transactions_df
        
        # Preprocessing
        self.le_diet = LabelEncoder()
        self.le_category = LabelEncoder()
        
        # Models
        self.content_similarity_matrix = None
        self.user_item_matrix = None
        self.user_factors = None
        self.item_factors = None
        self.product_features = None
        
    def prepare_content_features(self):
        """
        Create rich product features for content-based filtering
        """
        products = self.products_df.copy()
        
        # Create text features by combining multiple attributes
        products['content_text'] = (
            products['name'] + ' ' +
            products['category'] + ' ' +
            products['diet_type'] + ' ' +
            products['brand'] + ' ' +
            'price_' + pd.cut(products['price_mrp'], bins=5, labels=['very_low', 'low', 'medium', 'high', 'very_high']).astype(str) + ' ' +
            'discount_' + pd.cut(products['current_discount_percent'], bins=[-1, 0, 20, 40, 100], labels=['none', 'low', 'medium', 'high']).astype(str)
        )
        
        # Add allergen information
        products['allergen_text'] = products['allergens'].apply(
            lambda x: ' '.join(eval(x)) if isinstance(x, str) and x != '[]' else ''
        )
        products['content_text'] += ' ' + products['allergen_text']
        
        # Numerical features
        numerical_features = ['price_mrp', 'weight_grams', 'shelf_life_days', 
                            'current_discount_percent', 'days_until_expiry']
        
        # Encode categorical features
        products['diet_encoded'] = self.le_diet.fit_transform(products['diet_type'])
        products['category_encoded'] = self.le_category.fit_transform(products['category'])
        
        # Create feature matrix
        self.product_features = products
        
        return products
    
    def build_content_similarity_matrix(self):
        """
        Build product similarity matrix using content features
        """
        products = self.prepare_content_features()
        
        # TF-IDF for text features
        tfidf = TfidfVectorizer(max_features=100, stop_words='english')
        tfidf_matrix = tfidf.fit_transform(products['content_text'])
        
        # Numerical features
        numerical_features = ['price_mrp', 'weight_grams', 'shelf_life_days', 
                            'current_discount_percent', 'diet_encoded', 'category_encoded']
        
        scaler = StandardScaler()
        numerical_matrix = scaler.fit_transform(products[numerical_features].fillna(0))
        
        # Combine features (weighted)
        # Give more weight to text features for product similarity
        combined_features = np.hstack([
            tfidf_matrix.toarray() * 0.6,  # Text features
            numerical_matrix * 0.4          # Numerical features
        ])
        
        # Calculate similarity
        self.content_similarity_matrix = cosine_similarity(combined_features)
        
        return self.content_similarity_matrix
    
    def build_collaborative_filtering_model(self, n_factors=50):
        """
        Build collaborative filtering model using matrix factorization (SVD)
        """
        # Create user-item interaction matrix
        pivot_table = self.transactions_df.pivot_table(
            index='user_id',
            columns='product_id',
            values='quantity',
            aggfunc='sum',
            fill_value=0
        )
        
        # Add implicit feedback from engagement
        engagement_pivot = self.transactions_df.pivot_table(
            index='user_id',
            columns='product_id',
            values='user_engaged_with_deal',
            aggfunc='mean',
            fill_value=0
        )
        
        # Combine explicit (purchases) and implicit (engagement) feedback
        self.user_item_matrix = pivot_table + 0.5 * engagement_pivot
        
        # Convert to sparse matrix for efficiency
        sparse_matrix = csr_matrix(self.user_item_matrix.values)
        
        # Apply SVD for matrix factorization
        svd = TruncatedSVD(n_components=n_factors, random_state=42)
        self.user_factors = svd.fit_transform(sparse_matrix)
        self.item_factors = svd.components_.T
        
        return self.user_factors, self.item_factors
    
    def get_content_based_recommendations(self, product_id, n_recommendations=10, 
                                        filter_expired=True, urgency_boost=True):
        """
        Get recommendations based on product similarity
        """
        if self.content_similarity_matrix is None:
            self.build_content_similarity_matrix()
        
        # Get product index
        product_idx = self.products_df[self.products_df['product_id'] == product_id].index[0]
        
        # Get similarity scores
        sim_scores = list(enumerate(self.content_similarity_matrix[product_idx]))
        sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
        
        # Get top similar products (excluding the product itself)
        similar_products = []
        for idx, score in sim_scores[1:]:  # Skip first item (itself)
            product = self.products_df.iloc[idx]
            
            # Filter expired products
            if filter_expired and product['days_until_expiry'] <= 0:
                continue
                
            recommendation = {
                'product_id': product['product_id'],
                'product_name': product['name'],
                'similarity_score': score,
                'days_until_expiry': product['days_until_expiry'],
                'category': product['category'],
                'price': product['price_mrp'],
                'discount': product['current_discount_percent']
            }
            
            # Apply urgency boost for expiring products
            if urgency_boost and product['days_until_expiry'] <= 30:
                urgency_factor = 1 + (30 - product['days_until_expiry']) / 30 * 0.5
                recommendation['final_score'] = score * urgency_factor
            else:
                recommendation['final_score'] = score
                
            similar_products.append(recommendation)
            
            if len(similar_products) >= n_recommendations:
                break
        
        return pd.DataFrame(similar_products).sort_values('final_score', ascending=False)
    
    def get_collaborative_recommendations(self, user_id, n_recommendations=10, 
                                        filter_purchased=True, focus_on_expiring=True):
        """
        Get recommendations using collaborative filtering
        """
        if self.user_factors is None:
            self.build_collaborative_filtering_model()
        
        # Get user index
        if user_id not in self.user_item_matrix.index:
            # Cold start problem - return popular expiring items
            return self.get_popular_expiring_products(n_recommendations)
        
        user_idx = self.user_item_matrix.index.get_loc(user_id)
        
        # Calculate predicted ratings for all items
        user_vector = self.user_factors[user_idx]
        predicted_ratings = np.dot(user_vector, self.item_factors.T)
        
        # Get product IDs
        product_ids = self.user_item_matrix.columns
        
        # Create recommendations
        recommendations = []
        for idx, rating in enumerate(predicted_ratings):
            product_id = product_ids[idx]
            
            # Filter already purchased items
            if filter_purchased and self.user_item_matrix.iloc[user_idx, idx] > 0:
                continue
            
            product = self.products_df[self.products_df['product_id'] == product_id].iloc[0]
            
            # Filter expired products
            if product['days_until_expiry'] <= 0:
                continue
            
            # Check dietary compatibility
            user = self.users_df[self.users_df['user_id'] == user_id].iloc[0]
            if not self.is_compatible(user, product):
                continue
            
            recommendation = {
                'product_id': product_id,
                'product_name': product['name'],
                'predicted_rating': rating,
                'days_until_expiry': product['days_until_expiry'],
                'category': product['category'],
                'price': product['price_mrp'],
                'discount': product['current_discount_percent']
            }
            
            # Boost score for expiring products
            if focus_on_expiring and product['days_until_expiry'] <= 30:
                urgency_factor = 1 + (30 - product['days_until_expiry']) / 30 * 0.5
                recommendation['final_score'] = rating * urgency_factor
            else:
                recommendation['final_score'] = rating
            
            recommendations.append(recommendation)
        
        # Sort and return top N
        recommendations_df = pd.DataFrame(recommendations)
        return recommendations_df.nlargest(n_recommendations, 'final_score')
    
    def get_hybrid_recommendations(self, user_id, n_recommendations=10, 
                                 content_weight=0.4, collaborative_weight=0.6):
        """
        Combine content-based and collaborative filtering
        """
        # Get user's purchase history
        user_products = self.transactions_df[
            self.transactions_df['user_id'] == user_id
        ]['product_id'].unique()
        
        if len(user_products) == 0:
            # New user - use popular expiring products
            return self.get_popular_expiring_products(n_recommendations)
        
        # Get collaborative recommendations
        collab_recs = self.get_collaborative_recommendations(
            user_id, n_recommendations * 2
        )
        
        # Get content-based recommendations from user's recent purchases
        content_recs_list = []
        for product_id in user_products[-3:]:  # Last 3 purchases
            content_recs = self.get_content_based_recommendations(
                product_id, n_recommendations
            )
            content_recs_list.append(content_recs)
        
        if content_recs_list:
            content_recs_combined = pd.concat(content_recs_list).groupby('product_id').agg({
                'final_score': 'mean',
                'product_name': 'first',
                'days_until_expiry': 'first',
                'category': 'first',
                'price': 'first',
                'discount': 'first'
            }).reset_index()
        else:
            content_recs_combined = pd.DataFrame()
        
        # Combine scores
        all_products = set()
        if not collab_recs.empty:
            all_products.update(collab_recs['product_id'].tolist())
        if not content_recs_combined.empty:
            all_products.update(content_recs_combined['product_id'].tolist())
        
        hybrid_scores = []
        for product_id in all_products:
            score = 0
            
            # Collaborative score
            if not collab_recs.empty and product_id in collab_recs['product_id'].values:
                collab_score = collab_recs[
                    collab_recs['product_id'] == product_id
                ]['final_score'].iloc[0]
                score += collaborative_weight * collab_score
            
            # Content score
            if not content_recs_combined.empty and product_id in content_recs_combined['product_id'].values:
                content_score = content_recs_combined[
                    content_recs_combined['product_id'] == product_id
                ]['final_score'].iloc[0]
                score += content_weight * content_score
            
            # Get product details
            product = self.products_df[self.products_df['product_id'] == product_id].iloc[0]
            
            hybrid_scores.append({
                'product_id': product_id,
                'product_name': product['name'],
                'hybrid_score': score,
                'days_until_expiry': product['days_until_expiry'],
                'category': product['category'],
                'price': product['price_mrp'],
                'discount': product['current_discount_percent'],
                'is_dead_stock_risk': product.get('is_dead_stock_risk', 0)
            })
        
        # Return top N
        hybrid_df = pd.DataFrame(hybrid_scores)
        return hybrid_df.nlargest(n_recommendations, 'hybrid_score')
    
    def get_popular_expiring_products(self, n_recommendations=10):
        """
        Fallback for cold start - return popular products that are expiring soon
        """
        # Get products expiring within 30 days
        expiring_products = self.products_df[
            (self.products_df['days_until_expiry'] > 0) & 
            (self.products_df['days_until_expiry'] <= 30)
        ].copy()
        
        # Calculate popularity from transactions
        product_popularity = self.transactions_df.groupby('product_id').agg({
            'quantity': 'sum',
            'user_id': 'nunique'
        }).rename(columns={'user_id': 'unique_buyers'})
        
        # Merge with expiring products
        expiring_products = expiring_products.merge(
            product_popularity, 
            left_on='product_id', 
            right_index=True, 
            how='left'
        )
        
        # Calculate urgency score
        expiring_products['urgency_score'] = (
            30 - expiring_products['days_until_expiry']
        ) / 30
        
        # Combined score
        expiring_products['recommendation_score'] = (
            expiring_products['quantity'].fillna(0) * 0.4 +
            expiring_products['unique_buyers'].fillna(0) * 0.3 +
            expiring_products['urgency_score'] * 0.3
        )
        
        # Return top N
        return expiring_products.nlargest(n_recommendations, 'recommendation_score')[[
            'product_id', 'name', 'category', 'days_until_expiry', 
            'price_mrp', 'current_discount_percent', 'recommendation_score'
        ]].rename(columns={'name': 'product_name'})
    
    def is_compatible(self, user, product):
        """
        Check if product is compatible with user's dietary restrictions
        """
        # Diet compatibility
        diet_hierarchy = {
            "non-vegetarian": 3,
            "eggs": 2,
            "vegetarian": 1,
            "vegan": 0
        }
        
        if diet_hierarchy.get(product['diet_type'], 0) > diet_hierarchy.get(user['diet_type'], 3):
            return False
        
        # Allergen check
        user_allergies = eval(user['allergies']) if isinstance(user['allergies'], str) else user['allergies']
        product_allergens = eval(product['allergens']) if isinstance(product['allergens'], str) else product['allergens']
        
        if any(allergen in product_allergens for allergen in user_allergies):
            return False
        
        return True
    
    def update_model_with_feedback(self, user_id, product_id, feedback_type='purchase', rating=None):
        """
        Update the model with new user feedback
        """
        # Add to transactions for retraining
        new_transaction = {
            'user_id': user_id,
            'product_id': product_id,
            'purchase_date': pd.Timestamp.now(),
            'quantity': 1 if feedback_type == 'purchase' else 0,
            'user_engaged_with_deal': 1 if feedback_type in ['click', 'view'] else 0
        }
        
        if rating:
            new_transaction['rating'] = rating
        
        # In production, this would update the database
        # Here we just show the concept
        self.transactions_df = pd.concat([
            self.transactions_df,
            pd.DataFrame([new_transaction])
        ], ignore_index=True)
        
        # Retrain models periodically (in production, this would be scheduled)
        if len(self.transactions_df) % 100 == 0:
            self.build_collaborative_filtering_model()
            self.build_content_similarity_matrix()


# Example usage
if __name__ == "__main__":
    print("Dynamic Recommendation System Examples")
    print("="*50)
    
    print("\n1. Content-Based Filtering:")
    print("   - Finds products similar to what user likes")
    print("   - Uses product features: category, price, ingredients, etc.")
    print("   - Works well for new products with no purchase history")
    
    print("\n2. Collaborative Filtering:")
    print("   - Learns from collective user behavior")
    print("   - Finds patterns: 'users who bought X also bought Y'")
    print("   - Discovers non-obvious connections")
    
    print("\n3. Hybrid Approach:")
    print("   - Combines both methods for best results")
    print("   - Handles cold start problem")
    print("   - Adapts to user preferences over time")
    
    print("\n4. Key Improvements:")
    print("   - Learns automatically from data")
    print("   - Discovers hidden patterns")
    print("   - Personalizes for each user")
    print("   - Updates with new feedback")
    print("   - Prioritizes expiring products intelligently") 