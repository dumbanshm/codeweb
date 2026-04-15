import os
import sys
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
import pandas as pd
import logging
from datetime import datetime, timedelta
from supabase import create_client, Client

# Import the existing UnifiedRecommendationSystem
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from unified_waste_reduction_system import UnifiedRecommendationSystem, calculate_dead_stock_risk_dynamic

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://bwysarrweyooqtjkowzp.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ3eXNhcnJ3ZXlvb3F0amtvd3pwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIzNTIzODEsImV4cCI6MjA2NzkyODM4MX0.cfOrT6MXZ9XHAjYC0K1rri1C4-jGmBbE9q0RQLpR3d8")

# Load all data from Supabase at startup
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Connected to Supabase successfully")
    
    # Fetch all users
    users_response = supabase.table('users').select("*").execute()
    users_df = pd.DataFrame(users_response.data)
    logger.info(f"Loaded {len(users_df)} users from Supabase")
    
    # Fetch all products
    products_response = supabase.table('products').select("*").execute()
    products_df = pd.DataFrame(products_response.data)
    
    # Convert date strings to datetime objects
    products_df['packaging_date'] = pd.to_datetime(products_df['packaging_date'])
    products_df['expiry_date'] = pd.to_datetime(products_df['expiry_date'])
    
    logger.info(f"Loaded {len(products_df)} products from Supabase")
    
    # Fetch all transactions
    transactions_response = supabase.table('transactions').select("*").execute()
    transactions_df = pd.DataFrame(transactions_response.data)
    
    # Convert date strings to datetime objects
    transactions_df['purchase_date'] = pd.to_datetime(transactions_df['purchase_date'])
    
    logger.info(f"Loaded {len(transactions_df)} transactions from Supabase")
    
    # Initialize the UnifiedRecommendationSystem with the loaded data
    system = UnifiedRecommendationSystem(users_df, products_df, transactions_df)
    logger.info("UnifiedRecommendationSystem initialized successfully")
    
except Exception as e:
    logger.error(f"Failed to initialize system: {e}")
    system = None

app = FastAPI(
    title="Unified Waste Reduction API (Supabase)",
    description="API for waste reduction recommendations using Supabase data with original model logic",
    version="3.0.0"
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

# Pydantic models for responses (same as original)
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
    inventory_quantity: Optional[int] = None
    expiry_date: Optional[str] = None
    risk_score: Optional[float] = None
    threshold: Optional[int] = None

class Product(BaseModel):
    product_id: str
    name: str
    category: str
    brand: str
    diet_type: str
    allergens: List[str]
    shelf_life_days: int
    packaging_date: str
    expiry_date: str
    days_until_expiry: int
    weight_grams: int
    price_mrp: float
    cost_price: Optional[float] = None
    current_discount_percent: float
    inventory_quantity: int
    initial_inventory_quantity: Optional[int] = None
    total_cost: Optional[float] = None
    revenue_generated: Optional[float] = 0.0
    store_location_lat: float
    store_location_lon: float
    is_dead_stock_risk: Optional[int] = None

class ApiResponse(BaseModel):
    message: str
    status: str = "success"

class TransactionCreate(BaseModel):
    user_id: str
    product_id: str
    quantity: int = 1
    
class TransactionResponse(BaseModel):
    transaction_id: int
    user_id: str
    product_id: str
    quantity: int
    price_paid_per_unit: float
    total_price_paid: float
    discount_percent: float
    message: str

class ExpiredProductsResponse(BaseModel):
    total_expired_products: int
    total_expired_value: float
    category_split: dict
    category_details: List[dict]

class WeeklyInventoryData(BaseModel):
    week_start: str
    week_end: str
    week_number: int
    total_inventory: float  # Can be qty or cost
    sold_inventory: float  # Can be qty or cost
    alive_products_count: int
    metric_type: str  # "qty" or "cost"

class WeeklyInventoryResponse(BaseModel):
    weeks: List[WeeklyInventoryData]
    summary: dict
    metric_type: str

class PaginatedProductsResponse(BaseModel):
    products: List[Product]
    total_items: int
    total_pages: int
    current_page: int
    page_size: int
    has_next: bool
    has_previous: bool

class WeeklyExpiredData(BaseModel):
    week_start: str
    week_end: str
    week_number: int
    expired_count: int
    expired_value: float
    expired_by_category: dict
    metric_type: str  # "qty" or "cost"

class WeeklyExpiredResponse(BaseModel):
    weeks: List[WeeklyExpiredData]
    summary: dict
    metric_type: str

@app.get("/", response_model=ApiResponse)
def root():
    return ApiResponse(
        message="Unified Waste Reduction System API (Supabase) is running.",
        status="success"
    )

@app.get("/health")
def health_check():
    """Health check endpoint"""
    model_status = "loaded" if system is not None else "not_loaded"
    db_status = "connected" if supabase is not None else "disconnected"
    return {
        "status": "healthy",
        "model_status": model_status,
        "database_status": db_status,
        "api_version": "3.0.0"
    }

@app.get("/recommendations/{user_id}", response_model=RecommendationsResponse)
def get_recommendations(user_id: str, n: int = Query(10, ge=1, le=50)):
    """Get personalized recommendations for a user"""
    if system is None:
        raise HTTPException(status_code=500, detail="Model not loaded.")
    
    try:
        logger.info(f"Generating recommendations for user: {user_id}")
        recs = system.get_hybrid_recommendations(user_id, n_recommendations=n)
        
        if recs.empty:
            logger.warning(f"No recommendations found for user: {user_id}")
            return RecommendationsResponse(user_id=user_id, recommendations=[])
        
        # Convert DataFrame to list of Recommendation
        recommendations = []
        for _, row in recs.iterrows():
            try:
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
                    score=float(row.get("hybrid_score", row.get("recommendation_score", 0))),
                    is_dead_stock_risk=int(row.get("is_dead_stock_risk", 0)),
                )
                recommendations.append(recommendation)
            except Exception as row_error:
                logger.error(f"Error processing recommendation row: {row_error}")
                continue
        
        logger.info(f"Successfully generated {len(recommendations)} recommendations for user: {user_id}")
        return RecommendationsResponse(user_id=user_id, recommendations=recommendations)
        
    except Exception as e:
        logger.error(f"Error generating recommendations for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating recommendations: {str(e)}")

