import os

from counter import run_counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF_THRESHOLD = 0.15
PAD = 60  # px of context padding around the crop sent to YOLO

# Standard YOLOv8 (COCO-trained): only generic vehicle classes, no South Asian types.
COCO_MODEL_PATH = os.path.join(BASE_DIR, "models", "yolov8n.pt")
COCO_TO_SURVEY = {
    "bicycle": "Bicycle",
    "motorcycle": "Motorcycle",
    "car": "Car/Suv",
    "bus": "Large Bus",
    "truck": "Medium Truck/2-Axle Truck",
}

# BNVD (Bangladeshi Native Vehicle Dataset) YOLOv8 — trained specifically on
# Bangladesh traffic, covers Rickshaw/CNG/etc. For personal/local use only:
# https://github.com/bipin-saha/BNVD (no license specified in the repo).
BNVD_MODEL_PATH = os.path.join(BASE_DIR, "models", "bnvd_yolov8.pt")
BNVD_TO_SURVEY = {
    "Bicycle": "Bicycle",
    "Rickshaw": "Rickshaw",
    "CNG": "Auto",
    "Motorbike": "Motorcycle",
    "Car": "Car/Suv",
    "MPV": "Car/Suv",
    "Van": "Small Open Truck/Small Van",
    "ShoppingVan": "Small Open Truck/Small Van",
    "Pickup": "Jeep/Pick-up",
    "Bus": "Large Bus",
    "Truck": "Medium Truck/2-Axle Truck",
    "Easybike": "Auto",
    "Leguna": "Tempo/Leguna/Maxi",
    "Bhotbhoti": "Other",
    "PowerTiller": "Other",
    "Wheelbarrow": "Push car (Thela gari)",
    "Pedestrian": None,  # not a vehicle; ignored
}

MODEL_REGISTRY = {
    "coco": (COCO_MODEL_PATH, COCO_TO_SURVEY),
    "bnvd": (BNVD_MODEL_PATH, BNVD_TO_SURVEY),
}
DEFAULT_MODEL_KEY = "bnvd" if os.path.isfile(BNVD_MODEL_PATH) else "coco"


def run_counter_hybrid(video_source, job, min_width=None, min_height=None,
                        lines=None, frame_sink=None, show_window=False,
                        model_key=DEFAULT_MODEL_KEY, conf_threshold=CONF_THRESHOLD,
                        display_max_width=1280):
    """Full-speed line-crossing counting (counter.run_counter's blob tracker) with
    per-crossing vehicle classification: YOLO only runs on the small cropped region
    of a vehicle at the instant it crosses a line, not on every frame. This keeps
    throughput close to the plain counter while still reporting vehicle type per count.

    model_key: "bnvd" (Bangladesh-specific, covers Rickshaw/CNG/etc. — used by default
               if the model file is present) or "coco" (standard YOLOv8, generic classes).

    job keys written: same as counter.run_counter, plus "categories" (per-category totals).
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        job["status"] = "error"
        job["error"] = "ultralytics is not installed. Run: pip install ultralytics"
        job["done"] = True
        return

    if model_key not in MODEL_REGISTRY:
        job["status"] = "error"
        job["error"] = f"Unknown model key: {model_key} (expected 'bnvd' or 'coco')"
        job["done"] = True
        return

    model_path, class_map = MODEL_REGISTRY[model_key]
    if not os.path.isfile(model_path):
        job["status"] = "error"
        job["error"] = f"YOLO model not found: {model_path}"
        job["done"] = True
        return

    model = YOLO(model_path)
    vehicle_classes = {k for k, v in class_map.items() if v is not None}
    categories = {}
    job["categories"] = {}
    job["model_used"] = model_key

    def best_vehicle_in(image):
        results = model(image, verbose=False)[0]
        best_name, best_conf = None, 0.0
        for box in results.boxes:
            cls_id = int(box.cls[0])
            name = model.names[cls_id]
            if name not in vehicle_classes:
                continue
            conf = float(box.conf[0])
            if conf > best_conf:
                best_conf, best_name = conf, name
        return best_name, best_conf

    def classify_crossing(frame, line, x, y, w, h):
        fh, fw = frame.shape[:2]
        x1, y1 = max(0, x - PAD), max(0, y - PAD)
        x2, y2 = min(fw, x + w + PAD), min(fh, y + h + PAD)
        crop = frame[y1:y2, x1:x2]

        best_name, best_conf = (None, 0.0) if crop.size == 0 else best_vehicle_in(crop)

        # Crop missed it (too tight, motion blur, edge of frame): retry on the
        # full frame before giving up, so as few real vehicles as possible land
        # in "Other" for lack of a second look.
        if best_conf < conf_threshold:
            full_name, full_conf = best_vehicle_in(frame)
            if full_conf > best_conf:
                best_name, best_conf = full_name, full_conf

        if best_conf < conf_threshold:
            # No vehicle-class object found at all — likely a pedestrian, parked
            # bike, shadow, or other noise blob. Reject the crossing entirely
            # instead of mislabeling it "Other".
            return False

        category = class_map.get(best_name, "Other")
        categories[category] = categories.get(category, 0) + 1
        job["categories"] = dict(categories)
        return True

    kwargs = {}
    if min_width is not None:
        kwargs["min_width"] = min_width
    if min_height is not None:
        kwargs["min_height"] = min_height

    run_counter(video_source, job, lines=lines, frame_sink=frame_sink,
                show_window=show_window, on_crossing=classify_crossing,
                display_max_width=display_max_width, **kwargs)
