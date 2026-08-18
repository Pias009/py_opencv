import argparse
import json
import os
import shutil
import sys
import time
import uuid

from counter import CountingLine, box_lines, default_lines, run_counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(BASE_DIR, "data", "results")
RESULTS_INDEX = os.path.join(RESULTS_DIR, "index.json")

os.makedirs(RESULTS_DIR, exist_ok=True)


def day_results_dir(started_at=None):
    """Results folder for a run, grouped by the date it started: data/results/YYYY-MM-DD/.
    Created up front so a run that errors or is cancelled before finishing still has
    somewhere to save its partial result.
    """
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


def term_width():
    return shutil.get_terminal_size((80, 20)).columns


def render_progress(job, video_label):
    total = job.get("total_frames") or 0
    frame_idx = job.get("frame_idx", 0)
    count = job.get("count", 0)
    lines = job.get("lines", {})
    categories = job.get("categories", {})
    speed_mode = job.get("speed_mode")
    reanalyzed = job.get("reanalyzed", 0)
    pct = (frame_idx / total * 100) if total else 0

    per_line = "  ".join(f"{name}[in:{v['in']} out:{v['out']}]" for name, v in lines.items())
    cat_str = "  ".join(f"{k}:{v}" for k, v in categories.items()) if categories else ""
    speed_str = f"speed:{speed_mode}" if speed_mode else ""
    reanalyze_str = f"re-checked:{reanalyzed}" if reanalyzed else ""
    suffix = (f"] {pct:5.1f}%  frame {frame_idx}/{total}  total: {count}  {per_line}  "
              f"{cat_str}  {speed_str}  {reanalyze_str}   ")
    bar_width = max(10, min(40, term_width() - len(suffix) - 1))
    filled = int(bar_width * pct / 100)
    bar = "#" * filled + "-" * (bar_width - filled)

    sys.stdout.write("\r[" + bar + suffix)
    sys.stdout.flush()


def prompt_video_path():
    while True:
        path = input("Video path (or drag & drop file here): ").strip().strip("'\"")
        if not path:
            print("Please enter a path.")
            continue
        if not os.path.isfile(path):
            print(f"File not found: {path}")
            continue
        return path


