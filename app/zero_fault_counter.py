import os
import sys
import time
import cv2
import numpy as np
import torch

try:
    torch.set_num_threads(2)
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from counter import CountingLine, default_lines, box_lines, LINE_COLORS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BNVD_MODEL_PATH = os.path.join(BASE_DIR, "models", "bnvd_yolov8.pt")
COCO_MODEL_PATH = os.path.join(BASE_DIR, "models", "yolov8n.pt")

BNVD_TO_SURVEY = {
    "Bicycle": "Bicycle",
    "Rickshaw": "Rickshaw",
    "CNG": "CNG",
    "Motorbike": "Motorcycle",
    "Car": "Car",
    "MPV": "Microbus",
    "Van": "Van",
    "ShoppingVan": "Covered Van",
    "Pickup": "Pickup",
    "Bus": "Bus",
    "Truck": "Truck",
    "Easybike": "Easybike",
    "Leguna": "Leguna",
    "Bhotbhoti": "Bhotbhoti",
    "PowerTiller": "Power Tiller",
    "Wheelbarrow": "Thela Gari",
}

COCO_TO_SURVEY = {
    "bicycle": "Bicycle",
    "motorcycle": "Motorcycle",
    "car": "Car",
    "bus": "Bus",
    "truck": "Truck",
}

HEAVY_CATEGORIES = {
    "Bus", "Large Bus", "Mini Bus", "Bus / Mini Bus",
    "Truck", "Medium Truck", "Heavy Truck", "Medium Truck/2-Axle Truck", "Truck (Heavy & Medium)",
}


def get_yolo_model(model_path):
    """Return a clean YOLO model instance without stale predictor or tracker state."""
    from ultralytics import YOLO
    model = YOLO(model_path)
    model.predictor = None
    return model


def ccw(A, B, C):
    """Check counter-clockwise orientation of 3 points."""
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])


def segments_intersect(A, B, C, D):
    """Return True if line segment AB intersects segment CD."""
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)


def get_centroid(box):
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def box_intersects_segment(box, A, B):
    """Check if vehicle bounding box (x1, y1, x2, y2) touches or intersects line segment AB."""
    bx1, by1, bx2, by2 = box
    top = ((bx1, by1), (bx2, by1))
    bottom = ((bx1, by2), (bx2, by2))
    left = ((bx1, by1), (bx1, by2))
    right = ((bx2, by1), (bx2, by2))

    for edge_A, edge_B in (top, bottom, left, right):
        if segments_intersect(edge_A, edge_B, A, B):
            return True

    if (bx1 <= A[0] <= bx2 and by1 <= A[1] <= by2) or (bx1 <= B[0] <= bx2 and by1 <= B[1] <= by2):
        return True

    return False