@app.get("/dead_stock_risk", response_model=List[DeadStockRiskItem])
def get_dead_stock_risk(category: Optional[str] = None):
    """Get items at risk of becoming dead stock"""
    if system is None:
        raise HTTPException(status_code=500, detail="Model not loaded.")
    
    try:
        logger.info(f"Fetching dead stock risk items for category: {category}")
        df = system.products_df.copy()
        
        if category:
            df = df[df["category"] == category]
            
        at_risk = df[df["is_dead_stock_risk"] == 1]
        
        items = []
        for _, row in at_risk.iterrows():
            try:
                # Calculate risk score from the threshold calculator
                threshold = system.threshold_calculator.get_threshold(row['product_id'])
                days_left = row['days_until_expiry']
                risk_score = max(0, min(1, (threshold - days_left) / threshold)) if threshold > 0 else 0
                
                item = DeadStockRiskItem(
                    product_id=str(row.get("product_id", "")),
                    name=str(row.get("name", "")),
                    category=str(row.get("category", "")),
                    days_until_expiry=int(row.get("days_until_expiry", 0)),
                    current_discount_percent=float(row.get("current_discount_percent", 0)),
                    price_mrp=float(row.get("price_mrp", 0)),
                    inventory_quantity=int(row.get("inventory_quantity", 0)),
                    expiry_date=str(row.get("expiry_date", "")),
                    risk_score=risk_score,
                    threshold=threshold,
                )
                items.append(item)
            except Exception as row_error:
                logger.error(f"Error processing dead stock risk row: {row_error}")
                continue
        
        logger.info(f"Successfully fetched {len(items)} dead stock risk items")
        
        # Sort by days_until_expiry (ascending) so most urgent items appear first
        items_sorted = sorted(items, key=lambda x: x.days_until_expiry)
        
        return items_sorted
        
    except Exception as e:
        logger.error(f"Error fetching dead stock risk: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching dead stock risk: {str(e)}")

@app.get("/categories")
def get_categories():
    """Get all available product categories"""
    if system is None:
        raise HTTPException(status_code=500, detail="Model not loaded.")
    
    try:
        categories = system.products_df["category"].unique().tolist()
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching categories: {str(e)}")

