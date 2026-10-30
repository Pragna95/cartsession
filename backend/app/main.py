import os
from uuid import uuid4
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from bson import ObjectId
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import MongoClient
from dotenv import load_dotenv

# Load backend/.env when running from the backend directory or project root.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "online_cart")
ASTRA_TOKEN = os.getenv("ASTRA_TOKEN")
ASTRA_BUNDLE = os.getenv("ASTRA_SECURE_CONNECT_BUNDLE")
ASTRA_KEYSPACE = os.getenv("ASTRA_KEYSPACE", "default_keyspace")
TTL = int(os.getenv("SESSION_TTL_SECONDS", "86400"))

mongo_client = None
products = None
carts = None
cluster = None
cass = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mongo_client, products, carts, cluster, cass

    # MongoDB Atlas connection
    if not MONGO_URI:
        raise RuntimeError("MONGO_URI is missing. Add it to backend/.env")
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    mongo_client.admin.command("ping")
    db = mongo_client[MONGO_DB_NAME]
    products = db["products"]
    carts = db["carts"]
    products.create_index("name")
    carts.create_index("session_id", unique=True)

    # Seed sample catalogue once, so the UI is not empty on first run.
    if products.count_documents({}) == 0:
        products.insert_many([
            {"name":"Wireless Headphones","description":"Comfortable Bluetooth headphones","price":1499,"category":"Electronics","image":"https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=700","stock":20},
            {"name":"Smart Watch","description":"Fitness and notification companion","price":2299,"category":"Electronics","image":"https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=700","stock":15},
            {"name":"Running Shoes","description":"Lightweight everyday running shoes","price":1899,"category":"Fashion","image":"https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=700","stock":12},
            {"name":"Backpack","description":"College and travel backpack","price":999,"category":"Accessories","image":"https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=700","stock":25},
            {"name":"Sunglasses","description":"Classic everyday sunglasses","price":799,"category":"Accessories","image":"https://images.unsplash.com/photo-1511499767150-a48a237f0083?w=700","stock":18},
            {"name":"Desk Lamp","description":"Minimal LED study lamp","price":649,"category":"Home","image":"https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=700","stock":10}
        ])

    # DataStax Astra DB (Cassandra-compatible) connection.
    if not ASTRA_TOKEN or not ASTRA_BUNDLE:
        raise RuntimeError(
            "ASTRA_TOKEN or ASTRA_SECURE_CONNECT_BUNDLE is missing. "
            "Set both values in backend/.env"
        )
    if not Path(ASTRA_BUNDLE).is_file():
        raise RuntimeError(f"Astra Secure Connect Bundle not found: {ASTRA_BUNDLE}")

    auth_provider = PlainTextAuthProvider("token", ASTRA_TOKEN)
    cluster = Cluster(
        cloud={"secure_connect_bundle": ASTRA_BUNDLE},
        auth_provider=auth_provider,
    )
    cass = cluster.connect(ASTRA_KEYSPACE)

    # Astra keyspaces must be created in the Astra console; CREATE KEYSPACE is
    # intentionally not issued here. Tables can be created in the selected keyspace.
    cass.execute("""CREATE TABLE IF NOT EXISTS sessions (
        session_id text PRIMARY KEY,
        created_at timestamp,
        last_seen timestamp,
        status text
    )""")
    cass.execute("""CREATE TABLE IF NOT EXISTS session_events (
        session_id text,
        event_time timestamp,
        event_type text,
        details text,
        PRIMARY KEY (session_id, event_time)
    ) WITH CLUSTERING ORDER BY (event_time DESC)""")

    print("Connected to MongoDB Atlas and DataStax Astra DB.")
    yield

    if mongo_client:
        mongo_client.close()
    if cluster:
        cluster.shutdown()

