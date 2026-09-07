import json
import os
import re
import shutil
import threading
import time
import urllib.parse
import uuid

import requests
from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from counter import box_lines

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads")
CHUNK_TEMP_DIR = os.path.join(BASE_DIR, "data", "chunks")
RESULTS_DIR = os.path.join(BASE_DIR, "data", "results")
RESULTS_INDEX = os.path.join(RESULTS_DIR, "index.json")

ALLOWED_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CHUNK_TEMP_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

app = Flask(__name__)

jobs = {}
jobs_lock = threading.Lock()

url_downloads = {}
url_downloads_lock = threading.Lock()


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


def cleanup_raw_video(video_path):
    """Safely removes raw uploaded video after processing to prevent Railway disk exhaustion."""
    if not video_path:
        return
    try:
        abs_video = os.path.abspath(video_path)
        abs_upload_dir = os.path.abspath(UPLOAD_DIR)
        if abs_video.startswith(abs_upload_dir) and os.path.isfile(abs_video):
            os.remove(abs_video)
    except Exception:
        pass


def clean_stale_temp_files():
    """Clean up leftover .part chunks older than 2 hours and old uploads older than 24 hours."""
    now = time.time()
    # Clean CHUNK_TEMP_DIR
    if os.path.exists(CHUNK_TEMP_DIR):
        for item in os.listdir(CHUNK_TEMP_DIR):
            item_path = os.path.join(CHUNK_TEMP_DIR, item)
            try:
                if os.path.isdir(item_path):
                    if now - os.path.getmtime(item_path) > 7200:
                        shutil.rmtree(item_path, ignore_errors=True)
            except Exception:
                pass
    # Clean orphaned uploads older than 24 hours
    if os.path.exists(UPLOAD_DIR):
        for item in os.listdir(UPLOAD_DIR):
            if item.startswith("."):
                continue
            item_path = os.path.join(UPLOAD_DIR, item)
            try:
                if os.path.isfile(item_path) and (now - os.path.getmtime(item_path) > 86400):
                    os.remove(item_path)
            except Exception:
                pass


def resolve_direct_video_url(raw_url: str):
    """
    Analyzes raw_url and converts Google Drive and Dropbox share links to direct downloadable streams.
    Returns (resolved_url, headers, is_gdrive, gdrive_file_id, suggested_filename)
    """
    url = raw_url.strip()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    # 1. Google Drive share link
    gdrive_match = re.search(r"drive\.google\.com\/(?:file\/d\/|open\?id=)([a-zA-Z0-9_-]+)", url)
    if gdrive_match:
        file_id = gdrive_match.group(1)
        direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        return direct_url, headers, True, file_id, f"gdrive_video_{file_id[:8]}.mp4"

    # 2. Dropbox share link
    if "dropbox.com" in url:
        if "dl=0" in url:
            url = url.replace("dl=0", "dl=1")
        elif "dl=1" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}dl=1"
        url = url.replace("www.dropbox.com", "dl.dropboxusercontent.com")
        path_name = urllib.parse.urlparse(url).path.split("/")[-1] or "dropbox_video.mp4"
        return url, headers, False, None, path_name

    # 3. Direct HTTP/HTTPS link
    parsed = urllib.parse.urlparse(url)
    path_name = parsed.path.split("/")[-1] or "cloud_video.mp4"
    if "?" in path_name:
        path_name = path_name.split("?")[0]
    if not any(path_name.lower().endswith(ext) for ext in ALLOWED_EXT):
        path_name += ".mp4"

    return url, headers, False, None, path_name


