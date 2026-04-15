import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import pandas as pd
import logging
from datetime import datetime, timedelta
from supabase import create_client, Client
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://bwysarrweyooqtjkowzp.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ3eXNhcnJ3ZXlvb3F0amtvd3pwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIzNTIzODEsImV4cCI6MjA2NzkyODM4MX0.cfOrT6MXZ9XHAjYC0K1rri1C4-jGmBbE9q0RQLpR3d8")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Connected to Supabase successfully")
except Exception as e:
    logger.error(f"Failed to connect to Supabase: {e}")
    supabase = None

app = FastAPI(
    title="Unified Waste Reduction API (Supabase)",
    description="API for waste reduction recommendations using Supabase backend",
    version="2.0.0"
)

# Enhanced CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Pydantic models for responses
class Recommendation(BaseModel):
    product_id: str
    product_name: str
    name: str
    category: str
    days_until_expiry: int
    price: float
    price_mrp: float
    discount: float
    current_discount_percent: float
    expiry_date: Optional[str] = None
    score: Optional[float] = None
    is_dead_stock_risk: Optional[int] = None

class RecommendationsResponse(BaseModel):
    user_id: str
    recommendations: List[Recommendation]

class DeadStockRiskItem(BaseModel):
    product_id: str
    name: str
    category: str
    days_until_expiry: int
    current_discount_percent: float
    price_mrp: float
    expiry_date: Optional[str] = None
    risk_score: Optional[float] = None
    threshold: Optional[int] = None

class ApiResponse(BaseModel):
    message: str
    status: str = "success"

