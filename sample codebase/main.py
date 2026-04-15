import pickle
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import pandas as pd
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load the pickled model at startup
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'model.pkl')
try:
    with open(MODEL_PATH, 'rb') as f:
        system = pickle.load(f)
    logger.info("Model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load model: {e}")
    system = None

app = FastAPI(
    title="Unified Waste Reduction API",
    description="API for waste reduction recommendations and dead stock risk analysis",
    version="1.0.0"
)

# Enhanced CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"]  # Expose all headers
)

# Pydantic models for responses
class Recommendation(BaseModel):
    product_id: str
    product_name: str
    name: str  # Add this field
    category: str
    days_until_expiry: int
    price: float
    price_mrp: float  # Add this field
    discount: float
    current_discount_percent: float  # Add this field
    expiry_date: Optional[str] = None  # Add this field
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
    price_mrp: float  # Add this field
    expiry_date: Optional[str] = None  # Add this field
    risk_score: Optional[float] = None
    threshold: Optional[int] = None

class ApiResponse(BaseModel):
    message: str
    status: str = "success"

@app.get("/", response_model=ApiResponse)
def root():
    return ApiResponse(
        message="Unified Waste Reduction System API is running.",
        status="success"
    )

@app.get("/health")
def health_check():
    """Health check endpoint"""
    model_status = "loaded" if system is not None else "not_loaded"
    return {
        "status": "healthy",
        "model_status": model_status,
        "api_version": "1.0.0"
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
        
        # Debug: Log the columns available in the recommendations DataFrame
        logger.info(f"Available columns in recommendations: {recs.columns.tolist()}")
        if not recs.empty:
            logger.info(f"First recommendation row: {recs.iloc[0].to_dict()}")
        
        # Convert DataFrame to list of Recommendation
        recommendations = []
        for _, row in recs.iterrows():
            try:
                recommendation = Recommendation(
                    product_id=str(row.get("product_id", "")),
                    product_name=str(row.get("product_name", "")),  # Fixed: use 'product_name'
                    name=str(row.get("product_name", "")),  # Fixed: use 'product_name'
                    category=str(row.get("category", "")),
                    days_until_expiry=int(row.get("days_until_expiry", 0)),
                    price=float(row.get("price", 0)),  # Fixed: use 'price'
                    price_mrp=float(row.get("price", 0)),  # Fixed: use 'price'
                    discount=float(row.get("discount", 0)),  # Fixed: use 'discount'
                    current_discount_percent=float(row.get("discount", 0)),  # Fixed: use 'discount'
                    expiry_date="",  # Not available in recommendations, leave empty
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
                item = DeadStockRiskItem(
                    product_id=str(row.get("product_id", "")),
                    name=str(row.get("name", "")),
                    category=str(row.get("category", "")),
                    days_until_expiry=int(row.get("days_until_expiry", 0)),
                    current_discount_percent=float(row.get("current_discount_percent", 0)),
                    price_mrp=float(row.get("price_mrp", 0)),  # Add the missing field
                    expiry_date=str(row.get("expiry_date", "")),  # Also add expiry_date
                    risk_score=None,
                    threshold=None,
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
    
@app.get("/users")
def get_users():
    """Get all available users"""
    if system is None:
        raise HTTPException(status_code=500, detail="Model not loaded.")
    
    try:
        # Assuming your system has access to users_df
        users = []
        for _, row in system.users_df.iterrows():
            users.append({
                "id": str(row["user_id"]),
                "name": f"User {row['user_id']}",  # Or generate names based on user_id
                "diet_type": str(row["diet_type"]),
                "allergies": str(row["allergies"]),
                "prefers_discount": bool(row["prefers_discount"])
            })
        return {"users": users}
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)