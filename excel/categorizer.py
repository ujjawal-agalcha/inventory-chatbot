import re
from typing import Optional, Tuple
from excel.normalizer import normalize_text

# ============================================================
# CATEGORY INFERENCE RULES
# ============================================================
CATEGORY_KEYWORDS = {
    "ESP Modules": ["esp32", "esp8266", "nodemcu", "devkit", "wroom", "esp-32"],
    "Arduino Boards": ["arduino", "uno", "nano", "mega", "leonardo"],
    "Motor Drivers": ["driver", "l298n", "bts7960", "tb6612"],
    "Motors": ["motor", "servo", "sg90", "mg996r", "stepper", "nema", "gear motor"],
    "Sensors": ["sensor", "ultrasonic", "hc-sr04", "pir", "dht11", "dht22", "mpu6050", "gyroscope", "ir obstacle"],
    "Batteries": ["battery", "18650", "lipo", "rechargeable", "cell"],
    "Displays": ["display", "lcd", "oled", "tft", "screen"],
    "Relays": ["relay", "channel relay"],
    "Communication": ["bluetooth", "hc-05", "gsm", "sim800l", "gps", "neo-6m", "lora", "zigbee", "rfid"],
    "Components": ["screw", "nut", "bolt", "resistor", "capacitor", "led", "breadboard", "jumper wire"],
    "Paper & Stationery": ["paper", "ream", "notebook", "notes", "sticky", "pen", "pencil", "marker", "whiteboard", "copier", "stationery"],
    "Office Equipment": ["stapler", "punch", "calculator", "cutter", "shredder", "laminator", "board", "extension", "socket"],
    "IT & Electronics": ["cartridge", "toner", "ink", "printer", "hdmi", "cable", "usb", "adapter", "mouse", "keyboard", "projector", "laptop", "monitor"],
    "Health & Hygiene": ["sanitiser", "sanitizer", "dettol", "soap", "mask", "disinfectant", "tissue", "cleaning"],
}


def infer_category(name: str, details: str = "") -> str:
    """Infer category from product name and details."""
    text = f"{name} {details}".lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw in text:
                return cat
    return "General Supplies"


def extract_category_and_subcategory(
    filename: str = "",
    sheet_name: str = "",
    item_name: str = "",
    details: str = "",
    row_category: Optional[str] = None,
    row_subcategory: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Extract normalized Category and Sub-category from filename, sheet name, row data, or inferred keywords.
    """
    cat = str(row_category).strip() if row_category and str(row_category).strip() else ""
    subcat = str(row_subcategory).strip() if row_subcategory and str(row_subcategory).strip() else ""

    # Clean filename without extension
    clean_fn = re.sub(r"\.xlsx?$", "", filename, flags=re.I).strip()

    # Check for "Category - Subcategory" or "Category – Subcategory" format in filename
    for sep in [" - ", " – ", " — "]:
        if sep in clean_fn:
            parts = clean_fn.split(sep, 1)
            if not cat:
                cat = parts[0].strip()
            if not subcat:
                subcat = parts[1].strip()
            break

    # Check sheet name
    if sheet_name:
        clean_sn = sheet_name.strip()
        for sep in [" - ", " – ", " — "]:
            if sep in clean_sn:
                sp = clean_sn.split(sep, 1)
                if not cat:
                    cat = sp[0].strip()
                if not subcat:
                    subcat = sp[1].strip()
                break
        if not subcat and clean_sn.lower() not in ("sheet1", "sheet2", "sheet", "data", "master", "overview", "dashboard"):
            subcat = clean_sn

    # If still missing category, infer from product name & details
    if not cat:
        inferred = infer_category(item_name, details)
        cat = inferred if inferred != "General Supplies" else "General"

    if not subcat:
        inferred = infer_category(item_name, details)
        subcat = inferred if inferred != "General Supplies" else "General"

    return cat, subcat
