"""FitFlow API — load backend/.env before imports that read os.environ."""
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(_BACKEND_DIR / ".env", override=True, encoding="utf-8-sig")

import requests

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import shutil
import os
import uuid
import io
from typing import Optional, List, Tuple
from urllib.parse import urlparse, unquote

from PIL import Image
from bson import ObjectId
from datetime import datetime, timezone

from ml.detect import detect_clothes
from ml.recommender import recommend_outfit, build_outfit, rate_outfit, OCCASIONS
from ml.shopping import test_products
from db import users_collection, wardrobe_collection, upload_image_to_cloudinary
from auth import get_password_hash, verify_password, create_access_token, get_current_user

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.get("/health")
def health():
    """Lightweight liveness probe — hit this from an uptime pinger (e.g. UptimeRobot)
    every ~10 min so Render's free tier never spins down and cold starts disappear."""
    return {"status": "ok"}


@app.on_event("startup")
def _warm_up():
    """Pre-open the Mongo connection and load the YOLO model in the background so
    the first real login / wardrobe upload doesn't pay that one-time cost.
    Runs in a daemon thread so it never delays the server from accepting requests."""
    import threading

    def _warm():
        try:
            from db import client as _mongo
            _mongo.admin.command("ping")
            print("✅ Mongo connection warmed")
        except Exception as e:
            print(f"⚠️  Mongo warm-up skipped: {e}")
        try:
            from ml.detect import get_model
            get_model()
            print("✅ YOLO model warmed")
        except Exception as e:
            print(f"⚠️  Model warm-up skipped: {e}")

    threading.Thread(target=_warm, daemon=True).start()

# Outfit preview: skip remove.bg if image already has alpha; reject API output if still effectively opaque.
_RGBA_ALPHA_CUTOFF = 250
_ALREADY_TRANSPARENT_MIN_RATIO = 0.012
# Reject remove.bg output only if it still looks fully opaque; keep lenient for edge-heavy cutouts.
_OUTPUT_MIN_TRANSPARENT_RATIO = 0.001


def _resize_for_alpha_probe(im: Image.Image, max_side: int = 512) -> Image.Image:
    w, h = im.size
    if max(w, h) <= max_side:
        return im.convert("RGBA")
    scale = max_side / max(w, h)
    nw = max(1, int(w * scale))
    nh = max(1, int(h * scale))
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:  # Pillow < 9.1
        resample = Image.LANCZOS
    return im.convert("RGBA").resize((nw, nh), resample)


def transparency_ratio_rgba(image_bytes: bytes) -> float:
    """Fraction of pixels with alpha < cutoff (0–1). JPEG/opaque images → ~0."""
    try:
        im = Image.open(io.BytesIO(image_bytes))
        im = _resize_for_alpha_probe(im)
        px = im.load()
        w, h = im.size
        if w * h == 0:
            return 0.0
        n = 0
        for y in range(h):
            for x in range(w):
                if px[x, y][3] < _RGBA_ALPHA_CUTOFF:
                    n += 1
        return n / (w * h)
    except Exception:
        return 0.0


def _has_meaningful_transparency(image_bytes: bytes) -> bool:
    """True if image has an alpha channel with at least one semi-transparent pixel."""
    try:
        im = Image.open(io.BytesIO(image_bytes))
        if im.mode == "RGBA":
            alpha = im.split()[3]
        elif im.mode == "LA":
            alpha = im.split()[1]
        elif im.mode == "PA":
            im = im.convert("RGBA")
            alpha = im.split()[3]
        else:
            return False
        return alpha.getextrema()[0] < _RGBA_ALPHA_CUTOFF
    except Exception:
        return False


