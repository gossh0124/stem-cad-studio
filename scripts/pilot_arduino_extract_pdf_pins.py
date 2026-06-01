"""scripts/pilot_arduino_extract_pdf_pins.py — Pilot-1.3

從 Arduino A000066-datasheet.pdf 抽出 §5.1 (POWER + AD) / §5.2 (IOL + IOH)
header pin 名稱表，作為 audit 的第三來源（次來源 — PDF 表格精度 1mm 或 inch）。

PDF 通常只給 pin name + function 描述，不給精確座標。本腳本只抽 name list，
audit step (Pilot-2.4) 用來確認「pin 名稱對應正確」這層維度，
座標的 0 誤差檢驗仍由 EAGLE BRD + KiCad mod 兩個主來源達成。
"""
from __future__ import annotations
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "data", "pcb_sources", "arduino_uno_r3", "A000066-datasheet.pdf"
)


def extract_pin_lines() -> list[tuple[int, str]]:
    """用 PyMuPDF 抽 PDF 全文，過濾出可能的 pin name 行。"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("[!] PyMuPDF 未安裝；嘗試: .venv/Scripts/pip install pymupdf")
        return []
    lines = []
    doc = fitz.open(PDF_PATH)
    for i in range(doc.page_count):
        page = doc[i]
        text = page.get_text() or ""
        for line in text.split("\n"):
            lines.append((i + 1, line))
    doc.close()
    return lines


PIN_TOKENS = (
    "IOREF", "RESET", "+3V3", "+5V", "GND", "VIN",
    "A0", "A1", "A2", "A3", "A4", "A5",
    "D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7",
    "D8", "D9", "D10", "D11", "D12", "D13",
    "SDA", "SCL", "MISO", "MOSI", "SCK", "AREF",
    "TX", "RX",
)


SECTIONS = ("5.1 JANALOG", "5.2 JDIGITAL", "5.3 ICSP")


def extract_section(raw: list[tuple[int, str]], header: str, max_rows: int = 80) -> list[tuple[int, str]]:
    """從 raw lines 抓 header 出現後的 max_rows 行（直到下一個 numeric section header）。"""
    out = []
    capture = False
    rows = 0
    for page, line in raw:
        stripped = line.strip()
        if stripped == header or stripped.startswith(header):
            capture = True
            out.append((page, f"### {stripped}"))
            continue
        if capture:
            # stop on next section header pattern like "5.4 ..." or "6 ..."
            if stripped and stripped[0].isdigit() and "." in stripped[:4] and stripped not in (header,):
                # likely next section
                next_sect = stripped.split()[0]
                if next_sect != header.split()[0] and "." in next_sect:
                    if next_sect.replace(".", "").isdigit():
                        break
            out.append((page, stripped))
            rows += 1
            if rows >= max_rows:
                break
    return out


def main():
    print(f"# PDF datasheet pin name extraction — {PDF_PATH}")
    raw = extract_pin_lines()
    if not raw:
        print("# (no output — PDF lib missing or PDF empty)")
        return
    print(f"# total raw lines: {len(raw)}\n")

    # Find ALL occurrences of each section header, keep the longest captured block
    # (TOC entries match too but capture nothing; real section body captures pin table)
    for sect in SECTIONS:
        best_rows = []
        # scan all occurrence indexes
        indexes = [i for i, (_, ln) in enumerate(raw) if ln.strip() == sect or ln.strip().startswith(sect)]
        for start_idx in indexes:
            sub_raw = raw[start_idx:]
            rows = extract_section(sub_raw, sect, max_rows=60)
            if len(rows) > len(best_rows):
                best_rows = rows
        rows = best_rows
        print(f"\n### Section '{sect}' — {len(rows)} lines captured (best of {len(indexes)} occurrences)")
        for page, line in rows:
            # filter empty lines and pure-numeric lines for readability
            if not line.strip():
                continue
            # safe-print to avoid cp950 issues
            try:
                print(f"  p{page:>2d}: {line}")
            except UnicodeEncodeError:
                print(f"  p{page:>2d}: <non-cp950 line, len={len(line)}>")

    # Build a found-token set
    import re
    def token_in(token: str, line: str) -> bool:
        return bool(re.search(rf"\b{re.escape(token)}\b", line))

    all_text = "\n".join(line for _, line in raw)
    found = sorted([t for t in PIN_TOKENS if token_in(t, all_text)])
    missing = sorted(set(PIN_TOKENS) - set(found))
    print(f"\n\n# Token coverage across whole PDF: {len(found)}/{len(PIN_TOKENS)}")
    print(f"#   found:  {found}")
    print(f"#   missing: {missing}")


if __name__ == "__main__":
    main()
