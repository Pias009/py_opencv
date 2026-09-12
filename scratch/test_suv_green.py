import cv2, os, sys
sys.path.insert(0, '/home/pias/Documents/py/app')

from zero_fault_counter import run_zero_fault_counter
from counter import CountingLine

# Extract frames 1100 to 1350 into a test clip
input_video = '/home/pias/Documents/py/scratch/user_test_video.mp4'
clip_path = '/home/pias/Documents/py/scratch/suv_clip.mp4'

cap = cv2.VideoCapture(input_video)
fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS) or 20.0

cap.set(cv2.CAP_PROP_POS_FRAMES, 1100)
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(clip_path, fourcc, fps, (fw, fh))

for _ in range(250):
    ret, frame = cap.read()
    if not ret: break
    out.write(frame)
cap.release()
out.release()
print("SUV clip extracted.")

lines = [CountingLine('Traffic Flow', 0, int(fh * 0.50), fw, int(fh * 0.50))]

job = {
    'id': 'test_suv_green_count',
    'line_mode': 'smart_flow',
    'count_scope_mode': 'active_only',
    'enable_in': True,
    'enable_out': False,
    'enabled_lines_in': ['South'],
    'enabled_lines_out': [],
    'invert_direction': False,
    'direction_mode': 'COMING_GOING'
}

green_frames = []
def frame_saver(jpeg_bytes):
    import numpy as np
    nparr = np.frombuffer(jpeg_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    fidx = job.get('frame_idx', 0)
    cnt = job.get('count', 0)
    if cnt > 0 and len(green_frames) < 5:
        cv2.imwrite(f'/home/pias/Documents/py/scratch/suv_green_frame_{fidx}.jpg', img)
        green_frames.append(fidx)

run_zero_fault_counter(clip_path, job, lines=lines, model_key="coco", conf_threshold=0.18, imgsz=640, vid_stride=3, frame_sink=frame_saver)

print("\n" + "="*60)
print(f"SUV Clip Result:")
print(f"Total Count: {job.get('count', 0)}")
print(f"Lines: {job.get('lines', {})}")
print(f"Categories: {job.get('categories', {})}")
print("="*60)
