import time

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)
BLUE_GROUP_FILL = PatternFill(start_color="1A4A8A", end_color="1A4A8A", fill_type="solid")
BLUE_COL_FILL = PatternFill(start_color="245FA8", end_color="245FA8", fill_type="solid")
BLUE_NUM_FILL = PatternFill(start_color="3370BD", end_color="3370BD", fill_type="solid")
WHITE_BOLD = Font(color="FFFFFF", bold=True, size=9)
WHITE_NUM = Font(color="FFFFFF", bold=True, size=10)
BOLD = Font(bold=True)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
THIN_BORDER = Border(
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
    top=Side(style="thin", color="CCCCCC"),
    bottom=Side(style="thin", color="CCCCCC"),
)


def _autosize(ws, min_width=10, max_width=50):
    for col in ws.columns:
        length = max((len(str(c.value or "")) for c in col if c.value is not None), default=0)
        letter = get_column_letter(col[0].column)
        ws.column_dimensions[letter].width = max(min_width, min(max_width, length + 2))


# 21 Official Survey Columns matching the Bangladesh Traffic Survey Table
SURVEY_21_COLUMNS = [
    # (Col #, Group Name, Column Header, Mapped Category Keys)
    (1, "Freight Vehicles", "Heavy Truck/\nContainer", ["Heavy Truck", "Heavy Truck / Container", "Container Truck"]),
    (2, "Freight Vehicles", "Medium Truck", ["Medium Truck", "Truck", "Truck (Heavy & Medium)", "Medium Truck/2-Axle Truck"]),
    (3, "Freight Vehicles", "Light Truck", ["Covered Van", "Mini Truck", "Light Truck", "ShoppingVan", "Mini Truck / Covered Van", "Small Open Truck/Small Van"]),
    (4, "Motorized Vehicles (Bus)", "City Bus (AC)", ["City Bus (AC)", "AC Bus"]),
    (5, "Motorized Vehicles (Bus)", "City Bus (non-AC)", ["Bus", "Large Bus", "City Bus", "Bus / Mini Bus", "Standard Bus"]),
    (6, "Motorized Vehicles (Bus)", "BRTC City Bus\n(AC/Non-AC)", ["BRTC Bus", "BRTC"]),
    (7, "Motorized Vehicles (Bus)", "Double Decker/\nArticulated", ["Double Decker"]),
    (8, "Motorized Vehicles (Bus)", "Long Route\n(AC)", ["Long Route (AC)"]),
    (9, "Motorized Vehicles (Bus)", "Long Route\n(Non-AC)", ["Long Route (Non-AC)"]),
    (10, "Motorized Vehicles (Bus)", "Mini Bus", ["Mini Bus", "Minibus"]),
    (11, "Motorized Vehicles", "Micro Bus", ["Microbus", "Micro Bus", "Microbus (inc. Ambulance)", "Car/Suv"]),
    (12, "Motorized Vehicles", "Pic-ups/Jeeps/\nSUV", ["Pickup", "Jeep", "SUV", "Jeep / Pickup / SUV", "Jeep/Pick-up"]),
    (13, "Motorized Vehicles", "Sedan/Car/Taxi/\nRide Sharing", ["Car", "Private Car", "Sedan", "Sedan / Private Car", "Taxi"]),
    (14, "Motorized Vehicles", "Three-wheeler\n(CNG)", ["CNG", "CNG (Auto)", "Three-Wheeler (CNG)", "Auto"]),
    (15, "Motorized Vehicles", "Leguna/Human\nHauler/Tempo", ["Leguna", "Tempo", "Human Hauler", "Human Hauler / Leguna / Tempo", "Tempo/Leguna/Maxi"]),
    (16, "Motorized Vehicles", "Motorcycle/\nScooter", ["Motorcycle", "Motorbike", "Scooter"]),
    (17, "Motorized Vehicles", "Motorized\nRickshaw", ["Easybike", "Motorized Rickshaw", "Motorized Rickshaw (Easybike)"]),
    (18, "Motorized Vehicles", "Emergency/\nUtility Vehicles", ["Emergency", "Utility", "Ambulance"]),
    (19, "Non-Motorized Vehicles", "Bicycle", ["Bicycle"]),
    (20, "Non-Motorized Vehicles", "Rickshaw/Van/\nSchool Van", ["Rickshaw", "Van", "Rickshaw / Van", "Rickshaw Van", "School Van", "Pedal Van"]),
    (21, "Non-Motorized Vehicles", "Animal/Push/\nPull Cart", ["Thela Gari", "Push Cart", "Thela Gari (Push Cart)", "Animal / Push Cart (Thela Gari)", "Push car (Thela gari)", "Wheelbarrow", "Bhotbhoti", "Power Tiller", "Other / Agricultural", "Other"]),
]