@app.get("/products", response_model=PaginatedProductsResponse)
def get_products(
    category: Optional[str] = Query(None, description="Filter by category"),
    diet_type: Optional[str] = Query(None, description="Filter by diet type"),
    min_discount: Optional[float] = Query(None, ge=0, le=100, description="Minimum discount percentage"),
    max_days_until_expiry: Optional[int] = Query(None, ge=0, description="Maximum days until expiry"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page")
):
    """Get products with optional filters and pagination support"""
    if system is None:
        raise HTTPException(status_code=500, detail="Model not loaded.")
    
    try:
        logger.info("Fetching products with filters: " + 
                   f"category={category}, diet_type={diet_type}, " +
                   f"min_discount={min_discount}, max_days_until_expiry={max_days_until_expiry}, " +
                   f"page={page}, page_size={page_size}")
        
        # Start with all products
        df = system.products_df.copy()
        
        # Apply filters
        if category:
            df = df[df["category"] == category]
        
        if diet_type:
            df = df[df["diet_type"] == diet_type]
        
        if min_discount is not None:
            df = df[df["current_discount_percent"] >= min_discount]
        
        if max_days_until_expiry is not None:
            df = df[df["days_until_expiry"] <= max_days_until_expiry]
        
        # Convert to Product models
        products = []
        for _, row in df.iterrows():
            try:
                # Handle allergens - could be a list or string
                allergens = row.get("allergens", [])
                if isinstance(allergens, str):
                    # If it's a comma-separated string, split it
                    allergens = [a.strip() for a in allergens.split(",")] if allergens else []
                elif not isinstance(allergens, list):
                    allergens = []
                
                product = Product(
                    product_id=str(row.get("product_id", "")),
                    name=str(row.get("name", "")),
                    category=str(row.get("category", "")),
                    brand=str(row.get("brand", "")),
                    diet_type=str(row.get("diet_type", "")),
                    allergens=allergens,
                    shelf_life_days=int(row.get("shelf_life_days", 0)),
                    packaging_date=str(row.get("packaging_date", "")),
                    expiry_date=str(row.get("expiry_date", "")),
                    days_until_expiry=int(row.get("days_until_expiry", 0)),
                    weight_grams=int(row.get("weight_grams", 0)),
                    price_mrp=float(row.get("price_mrp", 0)),
                    cost_price=float(row.get("cost_price", 0)) if row.get("cost_price") is not None else None,
                    current_discount_percent=float(row.get("current_discount_percent", 0)),
                    inventory_quantity=int(row.get("inventory_quantity", 0)),
                    initial_inventory_quantity=int(row.get("initial_inventory_quantity", 0)) if row.get("initial_inventory_quantity") is not None else None,
                    total_cost=float(row.get("total_cost", 0)) if row.get("total_cost") is not None else None,
                    revenue_generated=float(row.get("revenue_generated", 0)) if row.get("revenue_generated") is not None else 0.0,
                    store_location_lat=float(row.get("store_location_lat", 0)),
                    store_location_lon=float(row.get("store_location_lon", 0)),
                    is_dead_stock_risk=int(row.get("is_dead_stock_risk", 0))
                )
                products.append(product)
            except Exception as row_error:
                logger.error(f"Error processing product row: {row_error}")
                continue
        
        logger.info(f"Successfully fetched {len(products)} products")
        
        # Sort by product_id for consistent ordering
        products_sorted = sorted(products, key=lambda x: x.product_id)
        
        # Calculate pagination
        total_items = len(products_sorted)
        total_pages = (total_items + page_size - 1) // page_size  # Ceiling division
        
        # Calculate start and end indices for the current page
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_items)
        
        # Get the products for the current page
        paginated_products = products_sorted[start_idx:end_idx] if start_idx < total_items else []
        
        # Return paginated response
        return PaginatedProductsResponse(
            products=paginated_products,
            total_items=total_items,
            total_pages=total_pages,
            current_page=page,
            page_size=page_size,
            has_next=page < total_pages,
            has_previous=page > 1
        )
        
    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching products: {str(e)}")
    
@app.get("/users")
def get_users():
    """Get all available users"""
    if system is None:
        raise HTTPException(status_code=500, detail="Model not loaded.")
    
    try:
        users = []
        for _, row in system.users_df.iterrows():
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

