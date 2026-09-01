import json
import os
import threading
import time
import uuid

from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from counter import box_lines

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads")
RESULTS_DIR = os.path.join(BASE_DIR, "data", "results")
RESULTS_INDEX = os.path.join(RESULTS_DIR, "index.json")

ALLOWED_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

app = Flask(__name__)

jobs = {}
jobs_lock = threading.Lock()


def day_results_dir(started_at=None):
    """Results folder for a run, grouped by the date it started: data/results/YYYY-MM-DD/."""
    day = time.strftime("%Y-%m-%d", time.localtime(started_at or time.time()))
    path = os.path.join(RESULTS_DIR, day)
    os.makedirs(path, exist_ok=True)
    return path


def load_history():
    if not os.path.exists(RESULTS_INDEX):
        return []
    with open(RESULTS_INDEX) as f:
        return json.load(f)


def save_history_entry(entry):
    history = load_history()
    history.insert(0, entry)
    with open(RESULTS_INDEX, "w") as f:
        json.dump(history, f, indent=2)


def make_frame_sink(job):
    def sink(jpeg_bytes):
        with jobs_lock:
            job["last_frame"] = jpeg_bytes
    return sink


def build_entry(job_id, job, day):
    return {
        "id": job_id,
        "video": job.get("video"),
        "count": job.get("count", 0),
        "lines": job.get("lines", {}),
        "categories": job.get("categories", {}),
        "model_used": job.get("model_used"),
        "final_speed_mode": job.get("speed_mode"),
        "reanalyzed_count": job.get("reanalyzed", 0),
        "total_frames": job.get("total_frames", 0),
        "status": job.get("status", "error"),
        "error": job.get("error"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "duration_sec": round((job.get("finished_at", 0) - job.get("started_at", 0)), 2)
        if job.get("started_at") and job.get("finished_at") else None,
        "date_dir": day,
    }


def save_status_json(job_id, job, day_dir, day):
    entry = build_entry(job_id, job, day)
    json_path = os.path.join(day_dir, f"{job_id}.json")
    with open(json_path, "w") as f:
        json.dump(entry, f, indent=2)
    return entry


def refresh_reports(job_id, job, day_dir, day):
    entry = save_status_json(job_id, job, day_dir, day)
    try:
        from report import generate_report_pdf
        generate_report_pdf(entry, os.path.join(day_dir, f"{job_id}.pdf"))
    except Exception:
        pass
    try:
        from excel_report import generate_report_xlsx
        generate_report_xlsx(entry, os.path.join(day_dir, f"{job_id}.xlsx"))
    except Exception:
        pass
    return entry


def prewarm_models():
    """Pre-load YOLO model in background at startup to eliminate delay when user uploads video."""
    try:
        from zero_fault_counter import BNVD_MODEL_PATH, COCO_MODEL_PATH, get_yolo_model
        if os.path.exists(BNVD_MODEL_PATH):
            get_yolo_model(BNVD_MODEL_PATH)
        elif os.path.exists(COCO_MODEL_PATH):
            get_yolo_model(COCO_MODEL_PATH)
    except Exception:
        pass

threading.Thread(target=prewarm_models, daemon=True).start()


def job_worker(job_id, video_path, source_label):
    job = jobs[job_id]
    frame_sink = make_frame_sink(job)
    vid_stride = job.get("vid_stride", 2)
    line_mode = job.get("line_mode", "box")

    day_dir = day_results_dir()
    day = os.path.basename(day_dir)

    def status_loop():
        while not job.get("done"):
            save_status_json(job_id, job, day_dir, day)
            time.sleep(3)

    threading.Thread(target=status_loop, daemon=True).start()

    try:
        import cv2
        from counter import box_lines, default_lines, vertical_line
        cap = cv2.VideoCapture(video_path)
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        if line_mode == "horizontal":
            lines = default_lines(frame_w, frame_h)
        elif line_mode == "vertical":
            lines = vertical_line(frame_w, frame_h, pct=0.5)
        elif line_mode == "auto":
            from zero_fault_counter import auto_detect_road_corridor
            lines = auto_detect_road_corridor(video_path, frame_w, frame_h)
        else:
            lines = box_lines(frame_w, frame_h, margin=40)

        from zero_fault_counter import run_zero_fault_counter
        run_zero_fault_counter(video_path, job, lines=lines, model_key="bnvd",
                               conf_threshold=0.25, imgsz=640, vid_stride=vid_stride,
                               frame_sink=frame_sink)
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        job["done"] = True

    day_dir = day_results_dir(job.get("started_at"))
    day = os.path.basename(day_dir)
    entry = refresh_reports(job_id, job, day_dir, day)
    save_history_entry(entry)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/history")
def api_history():
    return jsonify(load_history())


CHUNK_TEMP_DIR = os.path.join(BASE_DIR, "data", "chunks")
os.makedirs(CHUNK_TEMP_DIR, exist_ok=True)


@app.route("/api/upload_chunk", methods=["POST"])
def api_upload_chunk():
    """Receives 4MB-5MB slices of large videos to eliminate Railway upload timeouts & proxy network errors."""
    upload_id = request.form.get("upload_id")
    try:
        chunk_index = int(request.form.get("chunk_index", 0))
        total_chunks = int(request.form.get("total_chunks", 1))
    except ValueError:
        return jsonify({"error": "Invalid chunk parameters"}), 400

    raw_filename = request.form.get("filename", "video.mp4")
    filename = secure_filename(raw_filename)

    if not upload_id or "chunk" not in request.files:
        return jsonify({"error": "Missing chunk file or upload ID"}), 400

    chunk_dir = os.path.join(CHUNK_TEMP_DIR, upload_id)
    os.makedirs(chunk_dir, exist_ok=True)

    chunk_file = request.files["chunk"]
    chunk_path = os.path.join(chunk_dir, f"{chunk_index}.part")
    chunk_file.save(chunk_path)

    # Check if all chunks have arrived
    parts = os.listdir(chunk_dir)
    if len(parts) >= total_chunks:
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        final_path = os.path.join(UPLOAD_DIR, unique_name)

        with open(final_path, "wb") as outfile:
            for i in range(total_chunks):
                p_path = os.path.join(chunk_dir, f"{i}.part")
                if os.path.exists(p_path):
                    with open(p_path, "rb") as infile:
                        outfile.write(infile.read())
                    try:
                        os.remove(p_path)
                    except Exception:
                        pass

        try:
            os.rmdir(chunk_dir)
        except Exception:
            pass

        return jsonify({
            "status": "complete",
            "file_path": final_path,
            "filename": filename
        })

    return jsonify({"status": "chunk_received", "chunk_index": chunk_index, "received": len(parts)})


@app.route("/api/start", methods=["POST"])
def api_start():
    save_path = request.form.get("file_path")
    filename = request.form.get("filename", "Uploaded Video")

    if save_path and os.path.exists(save_path):
        filename = os.path.basename(save_path)
    elif "file" in request.files and request.files["file"].filename:
        f = request.files["file"]
        filename = secure_filename(f.filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXT:
            return jsonify({"error": f"Unsupported file type: {ext}"}), 400

        unique_name = f"{uuid.uuid4().hex}_{filename}"
        save_path = os.path.join(UPLOAD_DIR, unique_name)
        f.save(save_path)
    else:
        return jsonify({"error": "No valid video file or upload path provided"}), 400

    speed_val = request.form.get("speed", "2")
    try:
        vid_stride = int(speed_val)
        if vid_stride < 1 or vid_stride > 5:
            vid_stride = 2
    except ValueError:
        vid_stride = 2

    line_mode = request.form.get("line_mode", "box")
    invert_direction = request.form.get("invert", "false").lower() == "true"
    enable_in = request.form.get("enable_in", "true").lower() == "true"
    enable_out = request.form.get("enable_out", "true").lower() == "true"
    count_scope_mode = request.form.get("count_scope_mode", "active_only")
    direction_mode = request.form.get("direction_mode", "IN_OUT")

    enabled_lines_raw = request.form.get("enabled_lines", "North,South,West,East,Line1")
    enabled_lines = [x.strip() for x in enabled_lines_raw.split(",") if x.strip()]

    raw_in = request.form.get("enabled_lines_in", "")
    enabled_lines_in = [x.strip() for x in raw_in.split(",") if x.strip()] if raw_in else None

    raw_out = request.form.get("enabled_lines_out", "")
    enabled_lines_out = [x.strip() for x in raw_out.split(",") if x.strip()] if raw_out else None

    job_id = uuid.uuid4().hex
    job = {
        "status": "starting",
        "video": filename,
        "cancel": False,
        "done": False,
        "last_frame": None,
        "count": 0,
        "lines": {},
        "categories": {},
        "frame_idx": 0,
        "total_frames": 0,
        "vid_stride": vid_stride,
        "line_mode": line_mode,
        "invert_direction": invert_direction,
        "enable_in": enable_in,
        "enable_out": enable_out,
        "count_scope_mode": count_scope_mode,
        "enabled_lines": enabled_lines,
        "enabled_lines_in": enabled_lines_in,
        "enabled_lines_out": enabled_lines_out,
        "direction_mode": direction_mode,
        "speed_mode": f"{vid_stride}x Fast-Forward",
        "reanalyzed": 0,
    }
    with jobs_lock:
        jobs[job_id] = job

    t = threading.Thread(target=job_worker, args=(job_id, save_path, filename), daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/api/invert/<job_id>", methods=["POST"])
def api_invert(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    job["invert_direction"] = not job.get("invert_direction", False)
    return jsonify({"inverted": job["invert_direction"]})


@app.route("/api/update_rules/<job_id>", methods=["POST"])
def api_update_rules(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    data = request.get_json(silent=True) or {}
    if "enable_in" in data:
        job["enable_in"] = bool(data["enable_in"])
    if "enable_out" in data:
        job["enable_out"] = bool(data["enable_out"])
    if "count_scope_mode" in data:
        job["count_scope_mode"] = str(data["count_scope_mode"])
    if "invert" in data:
        job["invert_direction"] = bool(data["invert"])
    if "enabled_lines" in data:
        job["enabled_lines"] = data["enabled_lines"]
    if "enabled_lines_in" in data:
        job["enabled_lines_in"] = data["enabled_lines_in"]
    if "enabled_lines_out" in data:
        job["enabled_lines_out"] = data["enabled_lines_out"]
    return jsonify({"ok": True})


@app.route("/api/status/<job_id>")
def api_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    progress = 0
    if job.get("total_frames"):
        progress = round(100 * job.get("frame_idx", 0) / job["total_frames"], 1)
    day = time.strftime("%Y-%m-%d", time.localtime(job.get("started_at") or time.time()))
    report_pdf_url = None
    report_xlsx_url = None
    if job.get("done"):
        pdf_path = os.path.join(RESULTS_DIR, day, f"{job_id}.pdf")
        xlsx_path = os.path.join(RESULTS_DIR, day, f"{job_id}.xlsx")
        if os.path.exists(pdf_path):
            report_pdf_url = f"/api/report/{day}/{job_id}.pdf"
        if os.path.exists(xlsx_path):
            report_xlsx_url = f"/api/report/{day}/{job_id}.xlsx"

    return jsonify({
        "status": job.get("status"),
        "count": job.get("count", 0),
        "lines": job.get("lines", {}),
        "categories": job.get("categories", {}),
        "speed_mode": job.get("speed_mode"),
        "reanalyzed": job.get("reanalyzed", 0),
        "frame_idx": job.get("frame_idx", 0),
        "total_frames": job.get("total_frames", 0),
        "progress": progress,
        "error": job.get("error"),
        "done": job.get("done", False),
        "report_pdf": report_pdf_url,
        "report_xlsx": report_xlsx_url,
    })


@app.route("/api/cancel/<job_id>", methods=["POST"])
def api_cancel(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    job["cancel"] = True
    return jsonify({"ok": True})


@app.route("/api/stream/<job_id>")
def api_stream(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404

    def generate():
        boundary = b"--frame"
        while True:
            frame = job.get("last_frame")
            if frame is not None:
                yield (boundary + b"\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            if job.get("done"):
                break
            time.sleep(0.05)

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/report/<day>/<filename>")
def api_report(day, filename):
    day_dir = os.path.join(RESULTS_DIR, day)
    return send_from_directory(day_dir, filename, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Host 0.0.0.0 allows connections from localhost, Render, and Railway
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)