def prompt_yes_no(label, default=True):
    suffix = "Y/n" if default else "y/N"
    raw = input(f"{label} [{suffix}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def prompt_float(label, default):
    raw = input(f"{label} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print("Invalid number, using default.")
        return default


def prompt_int(label, default):
    raw = input(f"{label} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print("Invalid number, using default.")
        return default


def show_history():
    history = load_history()
    if not history:
        print("No runs yet.")
        return
    print(f"\n{'When':<20} {'Video':<25} {'Total':>6} {'Frames':>7} {'Status':<10}  Per-line")
    print("-" * 100)
    for item in history[:15]:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(item["started_at"])) if item.get("started_at") else "-"
        video = (item.get("video") or "")[:25]
        lines = item.get("lines") or {}
        if lines:
            per_line = "  ".join(f"{name}(in:{v['in']},out:{v['out']})" for name, v in lines.items())
        else:
            per_line = f"(in:{item.get('incoming', 0)},out:{item.get('outgoing', 0)})"
        categories = item.get("categories") or {}
        if categories:
            per_line += "  |  " + ", ".join(f"{k}:{v}" for k, v in categories.items())
        print(f"{when:<20} {video:<25} {item.get('count', 0):>6} {item.get('total_frames', 0):>7} "
              f"{item.get('status', ''):<10}  {per_line}")
    print()


def parse_line_spec(spec, frame_w, frame_h):
    """Parse 'name:x1,y1,x2,y2' or 'name:pct' (horizontal line at pct height) into a CountingLine."""
    if ":" not in spec:
        sys.exit(f"Invalid --line spec (expected name:x1,y1,x2,y2 or name:0.0-1.0): {spec}")
    name, rest = spec.split(":", 1)
    parts = rest.split(",")
    if len(parts) == 1:
        pct = float(parts[0])
        y = int(frame_h * pct)
        return CountingLine(name, 25, y, frame_w - 25, y)
    if len(parts) == 4:
        x1, y1, x2, y2 = (int(float(p)) for p in parts)
        return CountingLine(name, x1, y1, x2, y2)
    sys.exit(f"Invalid --line spec (expected 4 coordinates or a single pct): {spec}")


def prompt_lines(frame_w, frame_h):
    print(f"\nVideo resolution: {frame_w}x{frame_h}")
    print("Define one counting line per road/direction (e.g. North, South, East, West).")
    print("For each: give a height fraction (0-1) for a straight horizontal line,")
    print("or four coordinates x1,y1,x2,y2 for a custom-angled line.\n")

    lines = []
    n = prompt_int("How many roads/directions to track", 1)
    for i in range(n):
        default_name = f"Line{i + 1}"
        name = input(f"  Name for line {i + 1} [{default_name}]: ").strip() or default_name
        raw = input(f"  Position for '{name}' (0-1 height, or x1,y1,x2,y2) [0.45]: ").strip() or "0.45"
        parts = raw.split(",")
        if len(parts) == 1:
            y = int(frame_h * float(parts[0]))
            lines.append(CountingLine(name, 25, y, frame_w - 25, y))
        else:
            x1, y1, x2, y2 = (int(float(p)) for p in parts)
            lines.append(CountingLine(name, x1, y1, x2, y2))
    return lines


def process_video(video_path, lines, min_width, min_height, show_window=False, classify=False,
                   classify_every_frame=False, imgsz=640, detect_every=1, model_key=None,
                   window_width=1280, auto_speed=True):
    job = {
        "status": "starting",
        "cancel": False,
        "done": False,
        "count": 0,
        "lines": {ln.name: {"in": 0, "out": 0} for ln in lines} if lines else {},
        "categories": {},
        "frame_idx": 0,
        "total_frames": 0,
    }

    video_label = os.path.basename(video_path)
    print(f"\nProcessing: {video_label}")
    if classify_every_frame:
        print("Classification mode (YOLOv8, every frame): most accurate, but slow "
              "(~8 fps on CPU, no GPU detected).")
    elif classify:
        print("Classification mode (hybrid): full-speed line-crossing tracking, "
              "YOLO only runs on each vehicle at the moment it crosses.")
    if show_window:
        print("A video window will open. Press ESC in that window (or Ctrl+C here) to stop early.\n")
    else:
        print("Press Ctrl+C to cancel.\n")

    job_id = uuid.uuid4().hex
    day_dir = day_results_dir()
    day = os.path.basename(day_dir)

    def build_entry():
        return {
            "id": job_id,
            "video": video_label,
            "count": job.get("count", 0),
            "lines": job.get("lines", {}),
            "categories": job.get("categories", {}),
            "model_used": job.get("model_used"),
            "final_speed_mode": job.get("speed_mode"),
            "reanalyzed_count": job.get("reanalyzed", 0),
            "total_frames": job.get("total_frames", 0),
            "status": job.get("status", "running"),
            "error": job.get("error"),
            "started_at": job.get("started_at"),
            "finished_at": job.get("finished_at"),
            "duration_sec": round((job.get("finished_at", 0) - job.get("started_at", 0)), 2)
            if job.get("started_at") and job.get("finished_at") else None,
            "date_dir": day,
        }

    json_path = os.path.join(day_dir, f"{job_id}.json")
    pdf_path = os.path.join(day_dir, f"{job_id}.pdf")
    xlsx_path = os.path.join(day_dir, f"{job_id}.xlsx")

    def refresh_reports():
        entry = build_entry()
        try:
            from report import generate_report_pdf
            generate_report_pdf(entry, pdf_path)
        except Exception:
            pass
        try:
            from excel_report import generate_report_xlsx
            generate_report_xlsx(entry, xlsx_path)
        except Exception:
            pass

    if classify_every_frame:
        from yolo_counter import run_counter_yolo as counter_fn
        extra_kwargs = {"imgsz": imgsz, "detect_every": detect_every}
    elif classify:
        from hybrid_counter import run_counter_hybrid as counter_fn, DEFAULT_MODEL_KEY
        extra_kwargs = {"min_width": min_width, "min_height": min_height,
                         "model_key": model_key or DEFAULT_MODEL_KEY,
                         "auto_speed": auto_speed}
    else:
        counter_fn = run_counter
        extra_kwargs = {"min_width": min_width, "min_height": min_height}

    import threading

    def pdf_refresh_loop():
        while not job.get("done"):
            refresh_reports()
            time.sleep(3)

    refresher = threading.Thread(target=pdf_refresh_loop, daemon=True)

    if show_window:
        # cv2.imshow/waitKey must run on the main thread, so the counter runs
        # synchronously here; the PDF/Excel refresher runs alongside it in the
        # background so results in data/results/ update live while it plays.
        refresher.start()
        try:
            counter_fn(video_path, job, lines=lines, show_window=True,
                      display_max_width=window_width or None, **extra_kwargs)
        except KeyboardInterrupt:
            job["cancel"] = True
        render_progress(job, video_label)
    else:
        t = threading.Thread(
            target=counter_fn,
            args=(video_path, job),
            kwargs={**extra_kwargs, "lines": lines},
            daemon=True,
        )
        t.start()
        refresher.start()

        try:
            while not job.get("done"):
                render_progress(job, video_label)
                time.sleep(0.1)
            render_progress(job, video_label)
        except KeyboardInterrupt:
            job["cancel"] = True
            while not job.get("done"):
                time.sleep(0.1)
            render_progress(job, video_label)

    print()

    is_error = job["status"] == "error"
    if is_error:
        print(f"Error: {job.get('error')}")
    else:
        status_word = {"finished": "Done", "cancelled": "Cancelled"}.get(job["status"], job["status"])
        per_line = "  ".join(f"{name}(in:{v['in']}, out:{v['out']})" for name, v in job.get("lines", {}).items())
        print(f"{status_word}. Total vehicles counted: {job.get('count', 0)}")
        if per_line:
            print(f"  {per_line}")
        categories = job.get("categories", {})
        if categories:
            print("  By category:")
            for name, n in sorted(categories.items(), key=lambda kv: -kv[1]):
                print(f"    {name}: {n}")

    # Always save whatever result exists, even on error or an incomplete/cancelled
    # run, so partial progress is never silently lost.
    entry = build_entry()
    save_history_entry(entry)
    with open(json_path, "w") as f:
        json.dump(entry, f, indent=2)
    print(f"Saved result to data/results/{day}/{job_id}.json")

    if is_error:
        return

    refresh_reports()
    print(f"Saved PDF report to data/results/{day}/{job_id}.pdf")
    print(f"Saved Excel report to data/results/{day}/{job_id}.xlsx\n")


def main():
    print("=" * 50)
    print(" Vehicle Counter (terminal)")
    print("=" * 50)

    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="Count vehicles crossing one or more lines in a video.")
        parser.add_argument("video", help="Path to the video file")
        parser.add_argument("--line-pos", type=float, default=0.45,
                             help="Single counting line position as a fraction of frame height (0-1). "
                                  "Ignored if --line is given. Default: 0.45")
        parser.add_argument("--line", action="append", default=[],
                             help="Add a named counting line: 'Name:pct' (horizontal, 0-1 height) or "
                                  "'Name:x1,y1,x2,y2' (custom segment). Repeatable for multiple roads/directions, "
                                  "e.g. --line North:0.2 --line South:0.8 --line East:100,100,100,600")
        parser.add_argument("--box", nargs="?", const=40, type=int, default=None, metavar="MARGIN",
                             help="Use a 4-sided North/South/West/East boundary box, centered in the frame "
                                  "and sized by --box-scale, instead of manual --line placement, so all "
                                  "lanes of an intersection cross it cleanly. Optional extra pixel margin "
                                  "to shrink it further (default: 40). Ignored if --line is given.")
        parser.add_argument("--box-scale", type=float, default=0.65, metavar="0-1",
                             help="Size of the --box boundary box as a fraction of the frame's width/height, "
                                  "centered in the frame. Default: 0.65 (about two-thirds of the frame, centered).")
        parser.add_argument("--min-width", type=int, default=40, help="Minimum contour width")
        parser.add_argument("--min-height", type=int, default=40, help="Minimum contour height")
        parser.add_argument("--no-window", action="store_true", help="Don't open a live video window")
        parser.add_argument("--window-width", type=int, default=1280,
                             help="Max width (px) of the live preview window; larger source video is "
                                  "scaled down to fit (detection still runs at full resolution). "
                                  "Set to 0 to disable scaling and show at native size. Default: 1280")
        parser.add_argument("--classify", action="store_true",
                             help="Classify each vehicle by type (bicycle, motorcycle, car/suv, bus, truck). "
                                  "Hybrid mode: fast blob-tracking counts crossings at full speed, YOLO only "
                                  "runs on the cropped vehicle at the moment it crosses (near full speed).")
        parser.add_argument("--classify-every-frame", action="store_true",
                             help="Like --classify but runs YOLO on every full frame instead of the hybrid "
                                  "approach. More classification context per vehicle, but much slower on CPU "
                                  "(~8 fps at 1080p, no GPU detected).")
        parser.add_argument("--imgsz", type=int, default=640,
                             help="YOLO inference resolution for --classify-every-frame. Default: 640 (full "
                                  "accuracy). Lower (e.g. 384, 320) is faster but misses small/distant vehicles.")
        parser.add_argument("--detect-every", type=int, default=1,
                             help="For --classify-every-frame: run YOLO every Nth frame, reuse boxes in "
                                  "between (faster, coarser, can miss crossings). Default: 1 (every frame)")
        parser.add_argument("--model", choices=["bnvd", "coco"], default=None,
                             help="Classification model: 'bnvd' (Bangladesh-specific, covers Rickshaw/CNG/"
                                  "Leguna/etc. — used automatically if downloaded) or 'coco' (standard "
                                  "YOLOv8: bicycle/motorcycle/car/bus/truck only). Default: bnvd if present.")
        parser.add_argument("--no-auto-speed", action="store_true",
                             help="For --classify: disable auto-speed. By default the classifier watches its "
                                  "own throughput against the video's frame rate and automatically shrinks "
                                  "the classification resolution on busy footage to keep up, then restores "
                                  "full detail once it catches up. Every crossing is still always classified — "
                                  "this only affects how much detail each classification pass uses, never "
                                  "which crossings get checked. Pass this flag to always run at full detail.")
        args = parser.parse_args()

        if not os.path.isfile(args.video):
            sys.exit(f"File not found: {args.video}")

        import cv2
        cap = cv2.VideoCapture(args.video)
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        if args.line:
            lines = [parse_line_spec(spec, frame_w, frame_h) for spec in args.line]
        elif args.box is not None:
            lines = box_lines(frame_w, frame_h, margin=args.box, scale=args.box_scale)
        else:
            lines = default_lines(frame_w, frame_h) if args.line_pos == 0.45 else \
                [parse_line_spec(f"Line1:{args.line_pos}", frame_w, frame_h)]

        process_video(args.video, lines, args.min_width, args.min_height,
                      show_window=not args.no_window,
                      classify=args.classify or args.classify_every_frame,
                      classify_every_frame=args.classify_every_frame,
                      imgsz=args.imgsz, detect_every=args.detect_every,
                      model_key=args.model, window_width=args.window_width,
                      auto_speed=not args.no_auto_speed)
        show_history()
        return

    while True:
        print("\n1) Count vehicles in a video")
        print("2) Show history")
        print("3) Quit")
        choice = input("> ").strip()

        if choice == "1":
            video_path = prompt_video_path()

            import cv2
            cap = cv2.VideoCapture(video_path)
            frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()

            show_window = prompt_yes_no("Open a live video window while scanning?", default=True)
            use_box = prompt_yes_no(
                "Use a 4-sided North/South/West/East boundary box centered in the frame "
                "(catches every lane of an intersection cleanly)?", default=False)
            if use_box:
                box_scale = prompt_float("Box size as a fraction of frame (0-1, centered)", 0.65)
                margin = prompt_int("Extra margin to shrink it further (px)", 0)
                lines = box_lines(frame_w, frame_h, margin=margin, scale=box_scale)
            else:
                multi = prompt_yes_no("Track multiple roads/directions (e.g. a 4-way intersection)?", default=False)
                if multi:
                    lines = prompt_lines(frame_w, frame_h)
                else:
                    line_pos_pct = prompt_float("Counting line position (0-1 of height)", 0.45)
                    lines = [parse_line_spec(f"Line1:{line_pos_pct}", frame_w, frame_h)]
            classify = prompt_yes_no(
                "Classify vehicle types (car/bus/truck/bike) using YOLO on each crossing?",
                default=False)
            min_width = prompt_int("Min box width (px)", 40)
            min_height = prompt_int("Min box height (px)", 40)
            window_width = prompt_int("Preview window max width (px, 0 = native size)", 1280) \
                if show_window else 1280
            process_video(video_path, lines, min_width, min_height,
                          show_window=show_window, classify=classify, window_width=window_width)
        elif choice == "2":
            show_history()
        elif choice == "3":
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