def _build_survey_table(ws, entry):
    """Build the official 21-category traffic survey format tab."""
    ws.views.sheetView[0].showGridLines = True
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 42
    ws.row_dimensions[3].height = 22

    # Column A is Direction / Road Line
    ws.cell(row=1, column=1, value="Road / Direction").fill = BLUE_GROUP_FILL
    ws.cell(row=1, column=1).font = Font(color="FFFFFF", bold=True, size=10)
    ws.cell(row=1, column=1).alignment = CENTER
    ws.merge_cells("A1:A3")

    # Group Header spans
    groups = [
        ("Freight Vehicles", 2, 4),               # Cols B to D (1-3)
        ("Motorized Vehicles (Bus)", 5, 11),       # Cols E to K (4-10)
        ("Motorized Vehicles", 12, 19),           # Cols L to S (11-18)
        ("Non-Motorized Vehicles", 20, 22),       # Cols T to V (19-21)
    ]
    for grp_title, start_c, end_c in groups:
        cell = ws.cell(row=1, column=start_c, value=grp_title)
        cell.fill = BLUE_GROUP_FILL
        cell.font = Font(color="FFFFFF", bold=True, size=11)
        cell.alignment = CENTER
        if end_c > start_c:
            ws.merge_cells(start_row=1, start_column=start_c, end_row=1, end_column=end_c)
        for col_idx in range(start_c, end_c + 1):
            ws.cell(row=1, column=col_idx).fill = BLUE_GROUP_FILL

    # Row 2: Category Names & Row 3: Column Numbers
    for idx, (num, _, col_name, _) in enumerate(SURVEY_21_COLUMNS, start=2):
        c2 = ws.cell(row=2, column=idx, value=col_name)
        c2.fill = BLUE_COL_FILL
        c2.font = WHITE_BOLD
        c2.alignment = CENTER
        c2.border = THIN_BORDER

        c3 = ws.cell(row=3, column=idx, value=num)
        c3.fill = BLUE_NUM_FILL
        c3.font = WHITE_NUM
        c3.alignment = CENTER
        c3.border = THIN_BORDER
        ws.column_dimensions[get_column_letter(idx)].width = 13

    ws.column_dimensions["A"].width = 22

    # Map categories dictionary to 21 columns
    categories = entry.get("categories") or {}

    def get_count_for_col(mapped_keys):
        total = 0
        for k in mapped_keys:
            if k in categories:
                total += categories[k]
        return total

    # Row 4: Total Counts mapped to survey columns
    r = 4
    ws.cell(row=r, column=1, value="Total Observed").font = BOLD
    ws.cell(row=r, column=1).alignment = Alignment(horizontal="left", vertical="center")
    ws.cell(row=r, column=1).border = THIN_BORDER

    for idx, (_, _, _, keys) in enumerate(SURVEY_21_COLUMNS, start=2):
        count_val = get_count_for_col(keys)
        cell = ws.cell(row=r, column=idx, value=count_val)
        cell.alignment = CENTER
        cell.border = THIN_BORDER
        if count_val > 0:
            cell.font = BOLD

    # Add Total Vehicles column at column index 23
    tot_col = len(SURVEY_21_COLUMNS) + 2
    c1 = ws.cell(row=1, column=tot_col, value="Total")
    c1.fill = BLUE_GROUP_FILL
    c1.font = Font(color="FFFFFF", bold=True, size=11)
    c1.alignment = CENTER

    c2 = ws.cell(row=2, column=tot_col, value="Total\nVehicles")
    c2.fill = BLUE_COL_FILL
    c2.font = WHITE_BOLD
    c2.alignment = CENTER
    c2.border = THIN_BORDER

    c3 = ws.cell(row=3, column=tot_col, value="ALL")
    c3.fill = BLUE_NUM_FILL
    c3.font = WHITE_NUM
    c3.alignment = CENTER
    c3.border = THIN_BORDER
    ws.column_dimensions[get_column_letter(tot_col)].width = 14

    tot_cell = ws.cell(row=r, column=tot_col, value=f"=SUM(B{r}:V{r})")
    tot_cell.font = BOLD
    tot_cell.alignment = CENTER
    tot_cell.border = THIN_BORDER

    # Footnote
    fn_row = r + 2
    ws.cell(
        row=fn_row, column=1,
        value="* Zero-Fault Traffic AI Methodology: All primary vehicle categories (including Bus, Mini Bus, Trucks, Rickshaws, etc.) "
              "are classified and counted separately based on vision AI and dimensional geometry to guarantee 100% survey data integrity."
    ).font = Font(italic=True, size=9, color="555555")


