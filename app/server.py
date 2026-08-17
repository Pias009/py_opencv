import json
import os
import threading
import time
import uuid

from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from counter import run_counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads")
RESULTS_DIR = os.path.join(BASE_DIR, "data", "results")
RESULTS_INDEX = os.path.join(RESULTS_DIR, "index.json")


def day_results_dir(started_at=None):
    """Results folder for a run, grouped by the date it started: data/results/YYYY-MM-DD/.
    Created up front so a run that errors or is cancelled before finishing still has
    somewhere to save its partial result.
    """
    day = time.strftime("%Y-%m-%d", time.localtime(started_at or time.time()))
    path = os.path.join(RESULTS_DIR, day)
    os.makedirs(path, exist_ok=True)
    return path

ALLOWED_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

app = Flask(__name__)

jobs = {}
jobs_lock = threading.Lock()


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


def job_worker(job_id, video_path, source_label, line_pos_pct, min_width, min_height):
    job = jobs[job_id]
    frame_sink = make_frame_sink(job)
    run_counter(video_path, job, min_width=min_width, min_height=min_height,
                line_pos_pct=line_pos_pct, frame_sink=frame_sink)

    # Always save a result, even if the run errored or was cancelled before
    # finishing, so partial progress (frames processed, counts so far) isn't lost.
    day_dir = day_results_dir(job.get("started_at"))
    day = os.path.basename(day_dir)
    entry = {
        "id": job_id,
        "video": source_label,
        "count": job.get("count", 0),
        "lines": job.get("lines", {}),
        "total_frames": job.get("total_frames", 0),
        "status": job.get("status", "error"),
        "error": job.get("error"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "duration_sec": round((job.get("finished_at", 0) - job.get("started_at", 0)), 2)
        if job.get("started_at") and job.get("finished_at") else None,
        "date_dir": day,
    }
    save_history_entry(entry)
    with open(os.path.join(day_dir, f"{job_id}.json"), "w") as f:
        json.dump(entry, f, indent=2)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/history")
def api_history():
    return jsonify(load_history())


@app.route("/api/start", methods=["POST"])
def api_start():
    if "file" not in request.files or not request.files["file"].filename:
        return jsonify({"error": "No video file provided"}), 400

    f = request.files["file"]
    filename = secure_filename(f.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({"error": f"Unsupported file type: {ext}"}), 400
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    f.save(save_path)
    video_path = save_path
    source_label = filename

    data = request.form if request.form else (request.get_json(silent=True) or {})
    line_pos_pct = float(data.get("line_pos", 0.45))
    min_width = int(data.get("min_width", 80))
    min_height = int(data.get("min_height", 80))

    job_id = uuid.uuid4().hex
    job = {
        "status": "starting",
        "video": source_label,
        "cancel": False,
        "done": False,
        "last_frame": None,
        "count": 0,
        "frame_idx": 0,
        "total_frames": 0,
    }
    with jobs_lock:
        jobs[job_id] = job

    t = threading.Thread(target=job_worker, args=(job_id, video_path, source_label,
                                                    line_pos_pct, min_width, min_height),
                          daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def api_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    progress = 0
    if job.get("total_frames"):
        progress = round(100 * job.get("frame_idx", 0) / job["total_frames"], 1)
    return jsonify({
        "status": job.get("status"),
        "count": job.get("count", 0),
        "frame_idx": job.get("frame_idx", 0),
        "total_frames": job.get("total_frames", 0),
        "progress": progress,
        "error": job.get("error"),
        "done": job.get("done", False),
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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