def _load_image_bytes_for_removal(url: str) -> Tuple[bytes, str]:
    """
    Bytes + file extension for remove.bg. When URL points at this server's /uploads/,
    read from disk so we never HTTP-fetch ourselves (single-worker uvicorn can deadlock).
    """
    parsed = urlparse(url.strip())
    path = unquote(parsed.path or "")
    uploads_marker = "/uploads/"
    if uploads_marker in path:
        suffix = path.split(uploads_marker, 1)[1].strip("/")
        safe = os.path.basename(suffix)
        if safe and ".." not in suffix.replace("\\", "/"):
            disk_path = os.path.join(UPLOAD_DIR, safe)
            if os.path.isfile(disk_path):
                ext = os.path.splitext(safe)[1].lower()
                if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"}:
                    ext = ".jpg"
                with open(disk_path, "rb") as f:
                    return f.read(), ext
    img_resp = requests.get(url, timeout=45)
    img_resp.raise_for_status()
    raw = img_resp.content
    ctype = (img_resp.headers.get("Content-Type") or "").lower()
    ext = ".jpg"
    if "png" in ctype:
        ext = ".png"
    elif "webp" in ctype:
        ext = ".webp"
    return raw, ext


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class UserAuth(BaseModel):
    email: str
    password: str = Field(..., max_length=72)

class DetectedItemChoice(BaseModel):
    category: str
    color: str
    display_name: str
    image_url: str
    confidence: Optional[float] = None
    bbox: Optional[List[int]] = None

class WardrobeStatusUpdate(BaseModel):
    status: str

class BuildOutfitRequest(BaseModel):
    occasion: str = Field(..., description="One of supported occasions")
    gender: Optional[str] = Field(None, description="Profile gender: male | female (optional)")

class RateOutfitRequest(BaseModel):
    occasion: str
    outfit: dict
    gender: Optional[str] = Field(None, description="Profile gender: male | female (optional)")

class ClothingTransparentRequest(BaseModel):
    image_url: str = Field(..., description="Public or localhost URL the server can GET")

class UserProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    fashion_styles: Optional[List[str]] = None
    preferred_colors: Optional[List[str]] = None
    fit_preference: Optional[str] = None
    description: Optional[str] = None
    profile_image: Optional[str] = None


@app.post("/register")
def register(user: UserAuth):
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pwd = get_password_hash(user.password)
    new_user = {
        "email": user.email,
        "password": hashed_pwd
    }
    result = users_collection.insert_one(new_user)
    
    token = create_access_token({"sub": str(result.inserted_id)})
    return {"token": token, "email": user.email}

@app.post("/login")
def login(user: UserAuth):
    db_user = users_collection.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_access_token({"sub": str(db_user["_id"])})
    return {"token": token, "email": user.email}

@app.get("/profile")
def get_profile(user_id: str = Depends(get_current_user)):
    db_user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "email": db_user.get("email"),
        "display_name": db_user.get("display_name", ""),
        "age": db_user.get("age", ""),
        "gender": db_user.get("gender", ""),
        "fashion_styles": db_user.get("fashion_styles", []),
        "preferred_colors": db_user.get("preferred_colors", []),
        "fit_preference": db_user.get("fit_preference", ""),
        "description": db_user.get("description", ""),
        "profile_image": db_user.get("profile_image", "")
    }

@app.put("/profile")
def update_profile(profile: UserProfileUpdate, user_id: str = Depends(get_current_user)):
    update_data = {k: v for k, v in profile.model_dump().items() if v is not None}
    
    if not update_data:
        return {"status": "ok", "message": "No changes provided"}
        
    result = users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {"status": "ok", "message": "Profile updated successfully"}


@app.get("/wardrobe")
def get_wardrobe(user_id: str = Depends(get_current_user)):
    # Fetch user's wardrobe from Mongo
    items = list(wardrobe_collection.find({"user_id": user_id}))
    # Convert ObjectId to string for JSON serialization
    for item in items:
        item["_id"] = str(item["_id"])
        # Backward-compatible defaults for older records.
        if not item.get("created_at"):
            item["created_at"] = _now_iso()
        if not item.get("last_washed_at"):
            item["last_washed_at"] = item.get("created_at")
    return {"items": items}

