"""
Database Schemas for Tech Product Platform

Each Pydantic model represents a MongoDB collection. The collection name is the
lowercased class name (e.g., Product -> "product").
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr


class Brand(BaseModel):
    name: str = Field(..., description="Brand name")
    logo_url: Optional[str] = Field(None, description="Public logo URL")
    slug: str = Field(..., description="URL-friendly unique identifier")


class PriceSource(BaseModel):
    merchant: str = Field(..., description="Merchant name e.g., Amazon, Flipkart")
    url: Optional[str] = Field(None, description="Product page URL at merchant")
    price: float = Field(..., ge=0, description="Listed price")


class ProductSpecs(BaseModel):
    display: Optional[str] = None
    camera: Optional[str] = None
    performance: Optional[str] = None
    battery: Optional[str] = None
    storage: Optional[str] = None
    ram: Optional[str] = None
    os: Optional[str] = None
    chipset: Optional[str] = None
    dimensions: Optional[str] = None
    weight: Optional[str] = None
    connectivity: Optional[str] = None
    extras: Optional[Dict[str, Any]] = None


class Product(BaseModel):
    title: str = Field(..., description="Product name")
    slug: str = Field(..., description="URL-friendly unique identifier")
    category: str = Field(..., description="Category: mobile, laptop, tablet, watch, accessory")
    brand: str = Field(..., description="Brand name")
    images: List[str] = Field(default_factory=list)
    thumbnail: Optional[str] = None
    price: float = Field(..., ge=0)
    price_sources: List[PriceSource] = Field(default_factory=list)
    rating: Optional[float] = Field(None, ge=0, le=5)
    popularity: Optional[int] = Field(0, ge=0)
    specs: ProductSpecs = Field(default_factory=ProductSpecs)
    tags: List[str] = Field(default_factory=list)


class Article(BaseModel):
    title: str
    slug: str
    cover_image: Optional[str] = None
    excerpt: Optional[str] = None
    content: str
    author: str
    category: str = Field("news", description="news | review | guide")
    published_at: Optional[str] = None


class User(BaseModel):
    name: Optional[str] = None
    email: EmailStr
    password: Optional[str] = Field(None, description="Hashed password or temp placeholder")
    provider: str = Field("local", description="local | google")
    avatar_url: Optional[str] = None


class Wishlist(BaseModel):
    user_id: str
    product_id: str


# A minimal response model for compare results
class CompareRequest(BaseModel):
    ids: List[str]
