"""Generates a client-facing PDF recommending an AI model/deployment approach
for faster vehicle-counting video analysis. Run directly: python docs/ai_model_recommendation.py
"""
import os
import time

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem, PageBreak,
)

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AI_Model_Recommendation.pdf")


def build():
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=22, spaceAfter=4)
    subtitle = ParagraphStyle("Sub", parent=styles["Normal"], fontSize=11, textColor=colors.grey, spaceAfter=16)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], spaceBefore=18, spaceAfter=8, textColor=colors.HexColor("#1a1a2e"))
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10.5, leading=15, spaceAfter=8)
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=9, leading=13, textColor=colors.HexColor("#555555"))

    doc = SimpleDocTemplate(OUT_PATH, pagesize=A4,
                             topMargin=2.2 * cm, bottomMargin=2 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)
    story = []

    story.append(Paragraph("AI Model Recommendation", title_style))
    story.append(Paragraph("Vehicle Detection &amp; Classification &mdash; Speed and Accuracy Options", subtitle))
    story.append(Paragraph(f"Prepared: {time.strftime('%Y-%m-%d')}", small))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Summary", h2))
    story.append(Paragraph(
        "The current system already uses a strong, purpose-built AI model for this task: a YOLOv8 "
        "object-detection model trained specifically on Bangladeshi road traffic (the BNVD dataset), "
        "which recognizes region-specific vehicles &mdash; rickshaw, CNG/auto-rickshaw, easy-bike, and others &mdash; "
        "that generic international models do not. The main constraint on speed today is not the model "
        "itself, but the hardware it runs on: a standard laptop CPU. The recommendation below is to keep "
        "the same model and improve the hardware it runs on, rather than switching to a different AI model.",
        body))

    story.append(Paragraph("Recommendation", h2))
    story.append(Paragraph(
        "<b>Run the existing model on a GPU (graphics processing unit) instead of a CPU.</b> "
        "GPUs are 10&ndash;30&times; faster than CPUs for this kind of AI workload. This alone is expected "
        "to bring a 1-hour video down from multiple hours of processing time to roughly 10&ndash;30 minutes, "
        "without changing what the system detects or how accurately.",
        body))
    story.append(Paragraph("Two ways to get GPU access:", body))
    story.append(ListFlowable([
        ListItem(Paragraph(
            "<b>Local GPU</b> &mdash; if the client's own computer has a dedicated NVIDIA graphics card, "
            "the same software already built can use it directly, at no extra recurring cost.", body)),
        ListItem(Paragraph(
            "<b>Rented cloud GPU</b> &mdash; if no local GPU is available, a cloud GPU can be rented by "
            "the hour (typically $0.20&ndash;$1.00/hour) from providers such as RunPod, Lambda Labs, or "
            "AWS. The same model and detection logic runs unchanged, just on rented hardware.", body)),
    ], bulletType="bullet", leftIndent=18))

    story.append(PageBreak())
    story.append(Paragraph("Options Considered", h2))

    rows = [
        ["Option", "Speed (1-hr video)", "Rickshaw/CNG\ndetection", "Ongoing cost", "Verdict"],
        ["Current setup\n(CPU only)", "Several hours", "Yes", "None", "Too slow for\nlarge videos"],
        ["Same model,\nlocal GPU", "~10–30 minutes", "Yes", "None\n(one-time hardware)", "Recommended\nif GPU available"],
        ["Same model,\nrented cloud GPU", "~10–30 minutes", "Yes", "~$0.20–$1/hr\nof processing", "Recommended\nif no local GPU"],
        ["Generic cloud\nvision API\n(e.g. Google, AWS)", "~10–30 minutes", "No — generic\nvehicle types only", "Per-frame or\nper-minute fees", "Not recommended:\nloses regional accuracy"],
        ["Newer YOLO version\n(v10/v11), same\nhardware", "Modest improvement", "Only if retrained\non the same dataset", "None", "Worth trying,\nsmaller impact"],
    ]
    table = Table(rows, colWidths=[3.3 * cm, 2.9 * cm, 3.0 * cm, 3.0 * cm, 3.0 * cm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f8")]),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#e8f5e9")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Why Not a Generic Cloud AI API?", h2))
    story.append(Paragraph(
        "General-purpose cloud vision services (Google Cloud, AWS Rekognition, and similar) can detect "
        "common vehicle types &mdash; cars, buses, trucks, motorcycles &mdash; quickly and without any "
        "local hardware. However, none of them recognize Bangladesh-specific vehicle types such as "
        "rickshaws, CNGs, or easy-bikes, which are central to the vehicle categories this project needs "
        "to report on. Using one of these services would mean losing that accuracy in exchange for "
        "convenience, and would introduce a recurring per-use cost. The current model already solves "
        "the accuracy problem; the recommended path solves the speed problem without giving that up.",
        body))

    story.append(Paragraph("Next Step", h2))
    story.append(Paragraph(
        "Confirm whether the client's computer has a dedicated NVIDIA graphics card. If yes, the existing "
        "software can be configured to use it directly at no additional cost. If no, the recommended path "
        "is a short trial on a rented cloud GPU to confirm real-world processing time on an actual "
        "1-hour video before committing to a longer-term setup.",
        body))

    doc.build(story)
    return OUT_PATH


if __name__ == "__main__":
    path = build()
    print(f"Saved: {path}")
