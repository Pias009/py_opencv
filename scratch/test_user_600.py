import cv2, os, sys
sys.path.insert(0, '/home/pias/Documents/py/app')

from zero_fault_counter import run_zero_fault_counter
from counter import CountingLine

video_path = '/home/pias/Documents/py/scratch/user_test_600.mp4'
cap = cv2.VideoCapture(video_path)
fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
cap.release()

lines = [CountingLine('Traffic Flow', 0, int(fh * 0.50), fw, int(fh * 0.50))]

job = {
    'id': 'test_600_south_coming',
    'line_mode': 'smart_flow',
    'count_scope_mode': 'active_only',
    'enable_in': True,
    'enable_out': False,
    'enabled_lines_in': ['South'],
    'enabled_lines_out': [],
    'invert_direction': False,
    'direction_mode': 'COMING_GOING'
}

saved_frames = []
def frame_saver(jpeg_bytes):
    import numpy as np
    nparr = np.frombuffer(jpeg_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    fidx = job.get('frame_idx', 0)
    if fidx in [50, 100, 200, 300, 400, 500, 580] and len(saved_frames) < 10:
        cv2.imwrite(f'/home/pias/Documents/py/scratch/south_test_frame_{fidx}.jpg', img)
        saved_frames.append(fidx)

print("Starting 600-frame run under South Coming Only...")
run_zero_fault_counter(video_path, job, lines=lines, model_key="coco", conf_threshold=0.18, imgsz=640, vid_stride=4, frame_sink=frame_saver)

print("\n" + "="*60)
print(f"600-Frame Result:")
print(f"Total Count: {job.get('count', 0)}")
print(f"Lines: {job.get('lines', {})}")
print(f"Categories: {job.get('categories', {})}")
print("="*60)

in_count = job.get('lines', {}).get('Traffic Flow', {}).get('in', 0)
out_count = job.get('lines', {}).get('Traffic Flow', {}).get('out', 0)
print(f"IN count: {in_count}, OUT count: {out_count}")
assert in_count == 0, f"FAIL: IN count is {in_count}, expected 0!"
assert out_count == 0, f"FAIL: OUT count is {out_count}, expected 0!"
assert job.get('count', 0) == 0, f"FAIL: Total count is {job.get('count', 0)}, expected 0!"
print("SUCCESS: Zero false counts for Right-to-Left cross traffic under South Coming Only!")