@app.get("/expired_products", response_model=ExpiredProductsResponse)
def get_expired_products():
    """Get number and category split of expired products cost-wise"""
    if system is None:
        raise HTTPException(status_code=500, detail="Model not loaded.")
    
    try:
        logger.info("Fetching expired products data")
        
        # Get all products including expired ones from all_products_df
        df = system.all_products_df.copy()
        
        # Calculate days until expiry
        current_date = pd.Timestamp.now()
        df['days_until_expiry'] = (df['expiry_date'] - current_date).dt.days
        
        # Get expired products (days_until_expiry < 0)
        expired_df = df[df["days_until_expiry"] < 0]
        
        # Calculate total value for each expired product
        expired_df["total_value"] = expired_df["price_mrp"] * expired_df["inventory_quantity"]
        
        # Calculate category-wise statistics
        category_stats = expired_df.groupby("category").agg({
            "product_id": "count",  # Number of products
            "total_value": "sum",   # Total value
            "inventory_quantity": "sum"  # Total quantity
        }).reset_index()
        
        category_stats.columns = ["category", "product_count", "total_value", "total_quantity"]
        
        # Calculate percentage split
        total_expired_value = category_stats["total_value"].sum()
        category_split = {}
        category_details = []
        
        for _, row in category_stats.iterrows():
            percentage = (row["total_value"] / total_expired_value * 100) if total_expired_value > 0 else 0
            category_split[row["category"]] = round(percentage, 2)
            
            category_details.append({
                "category": row["category"],
                "product_count": int(row["product_count"]),
                "total_quantity": int(row["total_quantity"]),
                "total_value": round(float(row["total_value"]), 2),
                "percentage_of_total": round(percentage, 2)
            })
        
        # Sort category details by total value descending
        category_details.sort(key=lambda x: x["total_value"], reverse=True)
        
        response = ExpiredProductsResponse(
            total_expired_products=len(expired_df),
            total_expired_value=round(float(total_expired_value), 2),
            category_split=category_split,
            category_details=category_details
        )
        
        logger.info(f"Successfully fetched expired products data: {len(expired_df)} products")
        return response
        
    except Exception as e:
        logger.error(f"Error fetching expired products: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching expired products: {str(e)}")

@app.post("/refresh_data")
def refresh_data():
    """Refresh data from Supabase"""
    global system
    
    try:
        # Fetch fresh data from Supabase
        users_response = supabase.table('users').select("*").execute()
        users_df = pd.DataFrame(users_response.data)
        
        products_response = supabase.table('products').select("*").execute()
        products_df = pd.DataFrame(products_response.data)
        products_df['packaging_date'] = pd.to_datetime(products_df['packaging_date'])
        products_df['expiry_date'] = pd.to_datetime(products_df['expiry_date'])
        
        transactions_response = supabase.table('transactions').select("*").execute()
        transactions_df = pd.DataFrame(transactions_response.data)
        transactions_df['purchase_date'] = pd.to_datetime(transactions_df['purchase_date'])
        
        # Reinitialize the system
        system = UnifiedRecommendationSystem(users_df, products_df, transactions_df)
        
        logger.info("Data refreshed successfully")
        return {"message": "Data refreshed successfully", "status": "success"}
        
    except Exception as e:
        logger.error(f"Error refreshing data: {e}")
        raise HTTPException(status_code=500, detail=f"Error refreshing data: {str(e)}")

