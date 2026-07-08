from pathlib import Path
from typing import Dict

from PIL import Image, ImageDraw, ImageFont

from .pipeline import scan


def _font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def create_label(path: Path):
    image = Image.new("RGB", (1600, 2200), "white")
    draw = ImageDraw.Draw(image)
    y = 120
    draw.text((180, y), "OLD TOM DISTILLERY", fill="black", font=_font(92, True))
    y += 150
    draw.text((250, y), "KENTUCKY STRAIGHT", fill="black", font=_font(58, True))
    y += 80
    draw.text((350, y), "BOURBON WHISKEY", fill="black", font=_font(58, True))
    y += 150
    draw.text((400, y), "45% Alc./Vol. (90 Proof)", fill="black", font=_font(48))
    y += 80
    draw.text((650, y), "750 mL", fill="black", font=_font(48))
    y += 180
    draw.text((100, y), "GOVERNMENT WARNING:", fill="black", font=_font(40, True))
    y += 65
    warning_lines = [
        "(1) According to the Surgeon General, women should not drink alcoholic",
        "beverages during pregnancy because of the risk of birth defects.",
        "(2) Consumption of alcoholic beverages impairs your ability to drive a",
        "car or operate machinery, and may cause health problems.",
    ]
    for line in warning_lines:
        draw.text((100, y), line, fill="black", font=_font(32))
        y += 50
    image.save(path, quality=95)


def run_self_test() -> Dict[str, object]:
    work = Path("self-test-input")
    output = Path("self-test-output")
    work.mkdir(exist_ok=True)
    label = work / "synthetic_label.jpg"
    create_label(label)

    manifest = work / "manifest.csv"
    manifest.write_text(
        "filename,application_id,brand_name,class_type,alcohol_content,"
        "net_contents,producer_name,producer_address,country_of_origin,imported\n"
        "synthetic_label.jpg,SELFTEST-1,OLD TOM DISTILLERY,"
        "KENTUCKY STRAIGHT BOURBON WHISKEY,45% Alc./Vol.,750 mL,,,,false\n",
        encoding="utf-8",
    )

    summary = scan(
        str(work), str(manifest), str(output),
        workers=1, recursive=False, limit=None, aggressive=False
    )
    print("")
    print("Self-test output:", summary["results_csv"])
    print("Completed:", summary["completed"], "Errors:", summary["errors"])
    return summary