class SupabaseRecommendationSystem:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self._content_similarity_matrix = None
        self._product_features = None
        
    def calculate_days_until_expiry(self, expiry_date_str: str) -> int:
        """Calculate days until product expires"""
        try:
            expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
            today = datetime.now().date()
            return (expiry_date - today).days
        except:
            return 0
    
    def is_dead_stock_risk(self, product: dict) -> int:
        """Determine if product is at risk of becoming dead stock"""
        days_until_expiry = product.get('days_until_expiry', 0)
        sales_velocity = product.get('sales_velocity', 0)
        
        # If already expired
        if days_until_expiry <= 0:
            return 1
        
        # If no sales history and less than 30 days to expiry
        if sales_velocity == 0 and days_until_expiry < 30:
            return 1
        
        # If sales velocity suggests won't sell out before expiry
        if sales_velocity > 0:
            projected_sales = sales_velocity * days_until_expiry
            # Assuming average inventory of 100 units per product
            if projected_sales < 80 and days_until_expiry < 30:
                return 1
        
        return 0
    
    def is_diet_compatible(self, user_diet: str, product_diet: str) -> bool:
        """Check if product is compatible with user's diet"""
        diet_hierarchy = {
            "non-vegetarian": 3,
            "eggs": 2,
            "vegetarian": 1,
            "vegan": 0
        }
        
        user_level = diet_hierarchy.get(user_diet, 3)
        product_level = diet_hierarchy.get(product_diet, 3)
        
        return product_level <= user_level
    
    def is_allergen_safe(self, user_allergies: list, product_allergens: list) -> bool:
        """Check if product is safe for user's allergies"""
        if not user_allergies or not product_allergens:
            return True
        
        # Check if any user allergy is in product allergens
        return not any(allergen in product_allergens for allergen in user_allergies)
    
    def build_content_similarity_matrix(self, products_df: pd.DataFrame):
        """Build content-based similarity matrix for products"""
        # Create feature text for each product
        products_df['feature_text'] = (
            products_df['name'] + ' ' +
            products_df['category'] + ' ' +
            products_df['brand'] + ' ' +
            products_df['diet_type']
        )
        
        # Create TF-IDF matrix
        tfidf = TfidfVectorizer(stop_words='english')
        tfidf_matrix = tfidf.fit_transform(products_df['feature_text'])
        
        # Calculate cosine similarity
        self._content_similarity_matrix = cosine_similarity(tfidf_matrix, tfidf_matrix)
        self._product_features = products_df
        
        return self._content_similarity_matrix
    
    def get_content_based_recommendations(self, product_id: str, n_recommendations: int = 10) -> pd.DataFrame:
        """Get content-based recommendations for a product"""
        if self._content_similarity_matrix is None:
            # Fetch all products and build similarity matrix
            products_response = self.supabase.table('products').select("*").execute()
            products_df = pd.DataFrame(products_response.data)
            
            # Calculate days until expiry
            products_df['days_until_expiry'] = products_df['expiry_date'].apply(self.calculate_days_until_expiry)
            
            self.build_content_similarity_matrix(products_df)
        
        # Find product index
        product_idx = self._product_features[self._product_features['product_id'] == product_id].index
        if len(product_idx) == 0:
            return pd.DataFrame()
        
        product_idx = product_idx[0]
        
        # Get similarity scores
        sim_scores = list(enumerate(self._content_similarity_matrix[product_idx]))
        sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
        
        # Get similar products (skip the first one as it's the same product)
        recommendations = []
        for idx, score in sim_scores[1:]:
            if len(recommendations) >= n_recommendations:
                break
                
            product = self._product_features.iloc[idx]
            
            # Skip expired products
            if product['days_until_expiry'] <= 0:
                continue
            
            recommendations.append({
                'product_id': product['product_id'],
                'product_name': product['name'],
                'category': product['category'],
                'days_until_expiry': product['days_until_expiry'],
                'price': product['price_mrp'],
                'discount': product['current_discount_percent'],
                'similarity_score': score,
                'is_dead_stock_risk': self.is_dead_stock_risk(product)
            })
        
        return pd.DataFrame(recommendations)
    
    def get_hybrid_recommendations(self, user_id: str, n_recommendations: int = 10) -> pd.DataFrame:
        """Get hybrid recommendations for a user"""
        try:
            # Fetch user data
            user_response = self.supabase.table('users').select("*").eq('user_id', user_id).execute()
            if not user_response.data:
                logger.warning(f"User {user_id} not found")
                return pd.DataFrame()
            
            user = user_response.data[0]
            
            # Fetch all products
            products_response = self.supabase.table('products').select("*").execute()
            products_df = pd.DataFrame(products_response.data)
            
            # Calculate days until expiry
            products_df['days_until_expiry'] = products_df['expiry_date'].apply(self.calculate_days_until_expiry)
            
            # Filter out expired products
            products_df = products_df[products_df['days_until_expiry'] > 0]
            
            # Get transactions to calculate sales velocity
            transactions_response = self.supabase.table('transactions').select("*").execute()
            if transactions_response.data:
                transactions_df = pd.DataFrame(transactions_response.data)
                
                # Calculate sales velocity
                sales_metrics = transactions_df.groupby('product_id').agg({
                    'quantity': ['sum', 'mean', 'count'],
                    'purchase_date': ['min', 'max']
                }).reset_index()
                
                sales_metrics.columns = ['product_id', 'total_quantity_sold', 'avg_quantity_per_sale',
                                        'number_of_sales', 'first_sale_date', 'last_sale_date']
                
                sales_metrics['days_on_market'] = (
                    pd.to_datetime(sales_metrics['last_sale_date']) - 
                    pd.to_datetime(sales_metrics['first_sale_date'])
                ).dt.days + 1
                sales_metrics['sales_velocity'] = sales_metrics['total_quantity_sold'] / sales_metrics['days_on_market']
                
                # Merge with products
                products_df = products_df.merge(
                    sales_metrics[['product_id', 'sales_velocity', 'total_quantity_sold']], 
                    on='product_id', how='left'
                )
                products_df['sales_velocity'] = products_df['sales_velocity'].fillna(0)
                products_df['total_quantity_sold'] = products_df['total_quantity_sold'].fillna(0)
            else:
                products_df['sales_velocity'] = 0
                products_df['total_quantity_sold'] = 0
            
            # Apply dietary restrictions
            compatible_products = []
            for _, product in products_df.iterrows():
                if self.is_diet_compatible(user['diet_type'], product['diet_type']):
                    if self.is_allergen_safe(user.get('allergies', []), product.get('allergens', [])):
                        compatible_products.append(product)
            
            if not compatible_products:
                logger.warning(f"No compatible products found for user {user_id}")
                return pd.DataFrame()
            
            compatible_df = pd.DataFrame(compatible_products)
            
            # Score products based on multiple factors
            recommendations = []
            for _, product in compatible_df.iterrows():
                # Base score
                score = 1.0
                
                # Urgency factor (products expiring soon get higher scores)
                if product['days_until_expiry'] <= 30:
                    urgency_score = (30 - product['days_until_expiry']) / 30
                    score += urgency_score * 2
                
                # Discount preference
                if user.get('prefers_discount', False) and product['current_discount_percent'] > 0:
                    score += product['current_discount_percent'] / 100
                
                # Category preference
                if product['category'] in user.get('preferred_categories', []):
                    score += 0.5
                
                # Dead stock boost
                if self.is_dead_stock_risk(product):
                    score += 1.5
                
                recommendations.append({
                    'product_id': product['product_id'],
                    'product_name': product['name'],
                    'category': product['category'],
                    'days_until_expiry': product['days_until_expiry'],
                    'price': product['price_mrp'],
                    'discount': product['current_discount_percent'],
                    'hybrid_score': score,
                    'is_dead_stock_risk': self.is_dead_stock_risk(product)
                })
            
            # Sort by score and return top N
            recommendations_df = pd.DataFrame(recommendations)
            return recommendations_df.nlargest(n_recommendations, 'hybrid_score')
            
        except Exception as e:
            logger.error(f"Error generating recommendations for user {user_id}: {e}")
            return pd.DataFrame()

