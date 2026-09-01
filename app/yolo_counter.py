import os
import time

import cv2

from counter import CountingLine, default_lines, pega_centro

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "yolov8n.pt")

MAX_TRACK_DISTANCE = 80
MAX_MISSED_FRAMES = 15
CONF_THRESHOLD = 0.35
INFER_SIZE = 640     # inference resolution; smaller = faster but misses small/far vehicles
DETECT_EVERY = 1      # run YOLO every Nth frame; other frames reuse the last known box positions

# Map YOLO/COCO classes to the closest category on the user's vehicle-survey sheet.
# COCO has no concept of Rickshaw, CNG, Tempo, Tanker, etc. (South-Asia-specific
# vehicle types), so anything not directly covered is reported honestly as "Other".
COCO_TO_SURVEY = {
    "bicycle": "Bicycle",
    "motorcycle": "Motorcycle",
    "car": "Car/Suv",
    "bus": "Large Bus",
    "truck": "Medium Truck/2-Axle Truck",
}
VEHICLE_CLASSES = set(COCO_TO_SURVEY.keys())


class Track:
    __slots__ = ("id", "cx", "cy", "prev_side", "missed", "counted_lines", "category", "conf")

    def __init__(self, track_id, cx, cy, category, conf):
        self.id = track_id
        self.cx = cx
        self.cy = cy
        self.prev_side = {}
        self.missed = 0
        self.counted_lines = set()
        self.category = category
        self.conf = conf


def run_counter_yolo(video_source, job, lines=None, conf_threshold=CONF_THRESHOLD,
                      frame_sink=None, show_window=False, model_path=MODEL_PATH,
                      imgsz=INFER_SIZE, detect_every=DETECT_EVERY, display_max_width=1280):
    """Detect and classify vehicles with YOLOv8, track them across frames, and count
    line crossings per named line and per vehicle category.

    imgsz: inference resolution passed to YOLO (smaller = faster, may miss small/far vehicles).
    detect_every: run YOLO on every Nth frame; frames in between reuse the last detections
                  for tracking continuity (faster overall, coarser motion sampling).

    job keys written: status, total_frames, frame_idx, count, lines (per-line in/out),
                       categories (per-category totals), error, done, started_at, finished_at
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        job["status"] = "error"
        job["error"] = "ultralytics is not installed. Run: pip install ultralytics"
        job["done"] = True
        return

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
        lines = default_lines(frame_w, frame_h)

    model = YOLO(model_path)

    tracks = []
    next_track_id = 0
    total_count = 0
    categories = {}

    job["status"] = "running"
    job["total_frames"] = total_frames
    job["frame_idx"] = 0
    job["count"] = 0
    job["lines"] = {ln.name: {"in": 0, "out": 0} for ln in lines}
    job["categories"] = {}
    job["started_at"] = time.time()

    frame_idx = 0
    while True:
        if job.get("cancel"):
            job["status"] = "cancelled"
            break

        ret, frame1 = cap.read()
        if not ret:
            break
        frame_idx += 1

        if frame_idx % detect_every == 1 or detect_every == 1:
            results = model(frame1, verbose=False, classes=None, imgsz=imgsz)[0]

            detections = []
            for box in results.boxes:
                cls_id = int(box.cls[0])
                name = model.names[cls_id]
                if name not in VEHICLE_CLASSES:
                    continue
                conf = float(box.conf[0])
                if conf < conf_threshold:
                    continue
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                category = COCO_TO_SURVEY.get(name, "Other")
                detections.append((x1, y1, x2 - x1, y2 - y1, category, conf))
            last_detections = detections
        else:
            # Skipped frame: reuse the last detected boxes so tracks stay alive
            # without paying for another inference pass.
            detections = last_detections

        for i, ln in enumerate(lines):
            cv2.line(frame1, (ln.x1, ln.y1), (ln.x2, ln.y2), (255, 127, 0), 3)
            cv2.putText(frame1, ln.name, (ln.x1 + 6, ln.y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 127, 0), 2)

        unmatched_tracks = list(range(len(tracks)))
        unmatched_detections = list(range(len(detections)))
        matches = []

        for ti in list(unmatched_tracks):
            best_di, best_dist = None, MAX_TRACK_DISTANCE
            tr = tracks[ti]
            for di in unmatched_detections:
                x, y, w, h, _, _ = detections[di]
                dcx, dcy = pega_centro(x, y, w, h)
                dist = ((tr.cx - dcx) ** 2 + (tr.cy - dcy) ** 2) ** 0.5
                if dist < best_dist:
                    best_dist = dist
                    best_di = di
            if best_di is not None:
                matches.append((ti, best_di))
                unmatched_tracks.remove(ti)
                unmatched_detections.remove(best_di)

        def cross_lines(tr, cx, cy):
            nonlocal total_count
            if getattr(tr, 'counted_globally', False):
                return
            for ln in lines:
                side = ln.signed_side(cx, cy)
                prev = tr.prev_side.get(ln.name)
                if (prev is not None and prev * side <= 0
                        and ln.distance_to_segment(cx, cy) <= 40
                        and ln.name not in tr.counted_lines):
                    tr.counted_lines.add(ln.name)
                    tr.counted_globally = True
                    if side > prev:
                        ln.in_count += 1
                    else:
                        ln.out_count += 1
                    total_count += 1
                    categories[tr.category] = categories.get(tr.category, 0) + 1
                    break
                tr.prev_side[ln.name] = side

        for ti, di in matches:
            x, y, w, h, category, conf = detections[di]
            cx, cy = pega_centro(x, y, w, h)
            tr = tracks[ti]
            tr.cx, tr.cy, tr.missed = cx, cy, 0
            if conf > tr.conf:
                tr.category, tr.conf = category, conf
            cross_lines(tr, cx, cy)
            cv2.rectangle(frame1, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame1, tr.category, (x, max(15, y - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        for di in unmatched_detections:
            x, y, w, h, category, conf = detections[di]
            cx, cy = pega_centro(x, y, w, h)
            tr = Track(next_track_id, cx, cy, category, conf)
            next_track_id += 1
            for ln in lines:
                tr.prev_side[ln.name] = ln.signed_side(cx, cy)
            tracks.append(tr)
            cv2.rectangle(frame1, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame1, category, (x, max(15, y - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        for ti in unmatched_tracks:
            tracks[ti].missed += 1
        tracks = [tr for tr in tracks if tr.missed <= MAX_MISSED_FRAMES]

        cv2.putText(frame1, "TOTAL: " + str(total_count), (15, frame_h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 255), 3)

        job["frame_idx"] = frame_idx
        job["count"] = total_count
        job["lines"] = {ln.name: {"in": ln.in_count, "out": ln.out_count} for ln in lines}
        job["categories"] = dict(categories)

        if frame_sink is not None:
            ok, jpeg = cv2.imencode(".jpg", frame1, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                frame_sink(jpeg.tobytes())

        if show_window:
            display_frame = frame1
            if display_max_width and frame_w > display_max_width:
                scale = display_max_width / frame_w
                new_size = (display_max_width, int(frame_h * scale))
                display_frame = cv2.resize(frame1, new_size, interpolation=cv2.INTER_AREA)
            cv2.imshow("Vehicle Counter (YOLO) - Video", display_frame)
            if cv2.waitKey(1) == 27:
                job["cancel"] = True

    if show_window:
        cv2.destroyAllWindows()

    cap.release()
    job["finished_at"] = time.time()
    job["done"] = True
    if job["status"] == "running":
        job["status"] = "finished"
