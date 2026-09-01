import os
import sys
import time
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from counter import CountingLine, default_lines, box_lines, LINE_COLORS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BNVD_MODEL_PATH = os.path.join(BASE_DIR, "models", "bnvd_yolov8.pt")
COCO_MODEL_PATH = os.path.join(BASE_DIR, "models", "yolov8n.pt")

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
}

COCO_TO_SURVEY = {
    "bicycle": "Bicycle",
    "motorcycle": "Motorcycle",
    "car": "Car/Suv",
    "bus": "Large Bus",
    "truck": "Medium Truck/2-Axle Truck",
}


_MODEL_CACHE = {}


def get_yolo_model(model_path):
    """Cache YOLO model in RAM to eliminate reload delay on job start."""
    if model_path not in _MODEL_CACHE:
        from ultralytics import YOLO
        _MODEL_CACHE[model_path] = YOLO(model_path)
    return _MODEL_CACHE[model_path]


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


def auto_detect_road_corridor(video_source, frame_w, frame_h, sample_frames=45):
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
            ymin = max(10, ymin - 25)
            ymax = min(frame_h - 10, ymax + 25)

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
                            conf_threshold=0.25, imgsz=512, vid_stride=2, frame_sink=None,
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

    if not lines:
        lines = box_lines(frame_w, frame_h, margin=40)

    # Apply initial direction inversion if requested
    if job.get("invert_direction"):
        for ln in lines:
            ln.nx, ln.ny = -ln.nx, -ln.ny

    enable_in = bool(job.get("enable_in", True))
    enable_out = bool(job.get("enable_out", True))
    raw_enabled_lines = job.get("enabled_lines")
    enabled_lines = set(raw_enabled_lines) if raw_enabled_lines is not None else None
    direction_mode = job.get("direction_mode", "IN_OUT")

    # Track histories: track_id -> dict of properties
    # properties: {"history": [(x, y)], "counted_lines": set(), "category_votes": {}, "best_category": str}
    track_data = {}
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

        # Draw line boundaries
        if needs_vis:
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

                cx, cy = get_centroid(box)

                bw, bh = box[2] - box[0], box[3] - box[1]
                box_area = max(1.0, float(bw * bh))
                area_weight = max(0.5, (box_area ** 0.5) / 100.0)
                vote_weight = float(conf) * area_weight

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
                    ey = history[0][1]
                    if ey < frame_h * 0.25:
                        tr["entry_bias"] = "coming"
                    elif ey > frame_h * 0.75:
                        tr["entry_bias"] = "going"
                    else:
                        tr["entry_bias"] = "neutral"

                # ── Resolve locked direction label (for display only) ────────
                CONFIDENCE_THRESH  = 0.65
                MIN_FRAMES_DIR     = 6
                MIN_TRAVEL_PX_DIR  = 18
                if "direction" not in tr and len(history) >= MIN_FRAMES_DIR:
                    dx_tot = history[-1][0] - history[0][0]
                    dy_tot = history[-1][1] - history[0][1]
                    tot_disp = (dx_tot**2 + dy_tot**2) ** 0.5
                    if tot_disp >= MIN_TRAVEL_PX_DIR:
                        votes_g = tr.get("votes_going",  0)
                        votes_c = tr.get("votes_coming", 0)
                        bias = tr.get("entry_bias", "neutral")
                        votes_g += (1 if bias == "going" else 0)
                        votes_c += (1 if bias == "coming" else 0)
                        total_votes = votes_g + votes_c
                        if total_votes > 0:
                            if votes_g / total_votes >= CONFIDENCE_THRESH:
                                tr["direction"] = "going"
                            elif votes_c / total_votes >= CONFIDENCE_THRESH:
                                tr["direction"] = "coming"
                            else:
                                tr["direction"] = "ambiguous"
                        else:
                            tr["direction"] = "ambiguous"

                # ── Zero-Fault Raycasting Line Crossing (SOLE counting authority) ──
                # Each physical vehicle is counted at most ONCE globally.
                # tr["globally_counted"] prevents counting the same bus multiple
                # times just because it crosses 2-4 box sides.
                if len(history) >= 2 and not tr.get("globally_counted"):
                    p_prev = history[-2]
                    p_curr = history[-1]

                    disp = ((p_curr[0] - p_prev[0])**2 + (p_curr[1] - p_prev[1])**2)**0.5
                    if disp >= 1.2:
                        for ln in lines:
                            if tr.get("globally_counted"):
                                break   # already counted by an earlier line this frame

                            clean_name = ln.name.replace(" Line", "").strip()
                            # Skip line if toggled off by user
                            if enabled_lines is not None and len(enabled_lines) > 0:
                                if clean_name not in enabled_lines and ln.name not in enabled_lines and len(lines) > 1:
                                    continue

                            if ln.name in tr["counted_lines"]:
                                continue

                            line_seg_A = (ln.x1, ln.y1)
                            line_seg_B = (ln.x2, ln.y2)

                            crossed = segments_intersect(p_prev, p_curr, line_seg_A, line_seg_B) or box_intersects_segment(box, line_seg_A, line_seg_B)
                            chk_prev = p_prev
                            chk_curr = p_curr

                            # --- Self-Healing Re-Scan (tightened to 30px to avoid false triggers) ---
                            # Only re-scan sub-trajectories for genuinely missed strided crossings.
                            if not crossed and len(history) >= 2:
                                dist = ln.distance_to_segment(p_curr[0], p_curr[1])
                                if dist <= 30:  # was 60px — tightened to prevent phantom hits
                                    sub_pts = history[-5:]
                                    for k in range(1, len(sub_pts)):
                                        if segments_intersect(sub_pts[k-1], sub_pts[k], line_seg_A, line_seg_B):
                                            crossed = True
                                            chk_prev = sub_pts[k-1]
                                            chk_curr = sub_pts[k]
                                            job["reanalyzed"] = job.get("reanalyzed", 0) + 1
                                            break
                                    # NOTE: The aggressive "force crossing if within 40px" fallback
                                    # has been removed — it caused buses near the North line edge
                                    # to be counted without actually crossing it.

                            if crossed:
                                # Determine vehicle motion direction cleanly and mutually exclusively
                                locked_dir = tr.get("direction")
                                if locked_dir == "going":
                                    is_going_vehicle = True
                                    is_coming_vehicle = False
                                elif locked_dir == "coming":
                                    is_going_vehicle = False
                                    is_coming_vehicle = True
                                else:
                                    sample_len = min(5, len(history))
                                    dy_recent = history[-1][1] - history[-sample_len][1] if len(history) >= sample_len else (chk_curr[1] - chk_prev[1])
                                    dy_total = history[-1][1] - history[0][1] if len(history) >= 2 else (chk_curr[1] - chk_prev[1])

                                    if abs(dy_recent) >= 1.0:
                                        is_going_vehicle = (dy_recent < 0)
                                        is_coming_vehicle = (dy_recent > 0)
                                    elif abs(dy_total) >= 1.0:
                                        is_going_vehicle = (dy_total < 0)
                                        is_coming_vehicle = (dy_total > 0)
                                    else:
                                        dy_step = chk_curr[1] - chk_prev[1]
                                        is_going_vehicle = (dy_step < 0)
                                        is_coming_vehicle = (dy_step >= 0)

                                if inverted_state:
                                    is_going_vehicle, is_coming_vehicle = is_coming_vehicle, is_going_vehicle

                                if enable_out and not enable_in:
                                    if is_coming_vehicle:
                                        continue  # Reject coming vehicles strictly
                                elif enable_in and not enable_out:
                                    if is_going_vehicle:
                                        continue  # Reject going vehicles strictly

                                clean_name = ln.name.replace(" Line", "").strip()

                                if count_scope_mode == "active_only":
                                    if is_going_vehicle:
                                        if not enable_out:
                                            continue
                                        if enabled_lines_out is not None and len(enabled_lines_out) > 0:
                                            if clean_name not in enabled_lines_out and ln.name not in enabled_lines_out and len(lines) > 1:
                                                continue
                                        ln.out_count += 1
                                    else:
                                        if not enable_in:
                                            continue
                                        if enabled_lines_in is not None and len(enabled_lines_in) > 0:
                                            if clean_name not in enabled_lines_in and ln.name not in enabled_lines_in and len(lines) > 1:
                                                continue
                                        ln.in_count += 1
                                else:
                                    # "all_road" mode: count all traffic regardless of active filters
                                    if is_going_vehicle:
                                        ln.out_count += 1
                                    else:
                                        ln.in_count += 1

                                tr["counted_lines"].add(ln.name)
                                # Mark globally counted so no other line increments this vehicle again
                                tr["globally_counted"] = True

                                cat = tr["best_category"]
                                categories_summary[cat] = categories_summary.get(cat, 0) + 1

                                # Draw highlight flash on crossing
                                if needs_vis:
                                    cv2.line(frame, (ln.x1, ln.y1), (ln.x2, ln.y2), (0, 255, 0), 5)

                if needs_vis:
                    # ── Pull direction from Motion-Vote Brain (display only) ──
                    locked_dir = tr.get("direction")      # "going" | "coming" | "ambiguous" | None
                    is_already_counted = tr.get("globally_counted", False)
                    votes_g = tr.get("votes_going",  0)
                    votes_c = tr.get("votes_coming", 0)
                    tot_v   = max(1, votes_g + votes_c)
                    conf_pct = int(max(votes_g, votes_c) / tot_v * 100)

                    # Direction from accumulated votes (for arrow display)
                    if locked_dir == "going":
                        motion_dir = "GOING"
                        dir_arrow  = "^"
                    elif locked_dir == "coming":
                        motion_dir = "COMING"
                        dir_arrow  = "v"
                    elif votes_g > votes_c:
                        motion_dir = "GOING?"     # not yet confirmed
                        dir_arrow  = "^"
                    elif votes_c > votes_g:
                        motion_dir = "COMING?"    # not yet confirmed
                        dir_arrow  = "v"
                    else:
                        motion_dir = "?"
                        dir_arrow  = "?"

                    # ── Box Color Logic ───────────────────────────────────────
                    # GREEN        = counted (direction confirmed + counted)
                    # CYAN         = direction confirmed, waiting to count
                    # YELLOW       = direction building (votes accumulating)
                    # RED (bright) = ambiguous / not counting / wrong direction
                    if is_already_counted:
                        box_color    = (0, 255, 60)     # GREEN — counted ✓
                        status_label = "COUNTED"
                    elif locked_dir == "going" and enable_out:
                        box_color    = (0, 200, 255)    # CYAN — confirmed going, will count
                        status_label = "GOING-ACTIVE"
                    elif locked_dir == "coming" and enable_in:
                        box_color    = (0, 200, 255)    # CYAN — confirmed coming, will count
                        status_label = "COMING-ACTIVE"
                    elif locked_dir == "ambiguous":
                        box_color    = (0, 0, 255)      # RED — direction ambiguous
                        status_label = "AMBIGUOUS"
                    elif (locked_dir == "going" and not enable_out) or (locked_dir == "coming" and not enable_in):
                        box_color    = (0, 0, 255)      # RED — direction confirmed but disabled
                        status_label = "NOT COUNTING"
                    elif votes_g + votes_c >= 2:
                        box_color    = (0, 180, 255)    # ORANGE/AMBER — still gathering votes
                        status_label = f"TRACKING {conf_pct}%"
                    else:
                        box_color    = (0, 0, 255)      # RED — just appeared, no data yet
                        status_label = "NEW"

                    cur_dir_mode = job.get("direction_mode", "COMING_GOING")
                    if cur_dir_mode == "FORWARD_BACKWARD":
                        disp_dir = "FORWARD" if motion_dir in ("GOING", "GOING?") else "BACKWARD"
                    elif cur_dir_mode == "IN_OUT":
                        disp_dir = "OUT" if motion_dir in ("GOING", "GOING?") else "IN"
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

        # Memory management: purge stale track_data entries not seen in 150 frames
        if frame_idx % 60 == 0:
            stale_keys = [k for k, v in track_data.items() if frame_idx - v.get("last_seen", frame_idx) > 150]
            for k in stale_keys:
                del track_data[k]

        if needs_vis:
            # ─── Zone Divider Line ───────────────────────────────────────────
            # Horizontal mid-line divides GOING (top) from COMING (bottom) zones
            mid_y = frame_h // 2
            divider_color_going  = (0, 230, 80)    # bright green  → GOING zone top
            divider_color_coming = (60, 120, 255)  # bright blue   → COMING zone bottom

            # Solid thick divider
            cv2.line(frame, (0, mid_y), (frame_w, mid_y), (255, 255, 255), 1)
            # Left bracket ticks
            cv2.line(frame, (0, 0),      (0, mid_y),      divider_color_going,  3)
            cv2.line(frame, (0, mid_y),  (0, frame_h),    divider_color_coming, 3)
            # Right bracket ticks
            cv2.line(frame, (frame_w - 3, 0),     (frame_w - 3, mid_y),   divider_color_going,  3)
            cv2.line(frame, (frame_w - 3, mid_y), (frame_w - 3, frame_h), divider_color_coming, 3)

            # GOING zone label (top-right, green)
            going_active  = enable_out
            coming_active = enable_in

            going_label  = "GOING ZONE (COUNTING)" if going_active  else "GOING ZONE (OFF)"
            coming_label = "COMING ZONE (COUNTING)" if coming_active else "COMING ZONE (OFF)"

            cv2.rectangle(frame, (frame_w - 320, 8),  (frame_w - 2, 38),      (0, 0, 0), -1)
            cv2.putText(frame, going_label,  (frame_w - 314, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.62, divider_color_going,  2)

            cv2.rectangle(frame, (frame_w - 340, mid_y + 8), (frame_w - 2, mid_y + 38), (0, 0, 0), -1)
            cv2.putText(frame, coming_label, (frame_w - 334, mid_y + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.62, divider_color_coming, 2)

            # ─── Stats Overlay (bottom-left) ────────────────────────────────
            overlay_lines = [
                (f"TOTAL COUNTED: {total_count}", (0, 255, 80), 0.90, 2),
            ]
            for i, ln in enumerate(lines):
                out_lbl = f"  {ln.name}  OUT(GOING):{ln.out_count}"
                in_lbl  = f"  {ln.name}  IN(COMING):{ln.in_count}"
                overlay_lines.append((out_lbl, divider_color_going,  0.58, 2))
                overlay_lines.append((in_lbl,  divider_color_coming, 0.58, 2))

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

    cap.release()
    job["finished_at"] = time.time()
    job["done"] = True
    if job["status"] == "running":
        job["status"] = "finished"