@app.post("/transactions", response_model=TransactionResponse)
def create_transaction(transaction: TransactionCreate, use_dynamic_pricing: bool = True):
    """
    Create a new transaction - automatically updates inventory and revenue via database trigger
    
    Args:
        transaction: Transaction details (user_id, product_id, quantity)
        use_dynamic_pricing: If True, uses dynamic pricing engine (default: True)
    """
    try:
        logger.info(f"Creating transaction for user {transaction.user_id}, product {transaction.product_id}, dynamic_pricing={use_dynamic_pricing}")
        
        # Get product details
        product_response = supabase.table('products').select("*").eq('product_id', transaction.product_id).execute()
        if not product_response.data:
            raise HTTPException(status_code=404, detail=f"Product {transaction.product_id} not found")
        
        product = product_response.data[0]
        
        # Check inventory
        if product['inventory_quantity'] < transaction.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient inventory. Available: {product['inventory_quantity']}")
        
        # Get user details
        user_response = supabase.table('users').select("*").eq('user_id', transaction.user_id).execute()
        if not user_response.data:
            raise HTTPException(status_code=404, detail=f"User {transaction.user_id} not found")
        
        user = user_response.data[0]
        
        # Calculate pricing
        if use_dynamic_pricing:
            # Use dynamic pricing engine
            product_df = pd.DataFrame([product])
            
            # Add necessary fields for dynamic pricing calculation
            current_date = pd.Timestamp.now()
            product_df['expiry_date'] = pd.to_datetime(product_df['expiry_date'])
            product_df['days_until_expiry'] = (product_df['expiry_date'] - current_date).dt.days
            
            # Get sales metrics for this product
            product_sales = transactions_df[transactions_df['product_id'] == transaction.product_id]
            if len(product_sales) > 0:
                sales_velocity = len(product_sales) / 30  # Approximate daily velocity
                avg_engagement = product_sales['user_engaged_with_deal'].mean()
            else:
                sales_velocity = 0
                avg_engagement = 0
            
            product_df['sales_velocity'] = sales_velocity
            product_df['avg_user_engagement'] = avg_engagement
            product_df['is_dead_stock_risk'] = system.products_df[
                system.products_df['product_id'] == transaction.product_id
            ]['is_dead_stock_risk'].values[0] if transaction.product_id in system.products_df['product_id'].values else 0
            
            # Calculate dynamic discount
            discount_info = system.pricing_engine.calculate_dynamic_discount(product_df.iloc[0])
            discount_percent = float(discount_info['recommended_discount'])
            
            logger.info(f"Dynamic pricing: current={discount_info['current_discount']}%, "
                       f"recommended={discount_percent}%, urgency={discount_info['urgency_score']:.2f}, "
                       f"reason={discount_info['reasoning']}")
        else:
            # Use static discount
            discount_percent = float(product['current_discount_percent'])
        
        price_per_unit = float(product['price_mrp']) * (1 - discount_percent / 100)
        total_price = price_per_unit * transaction.quantity
        
        # Calculate days to expiry
        current_date = pd.Timestamp.now()
        expiry_date = pd.to_datetime(product['expiry_date'])
        days_to_expiry = (expiry_date - current_date).days
        
        # Create transaction
        transaction_data = {
            'user_id': transaction.user_id,
            'product_id': transaction.product_id,
            'purchase_date': current_date.strftime('%Y-%m-%d'),
            'quantity': transaction.quantity,
            'price_paid_per_unit': round(price_per_unit, 2),
            'total_price_paid': round(total_price, 2),
            'discount_percent': discount_percent,
            'product_diet_type': product['diet_type'],
            'user_diet_type': user['diet_type'],
            'days_to_expiry_at_purchase': days_to_expiry,
            'user_engaged_with_deal': 1 if discount_percent > 0 else 0
        }
        
        # Insert transaction (trigger will update inventory and revenue)
        transaction_response = supabase.table('transactions').insert(transaction_data).execute()
        
        if transaction_response.data:
            created_transaction = transaction_response.data[0]
            
            # If using dynamic pricing, optionally update the product's current discount
            if use_dynamic_pricing and discount_percent != float(product['current_discount_percent']):
                # Update the product's discount for future transactions
                supabase.table('products').update({
                    'current_discount_percent': discount_percent
                }).eq('product_id', transaction.product_id).execute()
            
            # Refresh data to get updated inventory
            refresh_data()
            
            pricing_method = "dynamic" if use_dynamic_pricing else "static"
            return TransactionResponse(
                transaction_id=created_transaction['transaction_id'],
                user_id=created_transaction['user_id'],
                product_id=created_transaction['product_id'],
                quantity=created_transaction['quantity'],
                price_paid_per_unit=created_transaction['price_paid_per_unit'],
                total_price_paid=created_transaction['total_price_paid'],
                discount_percent=created_transaction['discount_percent'],
                message=f"Transaction created successfully with {pricing_method} pricing. Inventory and revenue updated automatically."
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to create transaction")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating transaction: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating transaction: {str(e)}")

@app.get("/dynamic_pricing/{product_id}")
def get_dynamic_pricing(product_id: str):
    """Get dynamic pricing recommendation for a specific product"""
    if system is None:
        raise HTTPException(status_code=500, detail="Model not loaded.")
    
    try:
        # Get product from all_products_df to include expired ones
        product_df = system.all_products_df[system.all_products_df['product_id'] == product_id]
        
        if product_df.empty:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
        
        product = product_df.iloc[0]
        
        # Calculate days until expiry
        current_date = pd.Timestamp.now()
        product['days_until_expiry'] = (pd.to_datetime(product['expiry_date']) - current_date).days
        
        # Add sales metrics
        product_sales = system.transactions_df[system.transactions_df['product_id'] == product_id]
        if len(product_sales) > 0:
            product['sales_velocity'] = len(product_sales) / 30
            product['avg_user_engagement'] = product_sales['user_engaged_with_deal'].mean()
        else:
            product['sales_velocity'] = 0
            product['avg_user_engagement'] = 0
        
        # Check if it's a dead stock risk
        product['is_dead_stock_risk'] = calculate_dead_stock_risk_dynamic(product, system.threshold_calculator)
        
        # Calculate dynamic pricing
        urgency_score = system.pricing_engine.calculate_dynamic_urgency_score(product)
        discount_info = system.pricing_engine.calculate_dynamic_discount(product)
        
        return {
            "product_id": product_id,
            "product_name": product['name'],
            "days_until_expiry": int(product['days_until_expiry']),
            "current_discount": float(product['current_discount_percent']),
            "recommended_discount": discount_info['recommended_discount'],
            "discount_increase": discount_info['discount_increase'],
            "urgency_score": urgency_score,
            "reasoning": discount_info['reasoning'],
            "current_price": float(product['price_mrp']) * (1 - float(product['current_discount_percent'])/100),
            "recommended_price": float(product['price_mrp']) * (1 - discount_info['recommended_discount']/100),
            "savings": float(product['price_mrp']) * discount_info['discount_increase']/100,
            "is_dead_stock_risk": bool(product['is_dead_stock_risk'])
        }
        
    except Exception as e:
        logger.error(f"Error calculating dynamic pricing: {e}")
        raise HTTPException(status_code=500, detail=f"Error calculating dynamic pricing: {str(e)}")