app = FastAPI(title="Online Cart and Session Management API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AddItem(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, le=99)

class Quantity(BaseModel):
    quantity: int = Field(ge=1, le=99)

def product_json(p):
    return {
        "id": str(p["_id"]),
        "name": p["name"],
        "description": p.get("description", ""),
        "price": p["price"],
        "category": p.get("category", "Other"),
        "image": p.get("image", ""),
        "stock": p.get("stock", 0),
    }

def active_session(sid):
    row = cass.execute("SELECT * FROM sessions WHERE session_id=%s", (sid,)).one()
    if not row or row.status != "active":
        raise HTTPException(404, "Session expired or not found. Start a new session.")
    return row

def event(sid, kind, detail=""):
    active_session(sid)
    now = datetime.now(timezone.utc)
    cass.execute(
        "UPDATE sessions USING TTL %s SET last_seen=%s,status=%s WHERE session_id=%s",
        (TTL, now, "active", sid),
    )
    cass.execute(
        "INSERT INTO session_events (session_id,event_time,event_type,details) "
        "VALUES (%s,toTimestamp(now()),%s,%s) USING TTL %s",
        (sid, kind, detail, TTL),
    )

def cart_doc(sid):
    carts.update_one({"session_id": sid}, {"$setOnInsert": {"items": []}}, upsert=True)
    return carts.find_one({"session_id": sid})

def cart_json(sid):
    doc = cart_doc(sid)
    result = []
    total = 0
    count = 0
    for item in doc.get("items", []):
        if not ObjectId.is_valid(item["product_id"]):
            continue
        p = products.find_one({"_id": ObjectId(item["product_id"])})
        if p:
            p = product_json(p)
            qty = item["quantity"]
            subtotal = p["price"] * qty
            result.append({"product": p, "quantity": qty, "subtotal": subtotal})
            total += subtotal
            count += qty
    return {"session_id": sid, "items": result, "total": total, "item_count": count}

@app.get("/api/health")
def health():
    return {"status": "ok", "mongodb": "connected", "astra": "connected"}

@app.get("/api/products")
def list_products(q: str = ""):
    query = {
        "$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"category": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]
    } if q else {}
    return [product_json(p) for p in products.find(query).limit(100)]

@app.post("/api/sessions")
def create_session():
    sid = str(uuid4())
    now = datetime.now(timezone.utc)
    cass.execute(
        "INSERT INTO sessions (session_id,created_at,last_seen,status) "
        "VALUES (%s,%s,%s,%s) USING TTL %s",
        (sid, now, now, "active", TTL),
    )
    cass.execute(
        "INSERT INTO session_events (session_id,event_time,event_type,details) "
        "VALUES (%s,toTimestamp(now()),%s,%s) USING TTL %s",
        (sid, "session_created", "Guest session started", TTL),
    )
    cart_doc(sid)
    return {"session_id": sid, "status": "active", "expires_in_seconds": TTL}

@app.get("/api/sessions/{sid}")
def session_status(sid):
    r = active_session(sid)
    return {
        "session_id": sid,
        "status": r.status,
        "created_at": r.created_at.isoformat(),
        "last_seen": r.last_seen.isoformat(),
        "expires_in_seconds": TTL,
    }

@app.post("/api/sessions/{sid}/touch")
def touch(sid):
    event(sid, "session_activity", "Session refreshed")
    return {"status": "active"}

@app.get("/api/sessions/{sid}/events")
def events(sid):
    active_session(sid)
    rows = cass.execute(
        "SELECT event_time,event_type,details FROM session_events WHERE session_id=%s LIMIT 50",
        (sid,),
    )
    return [
        {"event_time": r.event_time.isoformat(), "event_type": r.event_type, "details": r.details}
        for r in rows
    ]

@app.get("/api/cart/{sid}")
def get_cart(sid):
    event(sid, "cart_viewed")
    return cart_json(sid)

@app.post("/api/cart/{sid}/items")
def add_item(sid, payload: AddItem):
    event(sid, "item_added", payload.product_id)
    if not ObjectId.is_valid(payload.product_id):
        raise HTTPException(404, "Product not found")
    p = products.find_one({"_id": ObjectId(payload.product_id)})
    if not p:
        raise HTTPException(404, "Product not found")
    doc = cart_doc(sid)
    items = doc.get("items", [])
    found = False
    for it in items:
        if it["product_id"] == payload.product_id:
            if it["quantity"] + payload.quantity > p["stock"]:
                raise HTTPException(400, "Not enough stock")
            it["quantity"] += payload.quantity
            found = True
            break
    if not found:
        if payload.quantity > p["stock"]:
            raise HTTPException(400, "Not enough stock")
        items.append({"product_id": payload.product_id, "quantity": payload.quantity})
    carts.update_one({"session_id": sid}, {"$set": {"items": items}})
    return cart_json(sid)

@app.patch("/api/cart/{sid}/items/{pid}")
def update_item(sid, pid, payload: Quantity):
    event(sid, "quantity_updated", pid)
    if not ObjectId.is_valid(pid):
        raise HTTPException(404, "Product not found")
    p = products.find_one({"_id": ObjectId(pid)})
    if not p:
        raise HTTPException(404, "Product not found")
    if payload.quantity > p["stock"]:
        raise HTTPException(400, "Not enough stock")
    doc = cart_doc(sid)
    items = doc.get("items", [])
    found = False
    for it in items:
        if it["product_id"] == pid:
            it["quantity"] = payload.quantity
            found = True
    if not found:
        raise HTTPException(404, "Item not in cart")
    carts.update_one({"session_id": sid}, {"$set": {"items": items}})
    return cart_json(sid)

@app.delete("/api/cart/{sid}/items/{pid}")
def remove_item(sid, pid):
    event(sid, "item_removed", pid)
    doc = cart_doc(sid)
    carts.update_one(
        {"session_id": sid},
        {"$set": {"items": [i for i in doc.get("items", []) if i["product_id"] != pid]}},
    )
    return cart_json(sid)

@app.delete("/api/cart/{sid}")
def clear_cart(sid):
    event(sid, "cart_cleared")
    carts.update_one({"session_id": sid}, {"$set": {"items": []}})
    return cart_json(sid)
