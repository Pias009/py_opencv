import sys, os, time
sys.path.insert(0, '/home/pias/Documents/py/app')

from zero_fault_counter import run_zero_fault_counter

VIDEO_PATH = '/home/pias/Documents/py/09.00.00-09.05.00[M][0@0][0].mp4'

job = {
    "status": "pending",
    "line_mode": "smart_flow",
    "direction_mode": "COMING_GOING",
    "enable_in": True,
    "enable_out": False,
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
        if job.get("frame_idx", 0) >= 80:
            job["cancel"] = True
            break
        time.sleep(0.05)

t = threading.Thread(target=cancel_after, daemon=True)
t.start()

run_zero_fault_counter(VIDEO_PATH, job, model_key="bnvd", vid_stride=2, frame_sink=frame_sink)

print("Count:", job.get("count"), "Lines:", job.get("lines"))
if saved_frames:
    out_img_path = "/home/pias/.gemini/antigravity-ide/brain/509114ca-23e0-47a0-b649-eb772f6243bf/coming_only_active_frame.jpg"
    with open(out_img_path, "wb") as f:
        f.write(saved_frames[-1])
    print("Saved active frame to:", out_img_path)