@app.get("/inventory_analytics")
def get_inventory_analytics(category: Optional[str] = None, min_profit_margin: Optional[float] = None):
    """
    Get inventory analytics from the database view
    Shows profitability metrics: initial investment, revenue, gross profit, profit margin
    """
    try:
        # Query the inventory_analytics view
        query = supabase.table('inventory_analytics').select("*")
        
        # Apply filters if provided
        if category:
            query = query.eq('category', category)
        
        if min_profit_margin is not None:
            query = query.gte('profit_margin', min_profit_margin)
        
        response = query.execute()
        
        if response.data:
            # Calculate summary statistics
            df = pd.DataFrame(response.data)
            
            summary = {
                "total_initial_investment": float(df['initial_investment'].sum()),
                "total_revenue_generated": float(df['revenue_generated'].sum()),
                "total_gross_profit": float(df['gross_profit'].sum()),
                "average_profit_margin": float(df['profit_margin'].mean()),
                "total_units_sold": int(df['units_sold'].sum()),
                "products_analyzed": len(df),
                "products": response.data
            }
            
            return summary
        else:
            return {
                "total_initial_investment": 0,
                "total_revenue_generated": 0,
                "total_gross_profit": 0,
                "average_profit_margin": 0,
                "total_units_sold": 0,
                "products_analyzed": 0,
                "products": []
            }
            
    except Exception as e:
        logger.error(f"Error fetching inventory analytics: {e}")
        # Fallback to manual calculation if view doesn't exist
        try:
            products_df = system.products_df.copy()
            
            if category:
                products_df = products_df[products_df['category'] == category]
            
            # Manual calculation
            analytics = []
            for _, product in products_df.iterrows():
                if 'initial_inventory_quantity' in product and product.get('initial_inventory_quantity'):
                    units_sold = product.get('initial_inventory_quantity', 0) - product.get('inventory_quantity', 0)
                    gross_profit = product.get('revenue_generated', 0) - (product.get('cost_price', 0) * units_sold)
                    profit_margin = (gross_profit / product.get('revenue_generated', 1) * 100) if product.get('revenue_generated', 0) > 0 else 0
                    
                    if min_profit_margin is None or profit_margin >= min_profit_margin:
                        analytics.append({
                            'product_id': product['product_id'],
                            'name': product['name'],
                            'category': product['category'],
                            'initial_inventory_quantity': product.get('initial_inventory_quantity', 0),
                            'current_inventory': product.get('inventory_quantity', 0),
                            'units_sold': units_sold,
                            'cost_price': product.get('cost_price', 0),
                            'price_mrp': product.get('price_mrp', 0),
                            'initial_investment': product.get('total_cost', 0),
                            'revenue_generated': product.get('revenue_generated', 0),
                            'gross_profit': gross_profit,
                            'profit_margin': profit_margin,
                            'days_until_expiry': product.get('days_until_expiry', 0),
                            'current_discount_percent': product.get('current_discount_percent', 0)
                        })
            
            df = pd.DataFrame(analytics) if analytics else pd.DataFrame()
            
            return {
                "total_initial_investment": float(df['initial_investment'].sum()) if not df.empty else 0,
                "total_revenue_generated": float(df['revenue_generated'].sum()) if not df.empty else 0,
                "total_gross_profit": float(df['gross_profit'].sum()) if not df.empty else 0,
                "average_profit_margin": float(df['profit_margin'].mean()) if not df.empty else 0,
                "total_units_sold": int(df['units_sold'].sum()) if not df.empty else 0,
                "products_analyzed": len(df),
                "products": analytics
            }
            
        except Exception as fallback_error:
            logger.error(f"Error in fallback calculation: {fallback_error}")
            raise HTTPException(status_code=500, detail="Error calculating inventory analytics")