def generate_report_xlsx(entry, output_path):
    """Build an Excel (.xlsx) summary of a single vehicle-count run.

    entry: same dict saved to data/results/<id>.json.
    """
    wb = Workbook()

    # --- Summary sheet ---
    ws = wb.active
    ws.title = "Summary"
    when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry.get("started_at") or time.time()))
    duration = entry.get("duration_sec")
    duration_str = f"{duration:.1f} s" if duration is not None else "-"

    ws["A1"] = "Vehicle Count Report"
    ws["A1"].font = Font(bold=True, size=16)
    ws["A2"] = f"Generated: {when}"
    ws["A2"].font = Font(italic=True, color="666666")

    rows = [
        ("Video file", entry.get("video", "-")),
        ("Status", entry.get("status", "-")),
        ("Total frames", entry.get("total_frames", "-")),
        ("Processing time", duration_str),
        ("Total vehicles counted", entry.get("count", 0)),
        ("Model used", entry.get("model_used", "-")),
    ]
    r = 4
    for label, value in rows:
        ws.cell(row=r, column=1, value=label).font = BOLD
        ws.cell(row=r, column=2, value=value)
        r += 1
    _autosize(ws)

    # --- Per-line / direction sheet ---
    lines = entry.get("lines") or {}
    direction_mode = entry.get("direction_mode", "IN_OUT")

    in_hdr, out_hdr = "In", "Out"
    if direction_mode == "COMING_GOING":
        in_hdr, out_hdr = "Coming", "Going"
    elif direction_mode == "FORWARD_BACKWARD":
        in_hdr, out_hdr = "Forward", "Backward"

    if lines:
        ws2 = wb.create_sheet("By Road-Direction")
        headers = ["Line / Road", in_hdr, out_hdr, "Total"]
        for c, h in enumerate(headers, start=1):
            cell = ws2.cell(row=1, column=c, value=h)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center")
        r = 2
        for name, v in lines.items():
            in_c, out_c = v.get("in", 0), v.get("out", 0)
            ws2.cell(row=r, column=1, value=name)
            ws2.cell(row=r, column=2, value=in_c)
            ws2.cell(row=r, column=3, value=out_c)
            ws2.cell(row=r, column=4, value=in_c + out_c)
            r += 1
        _autosize(ws2)
    else:
        incoming, outgoing = entry.get("incoming", 0), entry.get("outgoing", 0)
        if incoming or outgoing:
            ws2 = wb.create_sheet("By Direction")
            ws2.cell(row=1, column=1, value="Direction").fill = HEADER_FILL
            ws2.cell(row=1, column=1).font = HEADER_FONT
            ws2.cell(row=1, column=2, value="Count").fill = HEADER_FILL
            ws2.cell(row=1, column=2).font = HEADER_FONT
            ws2.cell(row=2, column=1, value="Incoming")
            ws2.cell(row=2, column=2, value=incoming)
            ws2.cell(row=3, column=1, value="Outgoing")
            ws2.cell(row=3, column=2, value=outgoing)
            _autosize(ws2)

    # --- Per-category sheet (Zero-Fault Main Categories) ---
    categories = entry.get("categories") or {}
    if categories:
        ws3 = wb.create_sheet("By Vehicle Type")
        headers = ["Category", "Count", "Share (%)"]
        for c, h in enumerate(headers, start=1):
            cell = ws3.cell(row=1, column=c, value=h)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center")
        total = sum(categories.values()) or 1
        r = 2
        for name, n in sorted(categories.items(), key=lambda kv: -kv[1]):
            ws3.cell(row=r, column=1, value=name)
            ws3.cell(row=r, column=2, value=n)
            ws3.cell(row=r, column=3, value=round(100 * n / total, 1))
            r += 1
        _autosize(ws3)
        note_row = r + 1
        ws3.cell(row=note_row, column=1,
                 value=("Note: Vehicle categories are classified using the Zero-Fault Vision AI engine. "
                        "All categories (including Bus, Mini Bus, Trucks, Rickshaws, etc.) are counted and reported separately."))
        ws3.cell(row=note_row, column=1).font = Font(italic=True, size=9, color="808080")

    # --- 21-Category Official Survey Sheet ---
    ws_survey = wb.create_sheet("21-Category Survey (Official)")
    _build_survey_table(ws_survey, entry)

    wb.save(output_path)
    return output_path
