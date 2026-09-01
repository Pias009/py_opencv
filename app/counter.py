import time

import cv2
import numpy as np

LARGURA_MIN = 40
ALTURA_MIN = 40
OFFSET = 8

MAX_TRACK_DISTANCE = 60   # px: max distance to match a detection to an existing track
MAX_MISSED_FRAMES = 15    # frames a track can go undetected before being dropped

LINE_COLORS = [
    (255, 127, 0), (0, 200, 255), (255, 0, 200), (0, 255, 100),
    (255, 255, 0), (180, 0, 255), (0, 128, 255), (128, 255, 0),
]


class CountingLine:
    """A named line segment (x1,y1)-(x2,y2) vehicles are counted against.

    inward_point: an optional (x, y) that "in" should point toward — e.g. an
    intersection's center for a boundary-box line. Without it, the two
    endpoints alone don't determine which side is "inward", so the normal's
    sign is an arbitrary artifact of point order: on a 4-sided box built from
    independent per-side coordinates, that arbitrary sign does NOT come out
    consistent across sides (verified: North/East end up correct, South/West
    inverted, for the same box). Passing inward_point makes "in" consistently
    mean "toward that point" on every line, regardless of how its endpoints
    were listed.
    """

    def __init__(self, name, x1, y1, x2, y2, inward_point=None):
        self.name = name
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.in_count = 0
        self.out_count = 0
        dx, dy = x2 - x1, y2 - y1
        length = (dx ** 2 + dy ** 2) ** 0.5 or 1.0
        # Unit normal to the line, used as the signed side/direction axis.
        self.nx, self.ny = -dy / length, dx / length

        if inward_point is not None:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ix, iy = inward_point
            # If the normal currently points away from inward_point, flip it
            # so "in" (side increasing) always means "toward inward_point".
            if (ix - mx) * self.nx + (iy - my) * self.ny < 0:
                self.nx, self.ny = -self.nx, -self.ny

    def signed_side(self, px, py):
        return (px - self.x1) * self.nx + (py - self.y1) * self.ny

    def distance_to_segment(self, px, py):
        dx, dy = self.x2 - self.x1, self.y2 - self.y1
        length_sq = dx * dx + dy * dy
        if length_sq == 0:
            return ((px - self.x1) ** 2 + (py - self.y1) ** 2) ** 0.5
        t = max(0.0, min(1.0, ((px - self.x1) * dx + (py - self.y1) * dy) / length_sq))
        proj_x, proj_y = self.x1 + t * dx, self.y1 + t * dy
        return ((px - proj_x) ** 2 + (py - proj_y) ** 2) ** 0.5

    def invert(self):
        """Flip the normal vector so IN becomes OUT and OUT becomes IN."""
        self.nx, self.ny = -self.nx, -self.ny


def default_lines(frame_w, frame_h):
    """Fallback: a single horizontal line at 45% height, spanning the frame."""
    y = int(frame_h * 0.45)
    return [CountingLine("Line1", 25, y, frame_w - 25, y)]


def vertical_line(frame_w, frame_h, pct=0.5):
    """A single vertical line down the frame at pct width (0-1)."""
    x = int(frame_w * pct)
    return [CountingLine("Line1", x, 25, x, frame_h - 25)]


def box_lines(frame_w, frame_h, margin=15, scale=0.88):
    """Four lines forming a small boundary box centered in the frame (North/South/
    West/East), sized at `scale` fraction of the frame's width/height, so all four
    approaches of an intersection cross it cleanly instead of chasing the far frame
    edges (which are often skewed or out of view for one or more lanes).

    margin: kept for backward compatibility / fine nudging, applied on top of the
            centered box (shrinks it further if > 0).
    scale: fraction (0-1) of frame width/height the box spans, centered in the frame.
           Default 0.65 = a box about two-thirds of the frame's size, centered.
    """
    box_w = frame_w * scale
    box_h = frame_h * scale
    x1 = int((frame_w - box_w) / 2) + margin
    y1 = int((frame_h - box_h) / 2) + margin
    x2 = int((frame_w + box_w) / 2) - margin
    y2 = int((frame_h + box_h) / 2) - margin
    center = ((x1 + x2) / 2, (y1 + y2) / 2)
    return [
        CountingLine("North", x1, y1, x2, y1, inward_point=center),
        CountingLine("South", x1, y2, x2, y2, inward_point=center),
        CountingLine("West", x1, y1, x1, y2, inward_point=center),
        CountingLine("East", x2, y1, x2, y2, inward_point=center),
    ]


