import os
import time

from counter import run_counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF_THRESHOLD = 0.15
PAD = 60  # px of context padding around the crop sent to YOLO
WIDE_PAD = 160  # larger context padding used on re-analysis retries
UPSCALE_FACTOR = 1.6  # how much a re-analysis crop is enlarged before re-checking

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
                        display_max_width=1280, auto_speed=True, target_realtime_factor=1.0):
    """Full-speed line-crossing counting (counter.run_counter's blob tracker) with
    per-crossing vehicle classification: YOLO only runs on the small cropped region
    of a vehicle at the instant it crosses a line, not on every frame. This keeps
    throughput close to the plain counter while still reporting vehicle type per count.

    model_key: "bnvd" (Bangladesh-specific, covers Rickshaw/CNG/etc. — used by default
               if the model file is present) or "coco" (standard YOLOv8, generic classes).

    auto_speed: if True, the classifier watches its own real processing rate against
                the video's native playback rate. When it falls behind (busy footage,
                lots of crossings), it automatically switches to a smaller, faster
                classification pass; once it catches back up, it returns to full
                detail. This only affects the crop size sent to the classifier — the
                blob-tracker driving line-crossing detection always runs every frame,
                so no crossing is ever skipped.
    target_realtime_factor: >1 means "try to run faster than real playback speed by
                             this multiple" before backing off detail; 1.0 = just keep
                             up with the video's own frame rate.

    job keys written: same as counter.run_counter, plus "categories" (per-category
                       totals) and "speed_mode" (current auto-speed tier, for display).
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
    job["speed_mode"] = "full"
    job["reanalyzed"] = 0

    import cv2 as _cv2

    cap_probe = _cv2.VideoCapture(video_source)
    video_fps = cap_probe.get(_cv2.CAP_PROP_FPS) or 25.0
    cap_probe.release()

    # --- Auto-speed: track real wall-clock throughput against the video's own
    # frame rate. When classification is keeping the run behind schedule, shrink
    # the crop resolution sent to YOLO (faster per-call, still runs every
    # crossing — no crossings are ever skipped, unlike naive frame-skipping).
    speed_state = {"mode": "full", "wall_start": time.time(), "video_frames_seen": 0}
    SPEED_TIERS = ["full", "reduced", "fast"]
    TIER_IMGSZ = {"full": None, "reduced": 480, "fast": 320}

    def update_speed_mode(frame_idx_now):
        if not auto_speed:
            return
        speed_state["video_frames_seen"] = frame_idx_now
        elapsed_wall = time.time() - speed_state["wall_start"]
        if elapsed_wall < 3:
            return  # not enough signal yet
        video_seconds_covered = frame_idx_now / video_fps
        # >1 means we're processing faster than the video plays; <1 means behind.
        realtime_ratio = video_seconds_covered / elapsed_wall
        current = speed_state["mode"]
        idx = SPEED_TIERS.index(current)
        if realtime_ratio < target_realtime_factor * 0.7 and idx < len(SPEED_TIERS) - 1:
            speed_state["mode"] = SPEED_TIERS[idx + 1]
        elif realtime_ratio > target_realtime_factor * 1.3 and idx > 0:
            speed_state["mode"] = SPEED_TIERS[idx - 1]
        job["speed_mode"] = speed_state["mode"]

    def best_vehicle_in(image, imgsz=None):
        kwargs = {"imgsz": imgsz} if imgsz else {}
        results = model(image, verbose=False, **kwargs)[0]
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
        imgsz = TIER_IMGSZ[speed_state["mode"]]

        x1, y1 = max(0, x - PAD), max(0, y - PAD)
        x2, y2 = min(fw, x + w + PAD), min(fh, y + h + PAD)
        crop = frame[y1:y2, x1:x2]

        best_name, best_conf = (None, 0.0) if crop.size == 0 else best_vehicle_in(crop, imgsz)

        # Stage 2: crop missed it (too tight, motion blur, edge of frame) — retry
        # on the full frame before giving up.
        if best_conf < conf_threshold:
            full_name, full_conf = best_vehicle_in(frame, imgsz)
            if full_conf > best_conf:
                best_name, best_conf = full_name, full_conf

        # Stage 3: still not confident — re-analyze with a wider, upscaled crop.
        # This is the "re-analyse the footage again" pass: a bigger window of
        # context plus enlarging the crop helps small/distant/blurry vehicles
        # that a tight or same-scale look missed. Always runs at full detail
        # regardless of the current speed tier, since this only fires rarely
        # (on genuinely ambiguous detections), not on every crossing.
        if best_conf < conf_threshold:
            wx1, wy1 = max(0, x - WIDE_PAD), max(0, y - WIDE_PAD)
            wx2, wy2 = min(fw, x + w + WIDE_PAD), min(fh, y + h + WIDE_PAD)
            wide_crop = frame[wy1:wy2, wx1:wx2]
            if wide_crop.size != 0:
                new_w = int(wide_crop.shape[1] * UPSCALE_FACTOR)
                new_h = int(wide_crop.shape[0] * UPSCALE_FACTOR)
                upscaled = _cv2.resize(wide_crop, (new_w, new_h), interpolation=_cv2.INTER_CUBIC)
                wide_name, wide_conf = best_vehicle_in(upscaled)
                if wide_conf > best_conf:
                    best_name, best_conf = wide_name, wide_conf
                    job["reanalyzed"] = job.get("reanalyzed", 0) + 1

        if best_conf < conf_threshold:
            # No vehicle-class object found at all after re-analysis — likely a
            # pedestrian, parked bike, shadow, or other noise blob. Reject the
            # crossing entirely instead of mislabeling it "Other".
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

    if auto_speed:
        import threading

        def speed_monitor():
            while not job.get("done"):
                update_speed_mode(job.get("frame_idx", 0))
                time.sleep(1.0)

        threading.Thread(target=speed_monitor, daemon=True).start()

    run_counter(video_source, job, lines=lines, frame_sink=frame_sink,
                show_window=show_window, on_crossing=classify_crossing,
                display_max_width=display_max_width, **kwargs)
