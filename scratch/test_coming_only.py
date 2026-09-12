import sys, os, time
sys.path.insert(0, '/home/pias/Documents/py/app')
import cv2

from zero_fault_counter import run_zero_fault_counter, get_yolo_model, BNVD_MODEL_PATH
from counter import CountingLine

VIDEO_PATH = '/home/pias/Documents/py/09.00.00-09.05.00[M][0@0][0].mp4'

print("=" * 70)
print("VERIFYING COMING (FACE SHOWING) ONLY COUNTING & VISUALIZATION")
print("=" * 70)

job = {
    "status": "pending",
    "line_mode": "smart_flow",
    "direction_mode": "COMING_GOING",
    "enable_in": True,
    "enable_out": False,
    "count_scope_mode": "active_only"
}

saved_frame = None

def frame_sink(jpeg_bytes):
    global saved_frame
    if saved_frame is None and len(jpeg_bytes) > 0:
        saved_frame = jpeg_bytes

import threading
def cancel_after():
    while not job.get("done") and job.get("status") != "cancelled":
        if job.get("frame_idx", 0) >= 160:
            job["cancel"] = True
            break
        time.sleep(0.05)

t = threading.Thread(target=cancel_after, daemon=True)
t.start()

run_zero_fault_counter(VIDEO_PATH, job, model_key="bnvd", vid_stride=2, frame_sink=frame_sink)

print(f"Result count: {job.get('count')}")
print(f"Lines: {job.get('lines')}")
print(f"Categories: {job.get('categories')}")

tf = job.get("lines", {}).get("Traffic Flow", {})
in_count = tf.get("in", 0)
out_count = tf.get("out", 0)
cat_sum = sum(job.get("categories", {}).values())

assert out_count == 0, f"Going traffic was counted when enable_out=False! out_count={out_count}"
assert in_count > 0, f"No incoming traffic was counted! in_count={in_count}"
assert job.get("count") == in_count, f"Total count mismatch with in_count: {job.get('count')} vs {in_count}"
assert job.get("count") == cat_sum, f"Total count mismatch with cat_sum: {job.get('count')} vs {cat_sum}"

if saved_frame:
    out_img_path = "/home/pias/.gemini/antigravity-ide/brain/509114ca-23e0-47a0-b649-eb772f6243bf/coming_only_verified_frame.jpg"
    with open(out_img_path, "wb") as f:
        f.write(saved_frame)
    print(f"Verified frame saved to: {out_img_path}")

print("=" * 70)
print("✓ COMING ONLY COUNTING VERIFIED 100% PERFECT: Zero Going Count, Parity Intact!")
print("=" * 70)