class Track:
    __slots__ = ("id", "cx", "cy", "vx", "vy", "prev_side", "missed", "counted_lines")

    def __init__(self, track_id, cx, cy):
        self.id = track_id
        self.cx = cx
        self.cy = cy
        self.vx = 0.0              # px/frame, smoothed
        self.vy = 0.0
        self.prev_side = {}       # line name -> last signed side value
        self.missed = 0
        self.counted_lines = set()  # line names already counted for this track

    def predicted_pos(self):
        """Where this track should be next frame, assuming constant velocity.
        Used to match against detections instead of last-known position, so
        fast-moving or briefly-occluded vehicles don't drift outside the
        matching radius and get mistaken for a new track (which would miss
        their line crossing) or swap identity with a nearby vehicle.
        """
        return self.cx + self.vx, self.cy + self.vy


def pega_centro(x, y, w, h):
    return x + w // 2, y + h // 2


def run_counter(video_source, job, min_width=LARGURA_MIN, min_height=ALTURA_MIN,
                 line_pos_pct=0.45, lines=None, frame_sink=None, show_window=False,
                 on_crossing=None, display_max_width=1280):
    """Process a video, updating `job` (a dict-like status object) as it goes.

    lines: optional list of CountingLine objects (multi-line / multi-direction mode).
           If omitted, falls back to a single horizontal line at line_pos_pct.
    display_max_width: if show_window is True and the frame is wider than this, the
                        preview window is scaled down to fit (detection still runs at
                        full resolution — only the displayed copy is resized).

    job keys written: status, total_frames, frame_idx, count, lines (per-line in/out),
                       error, done, started_at, finished_at
    frame_sink: optional callable(jpeg_bytes) invoked per processed frame for live streaming.
    show_window: if True, pop up an OpenCV window showing the annotated video live (ESC to stop early).
    on_crossing: optional callable(frame, line, x, y, w, h) -> bool, invoked the moment a
                 blob crosses a line, with the full (unannotated at call time) frame and
                 its bounding box. Return False to veto the crossing (e.g. classifier found
                 no real vehicle there — a pedestrian or noise blob) so it is not counted;
                 return True (or None) to accept it. Lets a slower per-crossing classifier
                 both verify and label crossings without paying its cost on every frame.

    Detection uses MOG2 background subtraction with shadow removal, then a lightweight
    nearest-neighbor tracker assigns an ID to each moving blob across frames so every
    vehicle is counted exactly once per line it crosses, with direction (in/out) resolved
    from which side of the line it approached from.
    """
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        job["status"] = "error"
        job["error"] = f"Could not open video: {video_source}"
        job["done"] = True
        return

    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if not lines:
        lines = default_lines(frame_w, frame_h)

    subtracao = cv2.createBackgroundSubtractorMOG2(
        history=500, varThreshold=40, detectShadows=True
    )
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))

    tracks = []
    next_track_id = 0
    carros = 0

    job["status"] = "running"
    job["total_frames"] = total_frames
    job["frame_idx"] = 0
    job["count"] = 0
    job["lines"] = {ln.name: {"in": 0, "out": 0} for ln in lines}
    job["started_at"] = time.time()

    frame_idx = 0
    while True:
        if job.get("cancel"):
            job["status"] = "cancelled"
            break

        ret, frame1 = cap.read()
        if not ret:
            break
        frame_idx += 1

        blur = cv2.GaussianBlur(frame1, (5, 5), 0)
        fgmask = subtracao.apply(blur)
        # Drop shadow pixels (MOG2 marks them as 127); keep only solid foreground (255).
        _, mask = cv2.threshold(fgmask, 200, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close, iterations=2)
        mask = cv2.dilate(mask, kernel_open, iterations=1)

        contorno, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for i, ln in enumerate(lines):
            color = LINE_COLORS[i % len(LINE_COLORS)]
            cv2.line(frame1, (ln.x1, ln.y1), (ln.x2, ln.y2), color, 3)
            cv2.putText(frame1, ln.name, (ln.x1 + 6, ln.y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        detections = []
        for c in contorno:
            (x, y, w, h) = cv2.boundingRect(c)
            if w >= min_width and h >= min_height and cv2.contourArea(c) >= (min_width * min_height * 0.5):
                detections.append((x, y, w, h))

        # Match detections to existing tracks by nearest centroid to each
        # track's *predicted* position (constant-velocity extrapolation), not
        # its last-known one. A vehicle moving fast enough to travel more than
        # MAX_TRACK_DISTANCE in one frame would otherwise fall outside the
        # search radius, get treated as a brand-new track, and silently lose
        # its line-crossing history — this is the single biggest source of
        # missed/duplicate counts on fast traffic. Matching is also resolved
        # globally-greedy (best pair first, across all track/detection pairs)
        # rather than track-by-list-order, so two vehicles passing close
        # together near a line are less likely to swap identities.
        candidates = []
        for ti, tr in enumerate(tracks):
            pred_x, pred_y = tr.predicted_pos()
            # A track that's been coasting on prediction (missed detections)
            # gets a wider search radius per missed frame, since its last
            # real position is stale and its predicted one carries more
            # uncertainty the longer it's gone unseen.
            radius = MAX_TRACK_DISTANCE * (1 + 0.5 * tr.missed)
            for di, (x, y, w, h) in enumerate(detections):
                dcx, dcy = pega_centro(x, y, w, h)
                dist = ((pred_x - dcx) ** 2 + (pred_y - dcy) ** 2) ** 0.5
                if dist < radius:
                    candidates.append((dist, ti, di))
        candidates.sort(key=lambda c: c[0])

        matched_tracks, matched_detections = set(), set()
        matches = []
        for dist, ti, di in candidates:
            if ti in matched_tracks or di in matched_detections:
                continue
            matches.append((ti, di))
            matched_tracks.add(ti)
            matched_detections.add(di)

        unmatched_tracks = [ti for ti in range(len(tracks)) if ti not in matched_tracks]
        unmatched_detections = [di for di in range(len(detections)) if di not in matched_detections]

        def update_track(tr, cx, cy, box):
            # Smooth (exponential moving average) the velocity estimate so a
            # single noisy detection doesn't swing the prediction wildly.
            new_vx, new_vy = cx - tr.cx, cy - tr.cy
            tr.vx = 0.6 * new_vx + 0.4 * tr.vx
            tr.vy = 0.6 * new_vy + 0.4 * tr.vy

            if getattr(tr, 'counted_globally', False):
                tr.cx, tr.cy = cx, cy
                tr.missed = 0
                return

            for ln in lines:
                side = ln.signed_side(cx, cy)
                prev = tr.prev_side.get(ln.name)
                if (prev is not None and prev * side <= 0
                        and ln.distance_to_segment(cx, cy) <= max(OFFSET * 4, 40)
                        and ln.name not in tr.counted_lines):
                    accepted = True
                    if on_crossing is not None:
                        accepted = on_crossing(frame1, ln, *box)
                        if accepted is None:
                            accepted = True
                    if accepted:
                        tr.counted_lines.add(ln.name)
                        tr.counted_globally = True
                        if side > prev:
                            ln.in_count += 1
                        else:
                            ln.out_count += 1
                        nonlocal carros
                        carros += 1
                        break
                tr.prev_side[ln.name] = side
            tr.cx, tr.cy = cx, cy
            tr.missed = 0

        for ti, di in matches:
            x, y, w, h = detections[di]
            cx, cy = pega_centro(x, y, w, h)
            tr = tracks[ti]
            update_track(tr, cx, cy, (x, y, w, h))
            cv2.rectangle(frame1, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.circle(frame1, (cx, cy), 4, (0, 0, 255), -1)

        for di in unmatched_detections:
            x, y, w, h = detections[di]
            cx, cy = pega_centro(x, y, w, h)
            tr = Track(next_track_id, cx, cy)
            next_track_id += 1
            for ln in lines:
                tr.prev_side[ln.name] = ln.signed_side(cx, cy)
            tracks.append(tr)
            cv2.rectangle(frame1, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.circle(frame1, (cx, cy), 4, (0, 0, 255), -1)

        for ti in unmatched_tracks:
            tracks[ti].missed += 1

        tracks = [tr for tr in tracks if tr.missed <= MAX_MISSED_FRAMES]

        overlay_lines = [("TOTAL: " + str(carros), (0, 0, 255), 1.1, 3)]
        for i, ln in enumerate(lines):
            color = LINE_COLORS[i % len(LINE_COLORS)]
            overlay_lines.append((f"{ln.name}  in:{ln.in_count} out:{ln.out_count}", color, 0.65, 2))

        line_height = 32
        y = frame_h - 20 - line_height * (len(overlay_lines) - 1)
        for text, color, scale, thickness in overlay_lines:
            cv2.putText(frame1, text, (15, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness)
            y += line_height

        job["frame_idx"] = frame_idx
        job["count"] = carros
        job["lines"] = {ln.name: {"in": ln.in_count, "out": ln.out_count} for ln in lines}

        if frame_sink is not None:
            ok, jpeg = cv2.imencode(".jpg", frame1, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                frame_sink(jpeg.tobytes())

        if show_window:
            display_frame, display_mask = frame1, mask
            if display_max_width and frame_w > display_max_width:
                scale = display_max_width / frame_w
                new_size = (display_max_width, int(frame_h * scale))
                display_frame = cv2.resize(frame1, new_size, interpolation=cv2.INTER_AREA)
                display_mask = cv2.resize(mask, new_size, interpolation=cv2.INTER_AREA)
            cv2.imshow("Vehicle Counter - Video", display_frame)
            cv2.imshow("Vehicle Counter - Detection", display_mask)
            if cv2.waitKey(1) == 27:
                job["cancel"] = True

    if show_window:
        cv2.destroyAllWindows()

    cap.release()
    job["finished_at"] = time.time()
    job["done"] = True
    if job["status"] == "running":
        job["status"] = "finished"
