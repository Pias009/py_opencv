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
    if lines:
        story.append(Paragraph("Counts by Road / Direction", h2))
        rows = [["Line / Road", "In", "Out", "Total"]]
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
        note = ("Note: vehicle types are classified using a general-purpose detection model "
                "(bicycle, motorcycle, car/suv, bus, truck). Region-specific vehicle types not "
                "covered by the model (rickshaw, CNG, tempo, etc.) are reported as their closest "
                "match or omitted if undetected.")
        story.append(Spacer(1, 8))
        story.append(Paragraph(note, ParagraphStyle("Note", parent=normal, fontSize=8,
                                                       textColor=colors.grey)))

    doc.build(story)
    return output_path