# Initialize recommendation system
recommender = SupabaseRecommendationSystem(supabase) if supabase else None

@app.get("/", response_model=ApiResponse)
def root():
    return ApiResponse(
        message="Unified Waste Reduction System API (Supabase) is running.",
        status="success"
    )

@app.get("/health")
def health_check():
    """Health check endpoint"""
    db_status = "connected" if supabase is not None else "disconnected"
    return {
        "status": "healthy",
        "database_status": db_status,
        "api_version": "2.0.0"
    }

@app.get("/recommendations/{user_id}", response_model=RecommendationsResponse)
def get_recommendations(user_id: str, n: int = Query(10, ge=1, le=50)):
    """Get personalized recommendations for a user"""
    if not recommender:
        raise HTTPException(status_code=500, detail="Recommendation system not available.")
    
    try:
        logger.info(f"Generating recommendations for user: {user_id}")
        recs = recommender.get_hybrid_recommendations(user_id, n_recommendations=n)
        
        if recs.empty:
            logger.warning(f"No recommendations found for user: {user_id}")
            return RecommendationsResponse(user_id=user_id, recommendations=[])
        
        # Convert DataFrame to list of Recommendation
        recommendations = []
        for _, row in recs.iterrows():
            recommendation = Recommendation(
                product_id=str(row.get("product_id", "")),
                product_name=str(row.get("product_name", "")),
                name=str(row.get("product_name", "")),
                category=str(row.get("category", "")),
                days_until_expiry=int(row.get("days_until_expiry", 0)),
                price=float(row.get("price", 0)),
                price_mrp=float(row.get("price", 0)),
                discount=float(row.get("discount", 0)),
                current_discount_percent=float(row.get("discount", 0)),
                expiry_date="",
                score=float(row.get("hybrid_score", 0)),
                is_dead_stock_risk=int(row.get("is_dead_stock_risk", 0)),
            )
            recommendations.append(recommendation)
        
        logger.info(f"Successfully generated {len(recommendations)} recommendations for user: {user_id}")
        return RecommendationsResponse(user_id=user_id, recommendations=recommendations)
        
    except Exception as e:
        logger.error(f"Error generating recommendations for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating recommendations: {str(e)}")