@app.patch("/wardrobe/{item_id}/status")
def update_wardrobe_status(
    item_id: str,
    payload: WardrobeStatusUpdate = Body(...),
    user_id: str = Depends(get_current_user)
):
    if payload.status not in {"available", "laundry"}:
        raise HTTPException(status_code=400, detail="status must be 'available' or 'laundry'")

    try:
        oid = ObjectId(item_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid wardrobe item id")

    existing = wardrobe_collection.find_one({"_id": oid, "user_id": user_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Wardrobe item not found")

    update_fields = {"status": payload.status}
    now_iso = _now_iso()
    if payload.status == "laundry":
        update_fields["last_sent_to_laundry_at"] = now_iso
    if payload.status == "available" and existing.get("status") == "laundry":
        # Returning from laundry means item has been washed now.
        update_fields["last_washed_at"] = now_iso

    result = wardrobe_collection.update_one(
        {"_id": oid, "user_id": user_id},
        {"$set": update_fields}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Wardrobe item not found")

    updated = wardrobe_collection.find_one({"_id": oid, "user_id": user_id})
    updated["_id"] = str(updated["_id"])
    return {"item": updated}

@app.delete("/wardrobe/{item_id}")
def delete_wardrobe_item(item_id: str, user_id: str = Depends(get_current_user)):
    try:
        oid = ObjectId(item_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid wardrobe item id")

    result = wardrobe_collection.delete_one({"_id": oid, "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Wardrobe item not found")
    return {"success": True}

@app.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    target: str = "auto",
    user_id: str = Depends(get_current_user)
):
    saved_name = f"{uuid.uuid4().hex}_{file.filename}"
    path = os.path.join(UPLOAD_DIR, saved_name)

    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 1. Run Detection
    if target not in {"auto", "upper", "lower"}:
        raise HTTPException(status_code=400, detail="target must be one of: auto, upper, lower")
    items = detect_clothes(path, target=target)
    
    # 2. Upload to Cloudinary (optional fallback if configured)
    cloud_url = upload_image_to_cloudinary(path)
    # If cloudinary fails or isn't set up, we just use the local path (or maybe it breaks on frontend)
    image_url = cloud_url if cloud_url else f"http://127.0.0.1:8000/uploads/{saved_name}"
    return {"detected": items, "image_url": image_url}

@app.post("/detect-items")
async def detect_items(file: UploadFile = File(...), target: str = "auto", user_id: str = Depends(get_current_user)):
    saved_name = f"{uuid.uuid4().hex}_{file.filename}"
    path = os.path.join(UPLOAD_DIR, saved_name)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    if target not in {"auto", "upper", "lower"}:
        raise HTTPException(status_code=400, detail="target must be one of: auto, upper, lower")
    items = detect_clothes(path, target=target)
    return {"detected": items, "supported_occasions": OCCASIONS}

@app.post("/wardrobe/add-detected")
def add_detected_item(payload: DetectedItemChoice = Body(...), user_id: str = Depends(get_current_user)):
    now_iso = _now_iso()
    wardrobe_item = {
        "user_id": user_id,
        "category": payload.category,
        "color": payload.color,
        "display_name": payload.display_name,
        "status": "available",
        "image": payload.image_url,
        "confidence": payload.confidence,
        "bbox": payload.bbox,
        "created_at": now_iso,
        "last_washed_at": now_iso,
    }

    duplicate = wardrobe_collection.find_one({
        "user_id": user_id,
        "category": wardrobe_item["category"],
        "color": wardrobe_item["color"],
        "image": wardrobe_item["image"]
    })

    if duplicate:
        duplicate["_id"] = str(duplicate["_id"])
        return {"item": duplicate}

    result = wardrobe_collection.insert_one(wardrobe_item)
    wardrobe_item["_id"] = str(result.inserted_id)
    return {"item": wardrobe_item}

@app.get("/recommend")
def recommend(occasion: str, user_id: str = Depends(get_current_user)):
    # Fetch user's profile for gender
    db_user = users_collection.find_one({"_id": ObjectId(user_id)})
    gender = db_user.get("gender") if db_user else None

    # Fetch user's wardrobe from Mongo
    user_wardrobe = list(wardrobe_collection.find({"user_id": user_id}))
    for item in user_wardrobe:
        item["_id"] = str(item["_id"])
        
    return recommend_outfit(user_wardrobe, occasion, gender=gender)

@app.post("/build-outfit")
def build_outfit_api(payload: BuildOutfitRequest = Body(...), user_id: str = Depends(get_current_user)):
    occasion = (payload.occasion or "").lower()
    if occasion not in OCCASIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported occasion. Use one of: {', '.join(OCCASIONS)}")

    user_wardrobe = list(wardrobe_collection.find({"user_id": user_id}))
    for item in user_wardrobe:
        item["_id"] = str(item["_id"])

    result = build_outfit(occasion, user_wardrobe, gender=payload.gender)
    return result

@app.post("/rate-outfit")
def rate_outfit_api(payload: RateOutfitRequest = Body(...), user_id: str = Depends(get_current_user)):
    occasion = (payload.occasion or "").lower()
    if occasion not in OCCASIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported occasion. Use one of: {', '.join(OCCASIONS)}")

    # Fetch the user's wardrobe so Groq can suggest items they already own
    user_wardrobe = list(wardrobe_collection.find({"user_id": user_id}))
    for item in user_wardrobe:
        item["_id"] = str(item["_id"])

    return rate_outfit(occasion, payload.outfit or {}, gender=payload.gender, wardrobe=user_wardrobe)

@app.get("/test-shopping")
@app.get("/test-serp-shopping")  # alias
def test_shopping_links():
    """Returns sample [{title, image, link, price}] built from a Google Shopping search URL."""
    return test_products()


@app.get("/clothing/background-removal")
def clothing_background_removal_status(user_id: str = Depends(get_current_user)):
    """Whether remove.bg integration is configured (REMOVEBG_API_KEY)."""
    key = os.getenv("REMOVEBG_API_KEY", "").strip()
    return {"enabled": bool(key)}


@app.post("/clothing/transparent")
def clothing_transparent_png(
    request: Request,
    payload: ClothingTransparentRequest = Body(...),
    user_id: str = Depends(get_current_user),
):
    """
    Download image from image_url, send to remove.bg, save PNG with alpha to uploads/.
    Skips the API if the source already has meaningful transparency. Disables remove.bg
    auto-crop so preview layers are not over-tightened. Verifies the result has real alpha
    before returning; otherwise returns the original image_url.
    """
    key = os.getenv("REMOVEBG_API_KEY", "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Background removal not configured. Set REMOVEBG_API_KEY in backend/.env",
        )
    url = (payload.image_url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="image_url required")
    try:
        raw, ext = _load_image_bytes_for_removal(url)
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Could not download image: {e}") from e

    input_alpha_ratio = transparency_ratio_rgba(raw)
    if input_alpha_ratio >= _ALREADY_TRANSPARENT_MIN_RATIO:
        return {
            "url": url,
            "background_removed": True,
            "skipped_api": True,
            "reason": "already_has_transparency",
            "input_alpha_ratio": round(input_alpha_ratio, 4),
        }

    try:
        rb = requests.post(
            "https://api.remove.bg/v1.0/removebg",
            files={"image_file": (f"source{ext}", raw)},
            # crop=false keeps original framing (avoids over-cropping items in preview).
            data={"size": "auto", "crop": "false"},
            headers={"X-Api-Key": key},
            timeout=90,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"remove.bg unreachable: {e}") from e

    if rb.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"remove.bg error {rb.status_code}: {rb.text[:400]}",
        )

    out_alpha = transparency_ratio_rgba(rb.content)
    looks_cut_out = (
        out_alpha >= _OUTPUT_MIN_TRANSPARENT_RATIO
        or _has_meaningful_transparency(rb.content)
    )
    if not looks_cut_out:
        return {
            "url": url,
            "background_removed": False,
            "skipped_api": False,
            "reason": "output_still_opaque",
            "output_alpha_ratio": round(out_alpha, 4),
        }

    out_name = f"{uuid.uuid4().hex}_nobg.png"
    path = os.path.join(UPLOAD_DIR, out_name)
    with open(path, "wb") as f:
        f.write(rb.content)

    base = str(request.base_url).rstrip("/")
    return {
        "url": f"{base}/uploads/{out_name}",
        "background_removed": True,
        "skipped_api": False,
        "reason": "remove_bg",
        "output_alpha_ratio": round(out_alpha, 4),
    }


from fastapi.staticfiles import StaticFiles
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