@app.get("/weekly_inventory", response_model=WeeklyInventoryResponse)
def get_weekly_inventory(
    weeks_back: int = Query(6, ge=1, le=52, description="Number of weeks to look back"),
    metric_type: str = Query("qty", regex="^(qty|cost)$", description="Metric type: 'qty' for quantity, 'cost' for monetary value")
):
    """
    Get weekly inventory analytics for the past N weeks.
    Shows total inventory and sold amounts for products that were alive during each week.
    A product is considered 'alive' during a week if it was packaged before/during the week
    and expires after/during the week.
    Metrics can be shown in quantity (qty) or cost value.
    """
    try:
        # Get current date and calculate week boundaries
        today = datetime.now().date()
        current_week_start = today - timedelta(days=today.weekday())  # Monday of current week
        
        weekly_data = []
        
        for week_offset in range(weeks_back):
            # Calculate week boundaries
            week_end = current_week_start - timedelta(days=7 * week_offset)
            week_start = week_end - timedelta(days=6)
            
            # Filter products that were "alive" during this week
            # Alive = packaged before/during week AND expires after/during week
            alive_products = products_df[
                (pd.to_datetime(products_df['packaging_date']).dt.date <= week_end) &
                (pd.to_datetime(products_df['expiry_date']).dt.date >= week_start)
            ].copy()
            
            # Calculate based on metric type
            if metric_type == "qty":
                # Calculate total inventory quantity
                total_inventory = float(alive_products['inventory_quantity'].sum())
                
                # Calculate sold quantity from transactions
                week_transactions = transactions_df[
                    (pd.to_datetime(transactions_df['purchase_date']).dt.date >= week_start) &
                    (pd.to_datetime(transactions_df['purchase_date']).dt.date <= week_end) &
                    (transactions_df['product_id'].isin(alive_products['product_id']))
                ]
                
                sold_inventory = float(week_transactions['quantity'].sum())
            else:  # metric_type == "cost"
                # Calculate total inventory value (quantity * cost_price)
                alive_products['inventory_value'] = alive_products['inventory_quantity'] * alive_products.get('cost_price', alive_products['price_mrp'] * 0.45)
                total_inventory = float(alive_products['inventory_value'].sum())
                
                # Calculate sold value from transactions
                week_transactions = transactions_df[
                    (pd.to_datetime(transactions_df['purchase_date']).dt.date >= week_start) &
                    (pd.to_datetime(transactions_df['purchase_date']).dt.date <= week_end) &
                    (transactions_df['product_id'].isin(alive_products['product_id']))
                ]
                
                if not week_transactions.empty:
                    # Merge with products to get cost price
                    week_transactions_with_cost = week_transactions.merge(
                        products_df[['product_id', 'cost_price', 'price_mrp']], 
                        on='product_id', 
                        how='left'
                    )
                    # Use cost_price if available, otherwise estimate at 45% of MRP
                    week_transactions_with_cost['unit_cost'] = week_transactions_with_cost.apply(
                        lambda x: x['cost_price'] if pd.notna(x['cost_price']) else x['price_mrp'] * 0.45, axis=1
                    )
                    week_transactions_with_cost['total_cost'] = week_transactions_with_cost['quantity'] * week_transactions_with_cost['unit_cost']
                    sold_inventory = float(week_transactions_with_cost['total_cost'].sum())
                else:
                    sold_inventory = 0.0
            
            weekly_data.append(WeeklyInventoryData(
                week_start=str(week_start),
                week_end=str(week_end),
                week_number=week_offset + 1,
                total_inventory=round(total_inventory, 2),
                sold_inventory=round(sold_inventory, 2),
                alive_products_count=len(alive_products),
                metric_type=metric_type
            ))
        
        # Calculate summary statistics
        total_sold = sum(week.sold_inventory for week in weekly_data)
        avg_weekly_sales = total_sold / weeks_back if weeks_back > 0 else 0
        
        # Current week inventory
        current_alive_products = products_df[
            (pd.to_datetime(products_df['packaging_date']).dt.date <= today) &
            (pd.to_datetime(products_df['expiry_date']).dt.date >= today)
        ]
        
        if metric_type == "qty":
            current_inventory = float(current_alive_products['inventory_quantity'].sum())
            unit_label = "units"
        else:  # cost
            current_alive_products['inventory_value'] = current_alive_products['inventory_quantity'] * current_alive_products.get('cost_price', current_alive_products['price_mrp'] * 0.45)
            current_inventory = float(current_alive_products['inventory_value'].sum())
            unit_label = "₹"
        
        summary = {
            "total_sold_past_n_weeks": round(total_sold, 2),
            "average_weekly_sales": round(avg_weekly_sales, 2),
            "current_total_inventory": round(current_inventory, 2),
            "weeks_analyzed": weeks_back,
            "metric_type": metric_type,
            "unit_label": unit_label
        }
        
        return WeeklyInventoryResponse(
            weeks=weekly_data,
            summary=summary,
            metric_type=metric_type
        )
        
    except Exception as e:
        logger.error(f"Error calculating weekly inventory: {e}")
        raise HTTPException(status_code=500, detail=f"Error calculating weekly inventory: {str(e)}")

