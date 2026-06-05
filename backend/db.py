import os
from pymongo import MongoClient
import cloudinary
import cloudinary.uploader
import cloudinary.api
from dotenv import load_dotenv

# Always load backend/.env regardless of cwd (e.g. uvicorn started from repo root).
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
# override=True: values in backend/.env win over stale shell/OS vars (e.g. old TRYON_BASE_IMAGE_URL).
load_dotenv(
    os.path.join(_BACKEND_DIR, ".env"),
    override=True,
    encoding="utf-8-sig",
)

# MongoDB Setup
# Bounded timeouts + a connection pool so the first request after a cold start
# fails fast (instead of hanging on pymongo's 30s default) and warm requests
# reuse pooled sockets. retryWrites smooths over transient Atlas blips.
_MONGO_KWARGS = dict(
    serverSelectionTimeoutMS=8000,
    connectTimeoutMS=8000,
    socketTimeoutMS=20000,
    maxPoolSize=20,
    retryWrites=True,
)

MONGO_URI = os.getenv("MONGODB_URI")
if MONGO_URI and "mongodb+srv" in MONGO_URI:
    client = MongoClient(MONGO_URI, **_MONGO_KWARGS)
    db_name = os.getenv("MONGODB_DB_NAME", "fitflow")
    db = client[db_name] # Uses the explicit database name
    users_collection = db["users"]
    wardrobe_collection = db["wardrobe"]
else:
    print("⚠️ WARNING: Invalid or missing MONGO_URI in .env. Falling back to local/in-memory for now.")
    # Fallback to local
    client = MongoClient("mongodb://localhost:27017/")
    db = client["fitflow_local"]
    users_collection = db["users"]
    wardrobe_collection = db["wardrobe"]

# Cloudinary Setup
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

def upload_image_to_cloudinary(file_path):
    try:
        if not os.getenv("CLOUDINARY_API_KEY"):
            return None # Skip if not configured
            
        result = cloudinary.uploader.upload(file_path, folder="fitflow")
        return result.get("secure_url")
    except Exception as e:
        print(f"Cloudinary upload failed: {e}")
        return None