def download_url_worker(download_id, raw_url):
    info = url_downloads[download_id]
    try:
        resolved_url, headers, is_gdrive, gdrive_file_id, suggested_name = resolve_direct_video_url(raw_url)
        session = requests.Session()
        session.headers.update(headers)

        res = session.get(resolved_url, stream=True, timeout=30)
        res.raise_for_status()

        if is_gdrive:
            confirm_token = None
            for key, val in session.cookies.items():
                if key.startswith("download_warning"):
                    confirm_token = val
                    break
            if not confirm_token:
                text_peek = res.text[:2000]
                match = re.search(r"confirm=([0-9A-Za-z_-]+)", text_peek)
                if match:
                    confirm_token = match.group(1)

            if confirm_token:
                confirm_url = f"https://drive.google.com/uc?export=download&confirm={confirm_token}&id={gdrive_file_id}"
                res = session.get(confirm_url, stream=True, timeout=30)
                res.raise_for_status()

        cd_header = res.headers.get("Content-Disposition", "")
        if "filename=" in cd_header:
            cd_match = re.search(r'filename=["\']?([^"\';]+)["\']?', cd_header)
            if cd_match:
                suggested_name = secure_filename(cd_match.group(1))

        if not any(suggested_name.lower().endswith(ext) for ext in ALLOWED_EXT):
            suggested_name += ".mp4"

        total_bytes = None
        if "Content-Length" in res.headers:
            try:
                total_bytes = int(res.headers["Content-Length"])
            except ValueError:
                pass

        MAX_DOWNLOAD_BYTES = 2500 * 1024 * 1024  # 2.5 GB limit safeguard for Railway disk
        if total_bytes and total_bytes > MAX_DOWNLOAD_BYTES:
            raise ValueError(f"Video file is too large ({round(total_bytes / (1024*1024), 1)} MB). Limit is 2.5 GB.")

        unique_name = f"{uuid.uuid4().hex}_{suggested_name}"
        save_path = os.path.join(UPLOAD_DIR, unique_name)

        with url_downloads_lock:
            info["total_bytes"] = total_bytes
            info["filename"] = suggested_name
            info["status"] = "downloading"

        downloaded = 0
        CHUNK_WRITE = 1024 * 1024  # 1MB buffer
        with open(save_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=CHUNK_WRITE):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if downloaded > MAX_DOWNLOAD_BYTES:
                    raise ValueError("Download exceeded 2.5 GB limit.")
                with url_downloads_lock:
                    info["downloaded_bytes"] = downloaded
                    if total_bytes and total_bytes > 0:
                        info["progress"] = round((downloaded / total_bytes) * 100, 1)

        with url_downloads_lock:
            info["status"] = "complete"
            info["file_path"] = save_path
            info["filename"] = suggested_name
            info["progress"] = 100
            info["done"] = True

    except Exception as e:
        with url_downloads_lock:
            info["status"] = "error"
            info["error"] = str(e)
            info["done"] = True


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
threading.Thread(target=clean_stale_temp_files, daemon=True).start()


def job_worker(job_id, video_path, source_label):
    job = jobs[job_id]
    frame_sink = make_frame_sink(job)
    vid_stride = job.get("vid_stride", 1)
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
                               conf_threshold=0.18, imgsz=640, vid_stride=vid_stride,
                               frame_sink=frame_sink)
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        job["done"] = True

    day_dir = day_results_dir(job.get("started_at"))
    day = os.path.basename(day_dir)
    entry = refresh_reports(job_id, job, day_dir, day)
    save_history_entry(entry)
    cleanup_raw_video(video_path)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/history")
def api_history():
    return jsonify(load_history())


@app.route("/api/fetch_url", methods=["POST"])
def api_fetch_url():
    """Starts background streaming download of video from direct URL, Google Drive, or Dropbox."""
    data = request.get_json(silent=True) or {}
    raw_url = (data.get("url") or "").strip()
    if not raw_url:
        return jsonify({"error": "Please provide a valid video URL"}), 400

    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in ("http", "https"):
        return jsonify({"error": "Invalid URL scheme. Must start with http:// or https://"}), 400

    download_id = uuid.uuid4().hex
    with url_downloads_lock:
        url_downloads[download_id] = {
            "status": "connecting",
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "progress": 0,
            "filename": "cloud_video.mp4",
            "file_path": None,
            "error": None,
            "done": False,
        }

    threading.Thread(target=download_url_worker, args=(download_id, raw_url), daemon=True).start()
    return jsonify({"download_id": download_id})


@app.route("/api/fetch_url_progress/<download_id>")
def api_fetch_url_progress(download_id):
    with url_downloads_lock:
        info = url_downloads.get(download_id)
    if not info:
        return jsonify({"error": "Download ID not found"}), 404
    return jsonify(info)


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
    raw_filename = request.form.get("filename")

    if save_path and os.path.exists(save_path):
        if raw_filename and raw_filename.strip():
            filename = secure_filename(raw_filename.strip()) or os.path.basename(save_path)
        else:
            base = os.path.basename(save_path)
            # If named uuid_filename.mp4, strip 32-hex-char uuid + underscore
            if len(base) > 33 and base[32] == "_":
                filename = base[33:]
            else:
                filename = base
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

