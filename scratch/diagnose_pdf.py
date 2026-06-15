"""Diagnostic script for CSET333_Syllabus.pdf outline extraction issue writing to file."""

import sys
from pathlib import Path
from collections import Counter

# Add project root to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar
import src.heading_logic as hl

PDF_PATH = "/Users/shouryatuhar/Downloads/CSET333_Syllabus.pdf"
OUT_PATH = "/Users/shouryatuhar/Downloads/docintel-ai-main/scratch/pdf_diagnosis_report.txt"

def diagnose():
    path = Path(PDF_PATH)
    if not path.exists():
        with open(OUT_PATH, "w") as out:
            out.write(f"Error: {PDF_PATH} does not exist!")
        return

    report = []
    report.append("=== DIAGNOSING CSET333_Syllabus.pdf ===\n")

    # 1. Raw text from page 1
    report.append("--- 1. Raw Text Extracted from Page 1 (first 1500 chars) ---")
    page_layouts = list(extract_pages(str(PDF_PATH)))
    if not page_layouts:
        report.append("No pages found in PDF!")
        with open(OUT_PATH, "w") as out:
            out.write("\n".join(report))
        return
    
    p1 = page_layouts[0]
    p1_text = ""
    for element in p1:
        if isinstance(element, LTTextContainer):
            p1_text += element.get_text()
    
    report.append(p1_text[:1500])
    report.append("-" * 60 + "\n")

    # 2. Font statistics & sizes
    report.append("--- 2. Font sizes and names detected (Top 30) ---")
    font_stats = hl.extract_font_styles(str(PDF_PATH))
    for style, count in font_stats.most_common(30):
        report.append(f"Font: {style[0]}, Size: {style[1]} -> Count: {count}")
    report.append("-" * 60 + "\n")

    # Compute thresholds
    thresholds = hl.compute_size_thresholds(font_stats)
    report.append("Derived Thresholds:")
    report.append(f"H1: {thresholds['H1']}")
    report.append(f"H2: {thresholds['H2']}")
    report.append(f"H3: {thresholds['H3']}")
    report.append("-" * 60 + "\n")

    # 3. Candidate headings detected
    report.append("--- 3. Candidate Headings (All raw candidates before merge) ---")
    candidates = list(hl.iter_heading_candidates(str(PDF_PATH), thresholds))
    for idx, cand in enumerate(candidates):
        report.append(f"{idx}: Page {cand['page']}, Level: {cand['level']}, Size: {cand['size']}, Bold: {cand['is_bold']}, Score: {cand['score']}, Text: '{cand['text']}'")
    report.append("-" * 60 + "\n")

    # 4. Qualified and merged headings
    report.append("--- 4. Qualified Headings (score >= MIN_HEADING_SCORE) ---")
    qualified = [item for item in candidates if item["score"] >= hl.MIN_HEADING_SCORE]
    for idx, cand in enumerate(qualified):
        report.append(f"{idx}: Page {cand['page']}, Level: {cand['level']}, Size: {cand['size']}, Bold: {cand['is_bold']}, Score: {cand['score']}, Text: '{cand['text']}'")
    report.append("-" * 60 + "\n")

    report.append("--- 5. Merged Headings ---")
    headings = hl.merge_multiline_headings(qualified)
    for idx, h in enumerate(headings):
        report.append(f"{idx}: Page {h['page']}, Level: {h['level']}, Text: '{h['text']}'")
    report.append("-" * 60 + "\n")

    # Title selection explanation
    title_candidate = None
    for candidate in qualified:
        if candidate["page"] == 1 and candidate["level"] == "H1":
            title_candidate = candidate["text"]
            break
    report.append("--- Title Selection Logic ---")
    report.append(f"First H1 on Page 1: '{title_candidate}'")
    report.append(f"First merged heading overall: '{headings[0]['text'] if headings else 'None'}'")
    title = title_candidate or (headings[0]["text"] if headings else "")
    report.append(f"Selected Title: '{title}'")
    report.append("-" * 60 + "\n")

    with open(OUT_PATH, "w") as out:
        out.write("\n".join(report))

if __name__ == "__main__":
    diagnose()
