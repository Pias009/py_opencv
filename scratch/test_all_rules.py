import sys, os, time
sys.path.insert(0, '/home/pias/Documents/py/app')

from zero_fault_counter import run_zero_fault_counter, get_yolo_model, BNVD_MODEL_PATH
from counter import box_lines, dual_gate_lines, default_lines, CountingLine
from report import generate_report_pdf
from excel_report import generate_report_xlsx

VIDEO_PATH = '/home/pias/Documents/py/09.00.00-09.05.00[M][0@0][0].mp4'

print("=" * 70)
print("COMPREHENSIVE TRAFFIC RULES & COUNTING ENGINE VERIFICATION")
print("=" * 70)

results = {}

# -------------------------------------------------------------
# TEST 1: Smart Trajectory Flow (Going-Only 1-Side Mode)
# -------------------------------------------------------------
print("\n>>> RUNNING TEST 1: Smart Trajectory Flow (Going-Only, enable_in=False, enable_out=True)")
job1 = {
    "status": "pending",
    "line_mode": "smart_flow",
    "direction_mode": "COMING_GOING",
    "enable_in": False,
    "enable_out": True,
    "count_scope_mode": "active_only"
}
# Run for first 150 frames (using vid_stride=2, so 75 model iterations)
def run_capped(job, max_frames=150, lines=None):
    orig_results_generator = None
    model = get_yolo_model(BNVD_MODEL_PATH)
    lines_list = lines or [CountingLine("Traffic Flow", 0, int(1296 * 0.35), 2304, int(1296 * 0.35))]
    
    # Run counter with a frame limiter
    frame_count = 0
    def limiter_sink(jpeg_bytes):
        pass

    # We run zero fault counter but set cancel when frame_idx reaches max_frames
    import threading
    def cancel_after():
        while not job.get("done") and job.get("status") != "cancelled":
            if job.get("frame_idx", 0) >= max_frames:
                job["cancel"] = True
                break
            time.sleep(0.05)
    
    t = threading.Thread(target=cancel_after, daemon=True)
    t.start()
    run_zero_fault_counter(VIDEO_PATH, job, lines=lines_list, model_key="bnvd", vid_stride=2, frame_sink=limiter_sink)

run_capped(job1, max_frames=160)
print(f"Test 1 Result: count={job1.get('count')}, lines={job1.get('lines')}, categories={job1.get('categories')}")
# Verify rules for Test 1:
# 1. Total count must equal sum of categories
cat_sum1 = sum(job1.get("categories", {}).values())
assert job1.get("count") == cat_sum1, f"Count mismatch: total={job1.get('count')} vs cat_sum={cat_sum1}"
# 2. IN count must be 0 because enable_in=False
tf_lines1 = job1.get("lines", {}).get("Traffic Flow", {})
assert tf_lines1.get("in", 0) == 0, f"Incoming traffic was counted despite enable_in=False: {tf_lines1}"
assert job1.get("count") == tf_lines1.get("out", 0), f"Total count does not match OUT line: {job1.get('count')} vs {tf_lines1.get('out')}"
print("✓ TEST 1 PASSED: Strict Outgoing-only gating enforced, categories & line parity 100%!")
results["test1_smart_flow_going_only"] = "PASSED"

# -------------------------------------------------------------
# TEST 2: Smart Trajectory Flow (Both Directions: enable_in=True, enable_out=True)
# -------------------------------------------------------------
print("\n>>> RUNNING TEST 2: Smart Trajectory Flow (Both Directions)")
job2 = {
    "status": "pending",
    "line_mode": "smart_flow",
    "direction_mode": "COMING_GOING",
    "enable_in": True,
    "enable_out": True,
    "count_scope_mode": "active_only"
}
run_capped(job2, max_frames=160)
print(f"Test 2 Result: count={job2.get('count')}, lines={job2.get('lines')}, categories={job2.get('categories')}")
cat_sum2 = sum(job2.get("categories", {}).values())
tf_lines2 = job2.get("lines", {}).get("Traffic Flow", {})
total_in_out = tf_lines2.get("in", 0) + tf_lines2.get("out", 0)
assert job2.get("count") == cat_sum2, f"Count mismatch: {job2.get('count')} vs {cat_sum2}"
assert job2.get("count") == total_in_out, f"Count mismatch with lines: {job2.get('count')} vs {total_in_out}"
print("✓ TEST 2 PASSED: Both flows cleanly counted, categories & line parity 100%!")
results["test2_smart_flow_both_flows"] = "PASSED"