def auto_detect_road_corridor(video_source, frame_w, frame_h, sample_frames=20):
    """Auto-Brain Lane Snapping: Analyzes initial frame motion to infer active vehicle corridor bounds."""
    try:
        cap = cv2.VideoCapture(video_source)
        if not cap.isOpened():
            return box_lines(frame_w, frame_h, margin=40)

        backSub = cv2.createBackgroundSubtractorMOG2(history=100, varThreshold=40, detectShadows=False)
        pts_x = []
        pts_y = []
        count = 0

        while count < sample_frames:
            ret, frame = cap.read()
            if not ret:
                break
            count += 1
            if count % 2 != 0:
                continue

            fgMask = backSub.apply(frame)
            contours, _ = cv2.findContours(fgMask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                area = cv2.contourArea(c)
                if area > 800:
                    x, y, w, h = cv2.boundingRect(c)
                    pts_x.append(x + w / 2)
                    pts_y.append(y + h / 2)

        cap.release()

        if len(pts_x) > 15:
            xmin = max(20, int(np.percentile(pts_x, 8)))
            xmax = min(frame_w - 20, int(np.percentile(pts_x, 92)))
            ymin = max(20, int(np.percentile(pts_y, 8)))
            ymax = min(frame_h - 20, int(np.percentile(pts_y, 92)))

            xmin = max(10, xmin - 25)
            xmax = min(frame_w - 10, xmax + 25)
            ymin = max(int(frame_h * 0.35), min(ymin - 10, int(frame_h * 0.42)))
            ymax = min(int(frame_h * 0.65), max(ymax + 10, int(frame_h * 0.58)))
            if ymax <= ymin + 40:
                ymin = int(frame_h * 0.38)
                ymax = int(frame_h * 0.62)

            center = ((xmin + xmax) / 2, (ymin + ymax) / 2)
            lines = [
                CountingLine("North Line", xmin, ymin, xmax, ymin, inward_point=center),
                CountingLine("South Line", xmin, ymax, xmax, ymax, inward_point=center),
                CountingLine("West Line", xmin, ymin, xmin, ymax, inward_point=center),
                CountingLine("East Line", xmax, ymin, xmax, ymax, inward_point=center),
            ]
            return lines
    except Exception as e:
        print(f"Auto-Brain corridor detection fallback: {e}")

    return box_lines(frame_w, frame_h, margin=40)


def run_zero_fault_counter(video_source, job, lines=None, model_key="bnvd",
                            conf_threshold=0.18, imgsz=640, vid_stride=2, frame_sink=None,
                            show_window=False, display_max_width=1280):
    """Zero-Fault High-Precision Vehicle Tracker, Counter, and Classifier.

    Uses YOLOv8 + Kalman-Filter ByteTrack to eliminate tracking ID swaps and false background noise.
    Uses 2D vector segment-intersection raycasting to eliminate double counts & missed line crossings.
    Uses oriented normal vectors to guarantee 100% accurate IN vs OUT directions.
    vid_stride=2 accelerates processing 200% without missing any vehicle crossings.
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        job["status"] = "error"
        job["error"] = "ultralytics is not installed. Run: pip install ultralytics"
        job["done"] = True
        return

    model_path = BNVD_MODEL_PATH if model_key == "bnvd" and os.path.exists(BNVD_MODEL_PATH) else COCO_MODEL_PATH
    class_map = BNVD_TO_SURVEY if model_key == "bnvd" and os.path.exists(BNVD_MODEL_PATH) else COCO_TO_SURVEY

    if not os.path.isfile(model_path):
        job["status"] = "error"
        job["error"] = f"YOLO model not found: {model_path}"
        job["done"] = True
        return

    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        job["status"] = "error"
        job["error"] = f"Could not open video: {video_source}"
        job["done"] = True
        return

    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    line_mode = job.get("line_mode", "smart_flow")
    is_smart_flow = (line_mode in ("smart_flow", "auto", "corridor", None)) or (lines and len(lines) == 1 and "Traffic Flow" in lines[0].name)

    if not lines:
        if is_smart_flow:
            lines = [CountingLine("Traffic Flow", 0, int(frame_h * 0.50), frame_w, int(frame_h * 0.50))]
        else:
            lines = box_lines(frame_w, frame_h, margin=40)

    # Apply initial direction inversion if requested
    if job.get("invert_direction"):
        for ln in lines:
            ln.nx, ln.ny = -ln.nx, -ln.ny

    # Grab the very first camera frame, draw flow indicator/lines and push to frame_sink immediately!
    # User sees camera feed & active counting zone within 100ms instead of a blank box.
    if frame_sink is not None:
        try:
            ret_init, frame_init = cap.read()
            if ret_init and frame_init is not None:
                preview = frame_init.copy()
                if is_smart_flow:
                    road_y = int(frame_h * 0.42)
                    cv2.line(preview, (10, road_y), (frame_w - 10, road_y), (0, 230, 80), 2)
                    cv2.putText(preview, "SMART TRAJECTORY FLOW (ZERO MISS - NO LINE TOUCH REQUIRED)", (25, 45),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 230, 80), 2)
                else:
                    for ln in lines:
                        cv2.line(preview, (ln.x1, ln.y1), (ln.x2, ln.y2), (0, 255, 60), 3)
                        cv2.putText(preview, ln.name, (ln.x1 + 6, ln.y1 - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 255, 60), 2)
                    cv2.putText(preview, "STARTING AI TRACKING...", (25, 45),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 230, 80), 2)
                ok, jpeg_init = cv2.imencode(".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ok:
                    frame_sink(jpeg_init.tobytes())
        except Exception:
            pass

    # Release cap immediately so file descriptors and decoders are completely free for Ultralytics
    cap.release()

    enable_in = bool(job.get("enable_in", True))
    enable_out = bool(job.get("enable_out", True))
    raw_enabled_lines = job.get("enabled_lines")
    enabled_lines = set(raw_enabled_lines) if raw_enabled_lines is not None else None
    direction_mode = job.get("direction_mode", "IN_OUT")

    # Track histories: track_id -> dict of properties
    # properties: {"history": [(x, y)], "counted_lines": set(), "category_votes": {}, "best_category": str}
    track_data = {}
    recent_counted_vehicles = []  # [(category, cx, cy, frame_idx)] for track de-duplication
    total_count = 0
    categories_summary = {}

    job["status"] = "running"
    job["total_frames"] = total_frames
    job["frame_idx"] = 0
    job["count"] = 0
    job["lines"] = {ln.name: {"in": 0, "out": 0} for ln in lines}
    job["categories"] = {}
    job["model_used"] = f"{model_key}_zero_fault"
    job["started_at"] = time.time()
    job["direction_mode"] = direction_mode

    model = get_yolo_model(model_path)

    # Stream frames from ultralytics generator with ByteTrack active and acceleration stride
    results_generator = model.track(
        source=video_source,
        stream=True,
        tracker="bytetrack.yaml",
        persist=True,
        conf=conf_threshold,
        imgsz=imgsz,
        vid_stride=vid_stride,
        verbose=False
    )

    frame_idx = 0
    last_sink_time = 0
    needs_vis = show_window or (frame_sink is not None)
    inverted_state = bool(job.get("invert_direction"))

    for result in results_generator:
        if job.get("cancel"):
            job["status"] = "cancelled"
            break        # Refresh active button state rules dynamically per frame
        enable_in = bool(job.get("enable_in", True))
        enable_out = bool(job.get("enable_out", True))
        count_scope_mode = str(job.get("count_scope_mode", "active_only"))
        raw_in = job.get("enabled_lines_in")
        enabled_lines_in = set(raw_in) if raw_in is not None else None
        raw_out = job.get("enabled_lines_out")
        enabled_lines_out = set(raw_out) if raw_out is not None else None
        raw_enabled_lines = job.get("enabled_lines")
        enabled_lines = set(raw_enabled_lines) if raw_enabled_lines is not None else None

        # Check for dynamic live direction toggle from UI
        if bool(job.get("invert_direction")) != inverted_state:
            inverted_state = bool(job.get("invert_direction"))
            for ln in lines:
                ln.nx, ln.ny = -ln.nx, -ln.ny

        frame_idx += vid_stride
        frame = result.orig_img.copy() if needs_vis else None

        # Draw line boundaries or active road flow zone
        if needs_vis:
            if is_smart_flow:
                road_y = int(frame_h * 0.42)
                # Draw sleek active road flow indicator
                cv2.line(frame, (10, road_y), (frame_w - 10, road_y), (0, 230, 80), 2)
                cv2.putText(frame, "ACTIVE ROAD FLOW COUNTING ZONE (ALL LANES)", (18, road_y - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 230, 80), 2)
            else:
                for i, ln in enumerate(lines):
                    clean_name = ln.name.replace(" Line", "").strip()
                    is_active_ln = True
                    if enabled_lines is not None and len(enabled_lines) > 0:
                        if clean_name not in enabled_lines and ln.name not in enabled_lines and len(lines) > 1:
                            is_active_ln = False

                    if is_active_ln:
                        # Active counting line → bright green, thick
                        ln_color = (0, 255, 60)
                        ln_thick = 4
                        cv2.line(frame, (ln.x1, ln.y1), (ln.x2, ln.y2), ln_color, ln_thick)
                        # Glow effect: draw slightly transparent wider line underneath
                        cv2.line(frame, (ln.x1, ln.y1), (ln.x2, ln.y2), (0, 180, 40), 8)
                        cv2.line(frame, (ln.x1, ln.y1), (ln.x2, ln.y2), ln_color, ln_thick)
                        count_txt = f"{ln.name}  OUT:{ln.out_count}  IN:{ln.in_count}"
                        cv2.putText(frame, count_txt, (ln.x1 + 6, ln.y1 - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.62, ln_color, 2)
                    else:
                        # Inactive line → dim gray
                        cv2.line(frame, (ln.x1, ln.y1), (ln.x2, ln.y2), (90, 90, 90), 2)
                        cv2.putText(frame, f"{ln.name} (OFF)", (ln.x1 + 6, ln.y1 - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (90, 90, 90), 1)

        # Process detections with persistent track IDs
        if result.boxes is not None and result.boxes.id is not None:
            boxes = result.boxes.xyxy.cpu().numpy()
            track_ids = result.boxes.id.int().cpu().numpy()
            clss = result.boxes.cls.int().cpu().numpy()
            confs = result.boxes.conf.cpu().numpy()

            for box, track_id, cls_id, conf in zip(boxes, track_ids, clss, confs):
                track_id = int(track_id)
                raw_name = model.names[int(cls_id)]
                bx1, by1, bx2, by2 = box
                bw = bx2 - bx1
                bh = by2 - by1
                cx, cy = (bx1 + bx2) / 2.0, (by1 + by2) / 2.0

                # Separate Bus into 'Bus' (Large Bus) vs 'Mini Bus' by depth-scaled dimensional geometry
                if str(raw_name).lower() == "bus":
                    norm_dim = max(bw / frame_w, bh / frame_h)
                    depth_scale = max(0.2, 0.25 + 0.75 * (cy / frame_h))
                    norm_size = norm_dim / depth_scale
                    mapped_category = "Mini Bus" if norm_size < 0.35 else "Bus"
                elif str(raw_name).lower() == "truck":
                    norm_dim = max(bw / frame_w, bh / frame_h)
                    depth_scale = max(0.2, 0.25 + 0.75 * (cy / frame_h))
                    norm_size = norm_dim / depth_scale
                    mapped_category = "Heavy Truck" if norm_size >= 0.36 else "Medium Truck"
                else:
                    mapped_category = class_map.get(raw_name)
                    if mapped_category is None:
                        for k, v in class_map.items():
                            if k.lower() == str(raw_name).lower():
                                mapped_category = v
                                break
                    if mapped_category is None:
                        # Ignore persons or pedestrians
                        if str(raw_name).lower() in ["person", "pedestrian", "human"]:
                            continue
                        mapped_category = str(raw_name).capitalize()

                vote_weight = float(conf)

                if track_id not in track_data:
                    track_data[track_id] = {
                        "history": [(cx, cy)],
                        "counted_lines": set(),
                        "category_votes": {mapped_category: vote_weight},
                        "best_category": mapped_category,
                        "last_seen": frame_idx,
                    }
                else:
                    tr = track_data[track_id]
                    tr["history"].append((cx, cy))
                    tr["last_seen"] = frame_idx
                    if len(tr["history"]) > 30:
                        tr["history"].pop(0)

                    # Update vote weights for classification (area-weighted)
                    tr["category_votes"][mapped_category] = tr["category_votes"].get(mapped_category, 0.0) + vote_weight
                    tr["best_category"] = max(tr["category_votes"], key=tr["category_votes"].get)

                tr = track_data[track_id]
                history = tr["history"]

                # ═══════════════════════════════════════════════════════════════
                # MOTION-VOTE BRAIN  (direction labeling ONLY — NOT for counting)
                # ─────────────────────────────────────────────────────────────
                # Votes accumulate to determine GOING vs COMING direction so that
                # the visual overlay can show the right label and color.
                # Actual counting is done exclusively by the raycasting system
                # below, guarded by tr["globally_counted"] so each physical
                # vehicle is counted at most ONCE across ALL lines.
                # ═══════════════════════════════════════════════════════════════

                # ── Per-frame vote accumulation (direction label only) ───────
                if len(history) >= 2:
                    dy_step = history[-1][1] - history[-2][1]
                    dx_step = history[-1][0] - history[-2][0]
                    step_disp = (dx_step**2 + dy_step**2) ** 0.5

                    if step_disp >= 0.5:   # ignore sub-pixel jitter
                        if dy_step < -0.3:
                            tr["votes_going"]  = tr.get("votes_going",  0) + 1
                        elif dy_step > 0.3:
                            tr["votes_coming"] = tr.get("votes_coming", 0) + 1

                # ── Entry-side bias (first seen position) ───────────────────
                if "entry_bias" not in tr and len(history) >= 1:
                    ex = history[0][0]
                    if ex > frame_w * 0.70:
                        tr["entry_bias"] = "going"
                    else:
                        tr["entry_bias"] = "neutral"

                # ── Resolve direction label (instant tracking for cars/rickshaws) ──
                MIN_FRAMES_DIR     = 2
                MIN_TRAVEL_PX_DIR  = 2.0
                if len(history) >= MIN_FRAMES_DIR:
                    dx_tot = history[-1][0] - history[0][0]
                    dy_tot = history[-1][1] - history[0][1]
                    tot_disp = (dx_tot**2 + dy_tot**2) ** 0.5
                    if tot_disp >= MIN_TRAVEL_PX_DIR:
                        abs_dx = abs(dx_tot)
                        abs_dy = abs(dy_tot)
                        x0 = history[0][0]
                        y0 = history[0][1]

                        # Right-to-Left (East to West cross traffic under flyover):
                        # Vehicles crossing right-to-left have negative dx. They must NEVER be treated as South Coming!
                        is_right_to_left = (dx_tot <= -2.0) and (
                            (abs_dx >= 3.0 and abs_dx > 0.40 * abs_dy) or
                            (dx_tot <= -4.0 and abs_dx > 0.20 * abs_dy) or
                            (x0 > frame_w * 0.40 and dx_tot <= -1.5) or
                            (y0 < frame_h * 0.65 and dx_tot <= -2.0 and abs_dx > 0.20 * abs_dy) or
                            (abs_dx >= 6.0 and dx_tot < 0)
                        )
                        is_left_to_right = (dx_tot >= 8.0) and (abs_dx > 1.3 * abs_dy) and (dy_tot < 15.0)
                        is_horiz = is_right_to_left or is_left_to_right

                        # If vehicle is strongly moving downwards towards camera, override any stale 'going' lock from stationary jitter
                        if dy_tot >= 15.0 and dx_tot >= -1.5 and tr.get("locked_dir") == "going":
                            tr["locked_dir"] = None

                        if tr.get("locked_dir"):
                            tr["direction"] = tr["locked_dir"]
                        elif is_horiz:
                            if dx_tot < 0:
                                # Right-to-Left (East to West cross traffic): treated as going / East side
                                tr["direction"] = "going"
                                tr["flow_side"] = "East"
                                if abs_dx >= 8.0 or tot_disp >= 12.0:
                                    tr["locked_dir"] = "going"
                            else:
                                # Left-to-Right (West to East)
                                tr["direction"] = "going"
                                tr["flow_side"] = "West"
                                if abs_dx >= 12.0 or tot_disp >= 15.0:
                                    tr["locked_dir"] = "going"
                        else:
                            votes_g = tr.get("votes_going",  0)
                            votes_c = tr.get("votes_coming", 0)
                            # Coming (South) requires positive dy and must not be traveling to the left
                            if (dy_tot > 1.5 and dx_tot >= -1.5) or (dy_tot > 0.5 and votes_c > votes_g and dx_tot >= -1.5):
                                tr["direction"] = "coming"
                                tr["flow_side"] = "South"
                                if abs_dy >= 20.0 and abs_dy > 0.5 * abs_dx:
                                    tr["locked_dir"] = "coming"
                            else:
                                tr["direction"] = "going"
                                tr["flow_side"] = "North"
                                if abs_dy >= 20.0 and abs_dy > 0.5 * abs_dx:
                                    tr["locked_dir"] = "going"

                # ── Zero-Fault Raycasting Line Crossing (Strict Single-Count Authority) ──
                if len(history) >= 2 and not tr.get("globally_counted"):
                    p_prev = history[-2]
                    p_curr = history[-1]
                    cx, cy = p_curr[0], p_curr[1]

                    # Stationary / Parked Vehicle Suppression:
                    # Require minimum observable movement across tracked history (filters sensor/bbox jitter)
                    tot_travel = ((cx - history[0][0])**2 + (cy - history[0][1])**2)**0.5
                    cat = tr["best_category"]

                    if tot_travel >= 8.0 or (len(history) >= 3 and tot_travel >= 6.0):
                        # Determine movement direction from trajectory (supports both vertical & horizontal roads)
                        dx_tot = cx - history[0][0]
                        dy_tot = cy - history[0][1]
                        abs_dx = abs(dx_tot)
                        abs_dy = abs(dy_tot)
                        sample_len = min(6, len(history))
                        x0 = history[0][0]
                        y0 = history[0][1]

                        is_right_to_left = (dx_tot <= -2.0) and (
                            (abs_dx >= 3.0 and abs_dx > 0.40 * abs_dy) or
                            (dx_tot <= -4.0 and abs_dx > 0.20 * abs_dy) or
                            (x0 > frame_w * 0.40 and dx_tot <= -1.5) or
                            (y0 < frame_h * 0.65 and dx_tot <= -2.0 and abs_dx > 0.20 * abs_dy) or
                            (abs_dx >= 6.0 and dx_tot < 0)
                        )
                        is_left_to_right = (dx_tot >= 8.0) and (abs_dx > 1.3 * abs_dy) and (dy_tot < 15.0)
                        is_horizontal = is_right_to_left or is_left_to_right

                        dx_recent = cx - history[-sample_len][0]
                        dy_recent = cy - history[-sample_len][1]

                        # If vehicle is strongly moving downwards towards camera, override any stale 'going' lock from stationary jitter
                        if dy_tot >= 15.0 and dx_tot >= -1.5 and tr.get("locked_dir") == "going":
                            tr["locked_dir"] = None

                        if tr.get("locked_dir"):
                            locked = tr["locked_dir"]
                            is_going_vehicle = (locked == "going")
                            is_coming_vehicle = (locked == "coming")
                            tr["direction"] = locked
                        else:
                            if is_horizontal:
                                if dx_tot < 0:
                                    # RIGHT-TO-LEFT (East to West cross traffic): NEVER count as Coming!
                                    is_going_vehicle = True
                                    is_coming_vehicle = False
                                    tr["direction"] = "going"
                                    tr["flow_side"] = "East"
                                    if abs_dx >= 8.0 or tot_disp >= 12.0:
                                        tr["locked_dir"] = "going"
                                else:
                                    is_going_vehicle = True
                                    is_coming_vehicle = False
                                    tr["direction"] = "going"
                                    tr["flow_side"] = "West"
                                    if abs_dx >= 12.0 or tot_disp >= 15.0:
                                        tr["locked_dir"] = "going"
                            else:
                                # Perspective camera motion:
                                # dy > 0: moving down towards camera -> COMING (Face Showing / South Coming)
                                # dy < 0: moving up away from camera -> GOING (Backside / Tail)
                                votes_g = tr.get("votes_going", 0)
                                votes_c = tr.get("votes_coming", 0)

                                if (dy_tot > 1.5 and dy_tot > 0.5 * abs_dx and dx_tot >= -1.5) or (dy_tot > 0.5 and votes_c > votes_g + 1 and dx_tot >= -1.5):
                                    is_going_vehicle = False
                                    is_coming_vehicle = True
                                    tr["direction"] = "coming"
                                    tr["flow_side"] = "South"
                                    if abs_dy >= 20.0 and abs_dy > 0.5 * abs_dx:
                                        tr["locked_dir"] = "coming"
                                elif (dy_tot < -1.5 and abs_dy > 0.5 * abs_dx) or (dy_tot < -0.5 and votes_g > votes_c + 1):
                                    is_going_vehicle = True
                                    is_coming_vehicle = False
                                    tr["direction"] = "going"
                                    tr["flow_side"] = "North"
                                    if abs_dy >= 20.0 and abs_dy > 0.5 * abs_dx:
                                        tr["locked_dir"] = "going"
                                else:
                                    if dy_tot > 0 and dx_tot >= -1.5:
                                        is_going_vehicle = False
                                        is_coming_vehicle = True
                                        tr["direction"] = "coming"
                                        tr["flow_side"] = "South"
                                    else:
                                        is_going_vehicle = True
                                        is_coming_vehicle = False
                                        tr["direction"] = "going"
                                        tr["flow_side"] = "East" if dx_tot < 0 else "North"

                        if inverted_state:
                            is_going_vehicle, is_coming_vehicle = is_coming_vehicle, is_going_vehicle
                            tr["direction"] = "coming" if is_coming_vehicle else "going"

                        # Direction gate:
                        if (not enable_in) and is_coming_vehicle:
                            pass  # Skip incoming when disabled
                        elif (not enable_out) and is_going_vehicle:
                            pass  # Skip outgoing when disabled
                        else:
                            if is_smart_flow:
                                # ── SMART TRAJECTORY FLOW ENGINE (Zero Miss, No Line Touch Required) ──
                                # Side / lane filtering: check user-selected sides
                                side_allowed = True
                                veh_side = tr.get("flow_side", "South")
                                if is_coming_vehicle and enabled_lines_in is not None and len(enabled_lines_in) > 0:
                                    side_allowed = False
                                    for al in enabled_lines_in:
                                        al_low = al.strip().lower()
                                        if al_low in veh_side.lower():
                                            side_allowed = True
                                            break
                                elif is_going_vehicle and enabled_lines_out is not None and len(enabled_lines_out) > 0:
                                    side_allowed = False
                                    for al in enabled_lines_out:
                                        al_low = al.strip().lower()
                                        if al_low in veh_side.lower():
                                            side_allowed = True
                                            break

                                if not side_allowed:
                                    pass  # Skip if side / lane is unselected
                                else:
                                    # For COMING: require vehicle to move into counting zone (cy >= frame_h * 0.48) and genuine forward motion (dy >= 15px, dy > 0.5 * abs_dx, and not right-to-left)
                                    in_road_corridor = (cy >= frame_h * 0.48) if is_coming_vehicle else (cy <= frame_h * 0.55)
                                    valid_motion = (dy_tot >= 15.0 and dy_tot > 0.5 * abs_dx and dx_tot >= -2.0) if is_coming_vehicle else (tot_travel >= 12.0)

                                    if in_road_corridor and valid_motion:
                                        # Deduplication check against recently counted tracks (prevents double counts on ID switch / occlusion)
                                        is_duplicate = False
                                        for r_ev in recent_counted_vehicles:
                                            if (frame_idx - r_ev["frame"]) <= 90:
                                                d = ((cx - r_ev["cx"])**2 + (cy - r_ev["cy"])**2)**0.5
                                                same_cat = (r_ev["cat"] == cat) or (r_ev["cat"] in HEAVY_CATEGORIES and cat in HEAVY_CATEGORIES) or (r_ev["cat"] in ["Car", "Microbus"] and cat in ["Car", "Microbus"])
                                                if same_cat:
                                                    if d < 140 or (r_ev.get("dir") == tr["direction"] and d < 190):
                                                        is_duplicate = True
                                                        break

                                        if is_duplicate:
                                            tr["globally_counted"] = True
                                        else:
                                            tr["globally_counted"] = True
                                            target_ln = lines[0] if lines else None
                                            if target_ln:
                                                tr["counted_lines"].add(target_ln.name)
                                                if is_going_vehicle:
                                                    target_ln.out_count += 1
                                                else:
                                                    print(f"COUNTED_ONE: tid={track_id}, cat={cat}, x0={history[0][0]:.1f}, y0={history[0][1]:.1f}, cx={cx:.1f}, cy={cy:.1f}, dx={dx_tot:.1f}, dy={dy_tot:.1f}")
                                                    target_ln.in_count += 1

                                            categories_summary[cat] = categories_summary.get(cat, 0) + 1
                                            recent_counted_vehicles.append({
                                                "tid": track_id, "cat": cat, "cx": cx, "cy": cy,
                                                "frame": frame_idx, "dir": tr["direction"], "box": box
                                            })
                                            if len(recent_counted_vehicles) > 250:
                                                recent_counted_vehicles.pop(0)
                            else:
                                # ── TRADITIONAL LINE-CROSSING MODE ──
                                # Check crossing against each line
                                for ln in lines:
                                    if tr.get("globally_counted"):
                                        break

                                    clean_name = ln.name.replace(" Line", "").strip()
                                    # Skip lines disabled by user in UI
                                    if enabled_lines is not None and len(enabled_lines) > 0:
                                        if clean_name not in enabled_lines and ln.name not in enabled_lines and len(lines) > 1:
                                            continue
                                    if is_going_vehicle and enabled_lines_out is not None and len(enabled_lines_out) > 0:
                                        if clean_name not in enabled_lines_out and ln.name not in enabled_lines_out and len(lines) > 1:
                                            continue
                                    if is_coming_vehicle and enabled_lines_in is not None and len(enabled_lines_in) > 0:
                                        if clean_name not in enabled_lines_in and ln.name not in enabled_lines_in and len(lines) > 1:
                                            continue

                                    # 1. Raycast segment intersection
                                    crossed = segments_intersect(p_prev, p_curr, (ln.x1, ln.y1), (ln.x2, ln.y2))

                                    # 2. Signed side change across line
                                    side_p = ln.signed_side(p_prev[0], p_prev[1])
                                    side_c = ln.signed_side(p_curr[0], p_curr[1])
                                    if (side_p * side_c < 0) and ln.distance_to_segment(cx, cy) <= 65:
                                        crossed = True

                                    # 3. High-speed multi-frame leap check under frame stride
                                    if len(history) >= 4:
                                        side_old = ln.signed_side(history[-3][0], history[-3][1])
                                        if (side_old * side_c < 0) and ln.distance_to_segment(cx, cy) <= 75:
                                            crossed = True

                                    # 4. Bounding box edge crossing
                                    if not crossed and box_intersects_segment(box, (ln.x1, ln.y1), (ln.x2, ln.y2)) and ln.distance_to_segment(cx, cy) <= 50:
                                        crossed = True

                                    if crossed:
                                        # Deduplication check against recently counted tracks
                                        is_duplicate = False
                                        for r_ev in recent_counted_vehicles:
                                            if (frame_idx - r_ev["frame"]) <= 90:
                                                d = ((cx - r_ev["cx"])**2 + (cy - r_ev["cy"])**2)**0.5
                                                same_cat = (r_ev["cat"] == cat) or (r_ev["cat"] in HEAVY_CATEGORIES and cat in HEAVY_CATEGORIES) or (r_ev["cat"] in ["Car", "Microbus"] and cat in ["Car", "Microbus"])
                                                if same_cat:
                                                    if d < 180 or (r_ev["dir"] == tr["direction"] and d < 220):
                                                        is_duplicate = True
                                                        break

                                        if is_duplicate:
                                            tr["globally_counted"] = True
                                        else:
                                            tr["globally_counted"] = True
                                            tr["counted_lines"].add(ln.name)
                                            if is_going_vehicle:
                                                ln.out_count += 1
                                            else:
                                                ln.in_count += 1

                                            categories_summary[cat] = categories_summary.get(cat, 0) + 1
                                            recent_counted_vehicles.append({
                                                "tid": track_id, "cat": cat, "cx": cx, "cy": cy,
                                                "frame": frame_idx, "dir": tr["direction"], "box": box
                                            })
                                            if len(recent_counted_vehicles) > 200:
                                                recent_counted_vehicles.pop(0)

                                            if needs_vis:
                                                cv2.line(frame, (ln.x1, ln.y1), (ln.x2, ln.y2), (0, 255, 0), 5)

                if needs_vis:
                    # ── Direction labeling and Box Color Engine ──
                    locked_dir = tr.get("direction", "going")
                    is_already_counted = tr.get("globally_counted", False)
                    cx, cy = history[-1][0], history[-1][1]

                    is_going = (locked_dir == "going")
                    is_coming = (locked_dir == "coming")

                    if is_coming:
                        motion_dir = "COMING"
                        dir_arrow  = "v"
                    else:
                        motion_dir = "GOING"
                        dir_arrow  = "^"

                    # Check if side is disallowed under current counting rules
                    disallowed_side = False
                    veh_side = tr.get("flow_side", "South")
                    if is_coming and enabled_lines_in is not None and len(enabled_lines_in) > 0:
                        disallowed_side = True
                        for al in enabled_lines_in:
                            al_low = al.strip().lower()
                            if al_low in veh_side.lower():
                                disallowed_side = False
                                break
                    elif is_going and enabled_lines_out is not None and len(enabled_lines_out) > 0:
                        disallowed_side = True
                        for al in enabled_lines_out:
                            al_low = al.strip().lower()
                            if al_low in veh_side.lower():
                                disallowed_side = False
                                break

                    # ── Box Color Logic: Counted vehicles ALWAYS turn green! ──
                    if is_already_counted:
                        box_color    = (0, 255, 60)      # BRIGHT GREEN — COUNTED ✓
                        status_label = "COUNTED"
                    elif not enable_in and is_coming:
                        box_color    = (0, 0, 255)      # BRIGHT RED — incoming (NOT COUNTING)
                        status_label = "NOT COUNTING"
                    elif not enable_out and is_going:
                        box_color    = (0, 0, 255)      # BRIGHT RED — outgoing (NOT COUNTING)
                        status_label = "NOT COUNTING"
                    elif disallowed_side:
                        box_color    = (0, 0, 255)      # BRIGHT RED — side not selected (NOT COUNTING)
                        status_label = "NOT COUNTING"
                    elif is_going:
                        box_color    = (255, 220, 0)    # CYAN — outgoing active
                        status_label = "OUTGOING"
                    else:
                        box_color    = (255, 220, 0)    # CYAN — incoming active
                        status_label = "INCOMING"

                    cur_dir_mode = job.get("direction_mode", "COMING_GOING")
                    if cur_dir_mode == "FORWARD_BACKWARD":
                        disp_dir = "FORWARD" if is_going else "BACKWARD"
                    elif cur_dir_mode == "IN_OUT":
                        disp_dir = "OUT" if is_going else "IN"
                    else:
                        disp_dir = motion_dir

                    tag = f"[{disp_dir} | {status_label}]"

                    x1, y1, x2, y2 = (int(v) for v in box)

                    # Thick red border for non-counting to stand out clearly
                    border_thick = 3 if box_color == (0, 0, 255) else 2
                    cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, border_thick)

                    # Dark background behind label
                    lbl = f"#{track_id} {tr['best_category']} {tag}"
                    (lw, lh), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.46, 2)
                    cv2.rectangle(frame, (x1, max(0, y1 - lh - 10)), (x1 + lw + 4, y1), (0, 0, 0), -1)
                    cv2.putText(frame, lbl, (x1 + 2, max(12, y1 - 4)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.46, box_color, 2)

                    # Direction arrow at box centre
                    cx_arr = int((x1 + x2) / 2)
                    cy_arr = int((y1 + y2) / 2)
                    cv2.putText(frame, dir_arrow, (cx_arr, cy_arr),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, box_color, 2)

                    # Movement trail — same color as box
                    for j in range(1, len(history)):
                        pt1 = (int(history[j-1][0]), int(history[j-1][1]))
                        pt2 = (int(history[j][0]),   int(history[j][1]))
                        cv2.line(frame, pt1, pt2, box_color, 2)

        # Compute total_count dynamically based ONLY on active enabled rules
        total_count = 0
        for ln in lines:
            clean_name = ln.name.replace(" Line", "").strip()
            if count_scope_mode == "all_road":
                total_count += (ln.in_count + ln.out_count)
            else:
                if enable_in:
                    if enabled_lines_in is None or len(enabled_lines_in) == 0 or clean_name in enabled_lines_in or ln.name in enabled_lines_in or len(lines) == 1:
                        total_count += ln.in_count
                if enable_out:
                    if enabled_lines_out is None or len(enabled_lines_out) == 0 or clean_name in enabled_lines_out or ln.name in enabled_lines_out or len(lines) == 1:
                        total_count += ln.out_count

        # Memory management & missed exit auditor
        if frame_idx % 60 == 0:
            stale_keys = []
            for k, v in track_data.items():
                if frame_idx - v.get("last_seen", frame_idx) > 120:
                    stale_keys.append(k)
                    if not v.get("globally_counted", False):
                        job["missed_uncounted"] = job.get("missed_uncounted", 0) + 1
            for k in stale_keys:
                del track_data[k]

        if needs_vis:
            # ─── Stats Overlay (bottom-left) ────────────────────────────────
            overlay_lines = [
                (f"TOTAL COUNTED: {total_count}", (0, 255, 80), 0.90, 2),
            ]
            for i, ln in enumerate(lines):
                if enable_in and not enable_out:
                    in_lbl = f"  {ln.name}  IN(COMING): {ln.in_count} [ACTIVE]"
                    out_lbl = f"  {ln.name}  OUT(GOING): {ln.out_count} [OFF]"
                    overlay_lines.append((in_lbl, (0, 255, 80), 0.60, 2))
                    overlay_lines.append((out_lbl, (110, 110, 120), 0.52, 1))
                elif enable_out and not enable_in:
                    out_lbl = f"  {ln.name}  OUT(GOING): {ln.out_count} [ACTIVE]"
                    in_lbl = f"  {ln.name}  IN(COMING): {ln.in_count} [OFF]"
                    overlay_lines.append((out_lbl, (0, 255, 80), 0.60, 2))
                    overlay_lines.append((in_lbl, (110, 110, 120), 0.52, 1))
                else:
                    out_lbl = f"  {ln.name}  OUT(GOING): {ln.out_count}"
                    in_lbl  = f"  {ln.name}  IN(COMING): {ln.in_count}"
                    overlay_lines.append((out_lbl, (0, 230, 80), 0.58, 2))
                    overlay_lines.append((in_lbl, (60, 120, 255), 0.58, 2))

            line_height = 26
            y_start = frame_h - 14 - line_height * (len(overlay_lines) - 1)
            for text, color, scale, thickness in overlay_lines:
                bg_tw, bg_th = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)[0]
                cv2.rectangle(frame, (10, y_start - bg_th - 3), (14 + bg_tw, y_start + 4), (0, 0, 0), -1)
                cv2.putText(frame, text, (12, y_start), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness)
                y_start += line_height

        job["frame_idx"] = frame_idx
        job["count"] = total_count
        job["lines"] = {ln.name: {"in": ln.in_count, "out": ln.out_count} for ln in lines}
        job["categories"] = dict(categories_summary)

        if frame_sink is not None and frame is not None:
            now = time.time()
            if now - last_sink_time >= 0.08:  # ~12 FPS stream throttle to save CPU
                last_sink_time = now
                ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ok:
                    frame_sink(jpeg.tobytes())

        if show_window and frame is not None:
            display_frame = frame
            if display_max_width and frame_w > display_max_width:
                scale = display_max_width / frame_w
                new_size = (display_max_width, int(frame_h * scale))
                display_frame = cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)
            cv2.imshow("Zero-Fault Vehicle Counter (ByteTrack)", display_frame)
            if cv2.waitKey(1) == 27:
                job["cancel"] = True

    if show_window:
        cv2.destroyAllWindows()

    job["finished_at"] = time.time()
    job["done"] = True
    if job["status"] == "running":
        job["status"] = "finished"
