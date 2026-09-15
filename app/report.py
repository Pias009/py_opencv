import time

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)


def generate_report_pdf(entry, output_path):
    """Build a PDF summary of a single vehicle-count run.

    entry: the same dict saved to data/results/<id>.json (video, count, lines,
           categories, total_frames, status, started_at, finished_at, duration_sec).
    """
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ReportTitle", parent=styles["Title"], fontSize=20, spaceAfter=4)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], spaceBefore=14, spaceAfter=6)
    normal = styles["Normal"]

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                             topMargin=2 * cm, bottomMargin=2 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)
    story = []

    story.append(Paragraph("Vehicle Count Report", title_style))
    when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry.get("started_at") or time.time()))
    story.append(Paragraph(f"Generated: {when}", normal))
    story.append(Spacer(1, 10))

    # --- Summary table ---
    duration = entry.get("duration_sec")
    duration_str = f"{duration:.1f} s" if duration is not None else "-"
    wrap_style = ParagraphStyle("Wrap", parent=normal, fontSize=10)
    summary_rows = [
        ["Video file", Paragraph(entry.get("video", "-"), wrap_style)],
        ["Status", entry.get("status", "-")],
        ["Total frames", str(entry.get("total_frames", "-"))],
        ["Processing time", duration_str],
        ["Total vehicles counted", str(entry.get("count", 0))],
    ]
    summary_table = Table(summary_rows, colWidths=[5 * cm, 10 * cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(summary_table)

    # --- Per-line / per-direction breakdown ---
    lines = entry.get("lines") or {}
    direction_mode = entry.get("direction_mode", "IN_OUT")

    in_hdr, out_hdr = "In", "Out"
    if direction_mode == "COMING_GOING":
        in_hdr, out_hdr = "Coming", "Going"
    elif direction_mode == "FORWARD_BACKWARD":
        in_hdr, out_hdr = "Forward", "Backward"

    if lines:
        story.append(Paragraph("Counts by Road / Direction", h2))
        rows = [["Line / Road", in_hdr, out_hdr, "Total"]]
        for name, v in lines.items():
            in_c, out_c = v.get("in", 0), v.get("out", 0)
            rows.append([name, str(in_c), str(out_c), str(in_c + out_c)])
        line_table = Table(rows, colWidths=[6 * cm, 3 * cm, 3 * cm, 3 * cm])
        line_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f7")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(line_table)
    else:
        incoming, outgoing = entry.get("incoming", 0), entry.get("outgoing", 0)
        if incoming or outgoing:
            story.append(Paragraph("Direction Breakdown", h2))
            rows = [["Direction", "Count"], ["Incoming", str(incoming)], ["Outgoing", str(outgoing)]]
            dir_table = Table(rows, colWidths=[6 * cm, 6 * cm])
            dir_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ]))
            story.append(dir_table)

    # --- Per-category breakdown ---
    categories = entry.get("categories") or {}
    if categories:
        story.append(Paragraph("Counts by Vehicle Type", h2))
        total = sum(categories.values()) or 1
        rows = [["Category", "Count", "Share"]]
        for name, n in sorted(categories.items(), key=lambda kv: -kv[1]):
            rows.append([name, str(n), f"{100 * n / total:.1f}%"])
        cat_table = Table(rows, colWidths=[8 * cm, 3 * cm, 3 * cm])
        cat_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f7")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(cat_table)
        note = ("Note: Vehicle categories are classified using the Zero-Fault Vision AI system "
                "(trained specifically on Bangladeshi traffic). Detailed vehicle categories "
                "(including Bus, Mini Bus, Trucks, Rickshaws, etc.) are detected and counted separately.")
        story.append(Spacer(1, 8))
        story.append(Paragraph(note, ParagraphStyle("Note", parent=normal, fontSize=8,
                                                       textColor=colors.grey)))

    doc.build(story)
    return output_path


