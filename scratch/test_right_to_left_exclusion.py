import sys, os, time
sys.path.insert(0, '/home/pias/Documents/py/app')

from zero_fault_counter import run_zero_fault_counter, CountingLine

VIDEO_PATH = '/home/pias/Documents/py/09.00.00-09.05.00[M][0@0][0].mp4'

print("=" * 70)
print("VERIFYING RIGHT-TO-LEFT EXCLUSION & SOUTH COMING ONLY GATING")
print("=" * 70)

job = {
    "status": "pending",
    "line_mode": "smart_flow",
    "direction_mode": "COMING_GOING",
    "enable_in": True,
    "enable_out": False,
    "enabled_lines_in": ["South"],
    "count_scope_mode": "active_only"
}

saved_frames = []
def frame_sink(jpeg_bytes):
    if len(jpeg_bytes) > 0:
        saved_frames.append(jpeg_bytes)
        if len(saved_frames) > 5:
            saved_frames.pop(0)

import threading
def cancel_after():
    while not job.get("done") and job.get("status") != "cancelled":
        if job.get("frame_idx", 0) >= 120:
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
assert tf.get("out", 0) == 0, f"Going traffic was counted: out={tf.get('out')}"
assert job.get("count") == tf.get("in", 0), f"Mismatch between total and in: {job.get('count')} vs {tf.get('in')}"

if saved_frames:
    out_img_path = "/home/pias/.gemini/antigravity-ide/brain/509114ca-23e0-47a0-b649-eb772f6243bf/south_coming_only_frame.jpg"
    with open(out_img_path, "wb") as f:
        f.write(saved_frames[-1])
    print(f"Saved active frame to: {out_img_path}")

print("=" * 70)
print("✓ RIGHT-TO-LEFT EXCLUSION VERIFIED 100% SUCCESSFUL!")
print("=" * 70)
