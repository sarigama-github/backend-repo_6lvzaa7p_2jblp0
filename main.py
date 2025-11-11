import os
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson.objectid import ObjectId
from urllib.parse import quote_plus

from database import db, create_document, get_documents
from schemas import Product, Brand, Article, CompareRequest

app = FastAPI(title="Tech Product Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers

def to_public_id(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    d = dict(doc)
    if d.get("_id"):
        d["id"] = str(d.pop("_id"))
    # Convert nested ObjectIds if present
    for k, v in list(d.items()):
        if isinstance(v, ObjectId):
            d[k] = str(v)
    return d


def slugify(text: str) -> str:
    return (
        text.lower()
        .strip()
        .replace(" ", "-")
        .replace("/", "-")
        .replace("_", "-")
    )


@app.get("/")
def read_root():
    return {"message": "Tech Product Platform API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            try:
                cols = db.list_collection_names()
                response["collections"] = cols
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️ Connected but error: {str(e)[:80]}"
        else:
            response["database"] = "❌ Not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# =============== BRANDS ==================
@app.get("/api/brands")
def list_brands():
    docs = get_documents("brand", {}, None)
    return [to_public_id(d) for d in docs]


# =============== PRODUCTS ==================
@app.get("/api/products")
def list_products(
    category: Optional[str] = None,
    search: Optional[str] = None,
    brand: Optional[str] = None,
    minPrice: Optional[float] = None,
    maxPrice: Optional[float] = None,
    ram: Optional[str] = None,
    storage: Optional[str] = None,
    battery: Optional[str] = None,
    camera: Optional[str] = None,
    os_name: Optional[str] = None,
    sort: Optional[str] = None,  # popularity|latest|price_asc|price_desc
    page: int = 1,
    limit: int = 20,
):
    q: Dict[str, Any] = {}
    if category:
        q["category"] = {"$regex": f"^{category}$", "$options": "i"}
    if brand:
        q["brand"] = {"$regex": f"^{brand}$", "$options": "i"}
    if minPrice is not None or maxPrice is not None:
        q["price"] = {}
        if minPrice is not None:
            q["price"]["$gte"] = minPrice
        if maxPrice is not None:
            q["price"]["$lte"] = maxPrice
    if ram:
        q["specs.ram"] = {"$regex": ram, "$options": "i"}
    if storage:
        q["specs.storage"] = {"$regex": storage, "$options": "i"}
    if battery:
        q["specs.battery"] = {"$regex": battery, "$options": "i"}
    if camera:
        q["specs.camera"] = {"$regex": camera, "$options": "i"}
    if os_name:
        q["specs.os"] = {"$regex": os_name, "$options": "i"}
    if search:
        q["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"brand": {"$regex": search, "$options": "i"}},
            {"tags": {"$regex": search, "$options": "i"}},
        ]

    collection = db["product"]
    skip = max(0, (page - 1) * limit)

    sort_clause = None
    if sort == "popularity":
        sort_clause = ("popularity", -1)
    elif sort == "latest":
        sort_clause = ("created_at", -1)
    elif sort == "price_asc":
        sort_clause = ("price", 1)
    elif sort == "price_desc":
        sort_clause = ("price", -1)

    cursor = collection.find(q)
    if sort_clause:
        cursor = cursor.sort([sort_clause])
    cursor = cursor.skip(skip).limit(limit)

    items = [to_public_id(d) for d in cursor]
    total = collection.count_documents(q)
    return {"items": items, "page": page, "limit": limit, "total": total}


@app.get("/api/products/{slug}")
def product_detail(slug: str):
    doc = db["product"].find_one({"slug": slug})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return to_public_id(doc)


@app.post("/api/compare")
def compare_products(payload: CompareRequest):
    ids = payload.ids[:4]
    obj_ids = []
    for _id in ids:
        try:
            obj_ids.append(ObjectId(_id))
        except Exception:
            # Also allow slug
            doc = db["product"].find_one({"slug": _id})
            if doc:
                obj_ids.append(doc["_id"])
    docs = list(db["product"].find({"_id": {"$in": obj_ids}}))
    return [to_public_id(d) for d in docs]


# =============== ARTICLES ==================
@app.get("/api/articles")
def list_articles(category: Optional[str] = None, limit: int = 20):
    q: Dict[str, Any] = {}
    if category:
        q["category"] = {"$regex": f"^{category}$", "$options": "i"}
    cursor = db["article"].find(q).sort([("created_at", -1)]).limit(limit)
    return [to_public_id(d) for d in cursor]


# =============== AUTH (Simple demo) ==================
class AuthPayload(BaseModel):
    email: str
    name: Optional[str] = None


@app.post("/api/auth/login")
def login(payload: AuthPayload):
    # This is a demo stub. In production, implement proper auth.
    user = db["user"].find_one({"email": payload.email})
    if not user:
        user_id = create_document("user", {"email": payload.email, "name": payload.name or "Guest"})
        user = db["user"].find_one({"_id": ObjectId(user_id)})
    return to_public_id(user)


# =============== WISHLIST ==================
class WishlistPayload(BaseModel):
    user_id: str
    product_id: str


@app.get("/api/wishlist")
def get_wishlist(user_id: str):
    items = list(db["wishlist"].find({"user_id": user_id}))
    # Join product details
    product_ids = [ObjectId(it["product_id"]) for it in items if ObjectId.is_valid(it["product_id"])]
    products = {str(p["_id"]): to_public_id(p) for p in db["product"].find({"_id": {"$in": product_ids}})}
    return [products.get(it["product_id"]) for it in items if products.get(it["product_id"]) is not None]


@app.post("/api/wishlist/toggle")
def toggle_wishlist(payload: WishlistPayload):
    existing = db["wishlist"].find_one({"user_id": payload.user_id, "product_id": payload.product_id})
    if existing:
        db["wishlist"].delete_one({"_id": existing["_id"]})
        return {"status": "removed"}
    create_document("wishlist", payload.model_dump())
    return {"status": "added"}


# =============== ADMIN: IMPORT/SEED ==================
class ImportPayload(BaseModel):
    products: Optional[List[Product]] = None
    articles: Optional[List[Article]] = None
    brands: Optional[List[Brand]] = None


@app.post("/api/admin/import")
def admin_import(payload: ImportPayload):
    inserted = {"products": 0, "articles": 0, "brands": 0}
    if payload.brands:
        for b in payload.brands:
            data = b.model_dump()
            data["slug"] = data.get("slug") or slugify(data["name"])
            create_document("brand", data)
            inserted["brands"] += 1
    if payload.products:
        for p in payload.products:
            data = p.model_dump()
            data["slug"] = data.get("slug") or slugify(data["title"])
            create_document("product", data)
            inserted["products"] += 1
    if payload.articles:
        for a in payload.articles:
            data = a.model_dump()
            data["slug"] = data.get("slug") or slugify(data["title"])
            create_document("article", data)
            inserted["articles"] += 1
    return {"inserted": inserted}


@app.post("/api/admin/seed")
def admin_seed():
    # Only seed if empty
    if db["product"].count_documents({}) > 0:
        return {"status": "exists"}

    sample_brands = [
        {"name": "Apple", "slug": "apple", "logo_url": "https://logo.clearbit.com/apple.com"},
        {"name": "Samsung", "slug": "samsung", "logo_url": "https://logo.clearbit.com/samsung.com"},
        {"name": "OnePlus", "slug": "oneplus", "logo_url": "https://logo.clearbit.com/oneplus.com"},
    ]
    for b in sample_brands:
        create_document("brand", b)

    sample_products = [
        {
            "title": "iPhone 15 Pro",
            "slug": "iphone-15-pro",
            "category": "mobile",
            "brand": "Apple",
            "images": [
                "https://images.unsplash.com/photo-1695048134701-4a3f1b2a0f6f",
                "https://images.unsplash.com/photo-1695048134823-efb2d9e2f5a1",
            ],
            "thumbnail": "https://images.unsplash.com/photo-1695048134701-4a3f1b2a0f6f",
            "price": 999.0,
            "price_sources": [
                {"merchant": "Amazon", "url": "#", "price": 999.0},
                {"merchant": "Flipkart", "url": "#", "price": 989.0},
            ],
            "rating": 4.8,
            "popularity": 100,
            "specs": {
                "display": "6.1 OLED 120Hz",
                "camera": "48MP + 12MP",
                "performance": "A17 Pro",
                "battery": "3274 mAh",
                "storage": "128GB",
                "ram": "8GB",
                "os": "iOS 17",
            },
            "tags": ["flagship", "ios", "premium"],
        },
        {
            "title": "Samsung Galaxy S23",
            "slug": "galaxy-s23",
            "category": "mobile",
            "brand": "Samsung",
            "images": [
                "https://images.unsplash.com/photo-1675864507642-1c39c2bf4f84",
            ],
            "thumbnail": "https://images.unsplash.com/photo-1675864507642-1c39c2bf4f84",
            "price": 799.0,
            "price_sources": [
                {"merchant": "Amazon", "url": "#", "price": 779.0},
            ],
            "rating": 4.6,
            "popularity": 90,
            "specs": {
                "display": "6.1 AMOLED 120Hz",
                "camera": "50MP + 10MP + 12MP",
                "performance": "Snapdragon 8 Gen 2",
                "battery": "3900 mAh",
                "storage": "256GB",
                "ram": "8GB",
                "os": "Android 13",
            },
            "tags": ["android", "flagship"],
        },
        {
            "title": "OnePlus 11",
            "slug": "oneplus-11",
            "category": "mobile",
            "brand": "OnePlus",
            "images": [
                "https://images.unsplash.com/photo-1682685794641-1b1e5d0e6505",
            ],
            "thumbnail": "https://images.unsplash.com/photo-1682685794641-1b1e5d0e6505",
            "price": 699.0,
            "price_sources": [
                {"merchant": "Amazon", "url": "#", "price": 679.0},
            ],
            "rating": 4.5,
            "popularity": 80,
            "specs": {
                "display": "6.7 AMOLED 120Hz",
                "camera": "50MP + 48MP + 32MP",
                "performance": "Snapdragon 8 Gen 2",
                "battery": "5000 mAh",
                "storage": "256GB",
                "ram": "12GB",
                "os": "Android 13",
            },
            "tags": ["value", "android"],
        },
    ]

    for p in sample_products:
        create_document("product", p)

    sample_articles = [
        {
            "title": "Top phones under $500 in 2025",
            "slug": "top-phones-under-500-2025",
            "cover_image": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9",
            "excerpt": "Great value phones you can buy today.",
            "content": "Long form review content here...",
            "author": "Flames Editorial",
            "category": "guide",
        },
        {
            "title": "Galaxy S23 Review: Still a compact champ",
            "slug": "galaxy-s23-review",
            "cover_image": "https://images.unsplash.com/photo-1510554310709-f60d7bfc35ef",
            "excerpt": "Our verdict after two months of use.",
            "content": "Review content...",
            "author": "Jane Doe",
            "category": "review",
        },
    ]

    for a in sample_articles:
        create_document("article", a)

    return {"status": "seeded"}


# Health for vercel-style pings
@app.get("/api/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