@app.get("/weekly_expired", response_model=WeeklyExpiredResponse)
def get_weekly_expired(
    weeks_back: int = Query(6, ge=1, le=52, description="Number of weeks to look back"),
    metric_type: str = Query("qty", regex="^(qty|cost)$", description="Metric type: 'qty' for quantity, 'cost' for monetary value")
):
    """
    Get weekly expired products analytics for the past N weeks.
    Shows the number of products that expired during each week.
    When metric_type is 'cost', category breakdown shows value instead of count.
    """
    try:
        # Get current date and calculate week boundaries
        today = datetime.now().date()
        current_week_start = today - timedelta(days=today.weekday())  # Monday of current week
        
        weekly_data = []
        
        for week_offset in range(weeks_back):
            # Calculate week boundaries
            week_end = current_week_start - timedelta(days=7 * week_offset)
            week_start = week_end - timedelta(days=6)
            
            # Filter products that expired during this week
            expired_products = products_df[
                (pd.to_datetime(products_df['expiry_date']).dt.date >= week_start) &
                (pd.to_datetime(products_df['expiry_date']).dt.date <= week_end)
            ].copy()
            
            # Calculate expired value (using inventory quantity * price_mrp)
            expired_products['expired_value'] = expired_products['inventory_quantity'] * expired_products['price_mrp']
            total_expired_value = float(expired_products['expired_value'].sum())
            
            # Group by category based on metric type
            if metric_type == "qty":
                category_breakdown = expired_products['category'].value_counts().to_dict()
            else:  # cost
                # Calculate cost value per product (using cost_price if available)
                expired_products['cost_value'] = expired_products.apply(
                    lambda x: x['inventory_quantity'] * (x['cost_price'] if pd.notna(x.get('cost_price', None)) else x['price_mrp'] * 0.45),
                    axis=1
                )
                # Group by category and sum cost values
                category_breakdown = expired_products.groupby('category')['cost_value'].sum().round(2).to_dict()
            
            weekly_data.append(WeeklyExpiredData(
                week_start=str(week_start),
                week_end=str(week_end),
                week_number=week_offset + 1,
                expired_count=len(expired_products),
                expired_value=round(total_expired_value, 2),
                expired_by_category=category_breakdown,
                metric_type=metric_type
            ))
        
        # Calculate summary statistics
        total_expired = sum(week.expired_count for week in weekly_data)
        total_value = sum(week.expired_value for week in weekly_data)
        avg_weekly_expired = total_expired / weeks_back if weeks_back > 0 else 0
        avg_weekly_value = total_value / weeks_back if weeks_back > 0 else 0
        
        # Get all categories that had expirations
        all_categories = set()
        for week in weekly_data:
            all_categories.update(week.expired_by_category.keys())
        
        # Calculate category totals across all weeks
        category_totals = {}
        for category in all_categories:
            category_totals[category] = sum(
                week.expired_by_category.get(category, 0) for week in weekly_data
            )
        
        # Round category totals if they're costs
        if metric_type == "cost":
            category_totals = {k: round(v, 2) for k, v in category_totals.items()}
        
        summary = {
            "total_expired_past_n_weeks": total_expired,
            "total_expired_value": round(total_value, 2),
            "average_weekly_expired": round(avg_weekly_expired, 2),
            "average_weekly_expired_value": round(avg_weekly_value, 2),
            "weeks_analyzed": weeks_back,
            "category_totals": category_totals,
            "metric_type": metric_type,
            "unit_label": "units" if metric_type == "qty" else "₹"
        }
        
        return WeeklyExpiredResponse(
            weeks=weekly_data,
            summary=summary,
            metric_type=metric_type
        )
        
    except Exception as e:
        logger.error(f"Error calculating weekly expired products: {e}")
        raise HTTPException(status_code=500, detail=f"Error calculating weekly expired products: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True) 