@app.get("/dead_stock_risk", response_model=List[DeadStockRiskItem])
def get_dead_stock_risk(category: Optional[str] = None):
    """Get items at risk of becoming dead stock"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection not available.")
    
    try:
        logger.info(f"Calculating dead stock risk items for category: {category}")
        
        # Build query
        query = supabase.table('products').select("*")
        
        if category:
            query = query.eq('category', category)
        
        products_response = query.execute()
        products_df = pd.DataFrame(products_response.data)
        
        # Calculate days until expiry
        products_df['days_until_expiry'] = products_df['expiry_date'].apply(
            lambda x: (datetime.strptime(x, "%Y-%m-%d").date() - datetime.now().date()).days
        )
        
        # Filter out already expired products
        products_df = products_df[products_df['days_until_expiry'] > 0]
        
        # Get all transactions to calculate sales velocity
        transactions_response = supabase.table('transactions').select("*").execute()
        transactions_df = pd.DataFrame(transactions_response.data)
        
        # Calculate sales velocity for each product
        if not transactions_df.empty:
            sales_metrics = transactions_df.groupby('product_id').agg({
                'quantity': ['sum', 'mean', 'count'],
                'purchase_date': ['min', 'max']
            }).reset_index()
            
            sales_metrics.columns = ['product_id', 'total_quantity_sold', 'avg_quantity_per_sale',
                                    'number_of_sales', 'first_sale_date', 'last_sale_date']
            
            # Calculate sales velocity
            sales_metrics['days_on_market'] = (
                pd.to_datetime(sales_metrics['last_sale_date']) - 
                pd.to_datetime(sales_metrics['first_sale_date'])
            ).dt.days + 1
            sales_metrics['sales_velocity'] = sales_metrics['total_quantity_sold'] / sales_metrics['days_on_market']
            
            # Merge with products
            products_df = products_df.merge(sales_metrics[['product_id', 'sales_velocity']], 
                                           on='product_id', how='left')
        
        # Fill NaN values for products with no sales
        products_df['sales_velocity'] = products_df.get('sales_velocity', 0).fillna(0)
        
        # Apply dead stock risk calculation
        at_risk = []
        for _, product in products_df.iterrows():
            if recommender.is_dead_stock_risk(product.to_dict()):
                at_risk.append(product)
        
        items = []
        for product in at_risk:
            # Calculate risk score (0-1) based on urgency
            days_left = product['days_until_expiry']
            risk_score = max(0, min(1, (30 - days_left) / 30))
            
            item = DeadStockRiskItem(
                product_id=str(product['product_id']),
                name=str(product['name']),
                category=str(product['category']),
                days_until_expiry=int(product['days_until_expiry']),
                current_discount_percent=float(product['current_discount_percent']),
                price_mrp=float(product['price_mrp']),
                expiry_date=str(product['expiry_date']),
                risk_score=risk_score,
                threshold=30,  # Using 30-day threshold
            )
            items.append(item)
        
        logger.info(f"Successfully calculated {len(items)} dead stock risk items")
        
        # Sort by days_until_expiry (ascending)
        items_sorted = sorted(items, key=lambda x: x.days_until_expiry)
        
        return items_sorted
        
    except Exception as e:
        logger.error(f"Error calculating dead stock risk: {e}")
        raise HTTPException(status_code=500, detail=f"Error calculating dead stock risk: {str(e)}")

@app.get("/categories")
def get_categories():
    """Get all available product categories"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection not available.")
    
    try:
        # Use distinct query
        response = supabase.table('products').select('category').execute()
        categories = list(set([item['category'] for item in response.data]))
        return {"categories": sorted(categories)}
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching categories: {str(e)}")

@app.get("/users")
def get_users():
    """Get all available users"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection not available.")
    
    try:
        response = supabase.table('users').select("*").execute()
        users = []
        for row in response.data:
            users.append({
                "id": str(row["user_id"]),
                "name": f"User {row['user_id']}",
                "diet_type": str(row["diet_type"]),
                "allergies": row.get("allergies", []),
                "prefers_discount": bool(row["prefers_discount"])
            })
        return {"users": users}
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True) 