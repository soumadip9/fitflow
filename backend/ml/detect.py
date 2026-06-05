import os
from .color import extract_color

# Get absolute path to this file's directory (backend/ml/)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(CURRENT_DIR, "best.pt")

if not os.path.exists(model_path):
    raise FileNotFoundError(
        f"Model file not found at '{model_path}'. "
        "Please place your trained model as backend/ml/best.pt."
    )

CONF_THRESHOLD = 0.35
MIN_COVERAGE_RATIO = 0.02
COLOR_DEBUG = os.getenv("COLOR_DEBUG", "0") == "1"
COLOR_DEBUG_DIR = os.path.join(CURRENT_DIR, "..", "uploads", "color_debug")

# ultralytics/torch are heavy (several seconds + lots of RAM) to import. We load
# them lazily so the API process boots fast on free-tier hosts (e.g. Render) —
# this keeps login and data endpoints responsive even on a cold start. The model
# is only loaded the first time an image is actually detected.
_model = None


def get_model():
    """Load and cache the YOLO model on first use."""
    global _model
    if _model is None:
        from ultralytics import YOLO
        _model = YOLO(model_path)
        print("DEBUG MODEL NAMES ON LOAD:", _model.names)
    return _model


def detect_clothes(image_path, target="auto"):
    import cv2

    model = get_model()
    # Read the image once into memory
    image = cv2.imread(image_path)
    if image is None:
        return []

    image_h, image_w = image.shape[:2]
    image_area = max(image_h * image_w, 1)
    target = (target or "auto").lower()

    # Run model with a moderate threshold, then filter tiny/noisy boxes ourselves.
    results = model(image, conf=CONF_THRESHOLD)[0]

    candidates = []

    if not results.boxes:
        return []

    for box in results.boxes:
        cls_id = int(box.cls[0])
        label = model.names[cls_id].lower()
        print("RAW LABEL:", label) # STEP 4 - DEBUG PRINT

        mapped_category = label

        x1, y1, x2, y2 = map(int, box.xyxy[0])
        conf = float(box.conf[0])
        box_area = max((x2 - x1), 0) * max((y2 - y1), 0)
        coverage = box_area / image_area
        center_y_ratio = ((y1 + y2) / 2) / max(image_h, 1)

        if coverage < MIN_COVERAGE_RATIO:
            continue
        if target == "upper" and center_y_ratio > 0.6:
            continue
        if target == "lower" and center_y_ratio < 0.4:
            continue

        color_dict = extract_color(
            image,
            (x1, y1, x2, y2),
            save_debug=COLOR_DEBUG,
            debug_dir=COLOR_DEBUG_DIR,
            debug_prefix=f"{os.path.basename(image_path)}_{cls_id}_{len(candidates)}"
        )
        color = color_dict.get("color", "gray")
        
        display_name = f"{color} {mapped_category}"

        candidates.append({
            "label": mapped_category,
            "category": mapped_category,
            "color": color,
            "top_colors": color_dict.get("top_colors", []),
            "display_name": display_name,
            "bbox": [x1, y1, x2, y2],
            "confidence": round(conf, 2),
            "coverage": round(coverage, 4),
            "center_y_ratio": round(center_y_ratio, 4),
            "debug_crop": color_dict.get("debug_crop"),
            "debug_swatch": color_dict.get("debug_swatch")
        })

    if not candidates:
        return []

    # If multiple boxes share the same class, keep only the largest one.
    largest_per_class = {}
    for item in candidates:
        key = item["label"]
        if key not in largest_per_class or item["coverage"] > largest_per_class[key]["coverage"]:
            largest_per_class[key] = item

    # Primary selector: choose max image coverage (not confidence).
    selected = max(largest_per_class.values(), key=lambda item: item["coverage"])
    return [selected]