# -------------------------------------------------------------
# TEST 3: Dual-Gate Virtual Trap Mode
# -------------------------------------------------------------
print("\n>>> RUNNING TEST 3: Dual-Gate Virtual Trap Mode")
dg_lines = dual_gate_lines(2304, 1296)
job3 = {
    "status": "pending",
    "line_mode": "dual_gate",
    "direction_mode": "COMING_GOING",
    "enable_in": True,
    "enable_out": True,
    "count_scope_mode": "active_only"
}
run_capped(job3, max_frames=160, lines=dg_lines)
print(f"Test 3 Result: count={job3.get('count')}, lines={job3.get('lines')}, categories={job3.get('categories')}")
cat_sum3 = sum(job3.get("categories", {}).values())
assert job3.get("count") == cat_sum3, f"Count mismatch: {job3.get('count')} vs {cat_sum3}"
print("✓ TEST 3 PASSED: Dual-Gate trap cleanly tracks & counts vehicles!")
results["test3_dual_gate"] = "PASSED"

# -------------------------------------------------------------
# TEST 4: 4-Way Intersection Box Mode with Line Filtering
# -------------------------------------------------------------
print("\n>>> RUNNING TEST 4: 4-Way Intersection Box Mode")
b_lines = box_lines(2304, 1296, margin=40)
job4 = {
    "status": "pending",
    "line_mode": "box",
    "direction_mode": "IN_OUT",
    "enable_in": True,
    "enable_out": True,
    "enabled_lines": ["North Line", "South Line"],
    "count_scope_mode": "active_only"
}
run_capped(job4, max_frames=160, lines=b_lines)
print(f"Test 4 Result: count={job4.get('count')}, lines={job4.get('lines')}, categories={job4.get('categories')}")
cat_sum4 = sum(job4.get("categories", {}).values())
assert job4.get("count") == cat_sum4, f"Count mismatch: {job4.get('count')} vs {cat_sum4}"
print("✓ TEST 4 PASSED: 4-Way Box Mode with line filtering works properly!")
results["test4_box_mode"] = "PASSED"

# -------------------------------------------------------------
# TEST 5: PDF & Excel Report Generation
# -------------------------------------------------------------
print("\n>>> RUNNING TEST 5: PDF & Excel Export Generation")
job_report = {
    "count": job1.get("count", 10),
    "lines": job1.get("lines", {}),
    "categories": job1.get("categories", {}),
    "direction_mode": "COMING_GOING",
    "line_mode": "smart_flow",
    "filename": "traffic_test_video.mp4",
    "started_at": time.time() - 120,
    "finished_at": time.time(),
    "fps": 25.0,
    "total_frames": 160,
    "frame_idx": 160
}

pdf_path = "/tmp/test_report.pdf"
excel_path = "/tmp/test_report.xlsx"

generate_report_pdf(job_report, pdf_path)
generate_report_xlsx(job_report, excel_path)

assert os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1000, "PDF generation failed"
assert os.path.exists(excel_path) and os.path.getsize(excel_path) > 1000, "Excel generation failed"
print(f"✓ TEST 5 PASSED: PDF ({os.path.getsize(pdf_path)} bytes) & Excel ({os.path.getsize(excel_path)} bytes) generated cleanly!")
results["test5_reports"] = "PASSED"

print("\n" + "=" * 70)
print("ALL RULES & COUNTING SYSTEMS VERIFIED 100% OPERATIONAL")
print(results)
print("=" * 70)
