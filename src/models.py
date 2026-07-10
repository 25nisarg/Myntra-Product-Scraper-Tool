from typing import List, Optional
from pydantic import BaseModel, Field


class SponsoredProduct(BaseModel):
    title: Optional[str] = None
    rating: Optional[str] = None
    price: Optional[str] = None
    product_url: Optional[str] = None


class DeliveryEstimate(BaseModel):
    city: str
    pincode: str
    estimated_delivery_days: Optional[str] = None
    message: Optional[str] = None
    status: str = "unavailable"
    error: Optional[str] = None


class ProductResult(BaseModel):
    product_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    rating: Optional[str] = None
    total_ratings_count: Optional[str] = None
    category: Optional[str] = None
    sponsored_results: List[SponsoredProduct] = Field(default_factory=list)
    delivery_estimates: List[DeliveryEstimate] = Field(default_factory=list)
    status: str = "pending"
    error: Optional[str] = None


class ScrapeResponse(BaseModel):
    total_products: int
    successful: int
    failed: int
    output_file: str
    results: List[ProductResult]