def generate_batch_report_pdf(batch_entry, output_path):
    """Build a PDF consolidated summary of a 3-video batch count run."""
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("BatchReportTitle", parent=styles["Title"], fontSize=18, spaceAfter=4, textColor=colors.HexColor("#1A4A8A"))
    h2 = ParagraphStyle("BatchH2", parent=styles["Heading2"], fontSize=12, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#2C3E50"))
    normal = styles["Normal"]
    wrap_style = ParagraphStyle("WrapBatch", parent=normal, fontSize=9)

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                             topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                             leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    story = []

    story.append(Paragraph("3-Video Batch Vehicle Count — Consolidated Report", title_style))
    when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(batch_entry.get("started_at") or time.time()))
    duration = batch_entry.get("duration_sec")
    duration_str = f"{duration:.1f} s" if duration is not None else "-"
    story.append(Paragraph(f"Generated: {when}  |  Total Batch Duration: {duration_str}", normal))
    story.append(Spacer(1, 10))

    results = batch_entry.get("results") or []
    v1_res = results[0] if len(results) > 0 else {}
    v2_res = results[1] if len(results) > 1 else {}
    v3_res = results[2] if len(results) > 2 else {}

    v1_name = v1_res.get("video") or "Video 1"
    v2_name = v2_res.get("video") or "Video 2"
    v3_name = v3_res.get("video") or "Video 3"

    # --- Video Overview Table ---
    story.append(Paragraph("Batch Video Overview", h2))
    overview_rows = [
        ["Video #", "Filename", "Frames", "Time", "Total Count"],
        ["Video 1", Paragraph(v1_name, wrap_style), str(v1_res.get("total_frames", "-")), f"{v1_res.get('duration_sec', 0):.1f} s" if v1_res.get("duration_sec") else "-", str(v1_res.get("count", 0))],
        ["Video 2", Paragraph(v2_name, wrap_style), str(v2_res.get("total_frames", "-")), f"{v2_res.get('duration_sec', 0):.1f} s" if v2_res.get("duration_sec") else "-", str(v2_res.get("count", 0))],
        ["Video 3", Paragraph(v3_name, wrap_style), str(v3_res.get("total_frames", "-")), f"{v3_res.get('duration_sec', 0):.1f} s" if v3_res.get("duration_sec") else "-", str(v3_res.get("count", 0))],
    ]

    grand_total_counted = (v1_res.get("count", 0) + v2_res.get("count", 0) + v3_res.get("count", 0))
    overview_rows.append([
        "COMBINED", "All 3 Videos", "-", duration_str, str(grand_total_counted)
    ])

    overview_table = Table(overview_rows, colWidths=[2.5 * cm, 7 * cm, 2.5 * cm, 2.5 * cm, 2.8 * cm])
    overview_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A4A8A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (1, 1), (1, -1), "LEFT"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#DCE6F1")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(overview_table)
    story.append(Spacer(1, 12))

    # --- Consolidated Vehicle Category Matrix ---
    story.append(Paragraph("Consolidated Vehicle Counting Matrix (All 3 Videos)", h2))

    matrix_rows = [
        ["Vehicle Category", f"Video 1\n({v1_name[:12]})", f"Video 2\n({v2_name[:12]})", f"Video 3\n({v3_name[:12]})", "Combined Total", "Share"]
    ]

    cats1 = v1_res.get("categories") or {}
    cats2 = v2_res.get("categories") or {}
    cats3 = v3_res.get("categories") or {}
    all_cats = sorted(set(list(cats1.keys()) + list(cats2.keys()) + list(cats3.keys())),
                      key=lambda k: (cats1.get(k, 0) + cats2.get(k, 0) + cats3.get(k, 0)),
                      reverse=True)

    denom = grand_total_counted or 1
    for cat in all_cats:
        c1 = cats1.get(cat, 0)
        c2 = cats2.get(cat, 0)
        c3 = cats3.get(cat, 0)
        row_tot = c1 + c2 + c3
        share_str = f"{(row_tot / denom) * 100:.1f}%"
        matrix_rows.append([cat, str(c1), str(c2), str(c3), str(row_tot), share_str])

    # Grand total row
    matrix_rows.append([
        "GRAND TOTAL",
        str(v1_res.get("count", 0)),
        str(v2_res.get("count", 0)),
        str(v3_res.get("count", 0)),
        str(grand_total_counted),
        "100.0%"
    ])

    matrix_table = Table(matrix_rows, colWidths=[4.8 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 2.8 * cm, 2.2 * cm])
    matrix_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F7F9FC")]),
        ("BACKGROUND", (4, 1), (4, -2), colors.HexColor("#EAF2F8")),
        ("FONTNAME", (4, 1), (4, -2), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#1A4A8A")),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(matrix_table)

    note = ("Note: All 3 videos were sequentially analyzed using the Zero-Fault AI Computer Vision Engine. "
            "All vehicle types are accurately categorized, tracked across lines, and consolidated into this final count sheet.")
    story.append(Spacer(1, 10))
    story.append(Paragraph(note, ParagraphStyle("BatchNote", parent=normal, fontSize=8, textColor=colors.grey)))

    doc.build(story)
    return output_path

