"""Rule-based extraction and review checks for invoice / purchase-order PDFs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .pdf_reader import extract_text_by_page

MONEY_RE = re.compile(r"(?<![\w/])(?:\$|USD\s*)?([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d{2})|[0-9]+\.\d{2})(?!\w)", re.I)
ITEM_RE = re.compile(
    r"\b(?:item|product|description)\s*:\s*(.*?)\s*\|\s*"
    r"(?:qty|quantity)\s*:\s*(\d+(?:\.\d+)?)\s*\|\s*"
    r"unit\s*price\s*:\s*\$?([\d,]+\.\d{2})\s*\|\s*"
    r"(?:line\s*total|amount)\s*:\s*\$?([\d,]+\.\d{2})",
    re.I,
)
DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2},?\s+\d{4})\b",
    re.I,
)
def _field(value: str | None = None, page: int | None = None, evidence: str | None = None) -> dict[str, Any]:
    return {"value": value, "page": page, "evidence": evidence}


def _lines_by_page(path: Path) -> list[tuple[int, str]]:
    return [
        (page_number, line.strip())
        for page_number, page in enumerate(extract_text_by_page(path), start=1)
        for line in page.splitlines()
        if line.strip()
    ]


def _label_value(
    lines: list[tuple[int, str]],
    labels: tuple[str, ...],
    value_pattern: str = r"([A-Z0-9][A-Z0-9./_-]{1,})",
) -> dict[str, Any]:
    labels_pattern = "|".join(re.escape(label) for label in labels)
    pattern = re.compile(rf"\b(?:{labels_pattern})\b\s*(?:number|no\.?|#|:|-)?\s*[:#-]?\s*{value_pattern}", re.I)
    for page, line in lines:
        match = pattern.search(line)
        if match:
            return _field(match.group(1).strip(" :#-"), page, line[:500])
    return _field()


def _date_field(lines: list[tuple[int, str]]) -> dict[str, Any]:
    for page, line in lines:
        if re.search(r"\b(invoice\s+date|date\s+issued|issued\s+on|date)\b", line, re.I):
            match = DATE_RE.search(line)
            if match:
                return _field(match.group(0), page, line[:500])
    return _field()


def _labeled_money(lines: list[tuple[int, str]], labels: tuple[str, ...]) -> dict[str, Any]:
    labels_pattern = "|".join(re.escape(label) for label in labels)
    label_re = re.compile(rf"\b(?:{labels_pattern})\b", re.I)
    for page, line in lines:
        if label_re.search(line):
            amounts = list(MONEY_RE.finditer(line))
            if amounts:
                return _field(amounts[-1].group(1).replace(",", ""), page, line[:500])
    return _field()


def _line_items(lines: list[tuple[int, str]]) -> list[dict[str, Any]]:
    items = []
    for page, line in lines:
        match = ITEM_RE.search(line)
        if match:
            items.append({
                "description": match.group(1).strip(),
                "quantity": float(match.group(2)),
                "unit_price": float(match.group(3).replace(",", "")),
                "line_total": float(match.group(4).replace(",", "")),
                "page": page,
                "evidence": line[:500],
            })
    return items


def _total_field(lines: list[tuple[int, str]]) -> dict[str, Any]:
    labels = ("grand total", "invoice total", "total due", "amount due", "order total", "total")
    candidates: list[tuple[int, int, str, str]] = []
    for page, line in lines:
        lowered = line.lower()
        for priority, label in enumerate(labels):
            if re.search(rf"\b{re.escape(label)}\b", lowered):
                amounts = list(MONEY_RE.finditer(line))
                if amounts:
                    candidates.append((priority, page, amounts[-1].group(1).replace(",", ""), line[:500]))
                    break
    if not candidates:
        return _field()
    # Prefer explicitly labeled totals, and the last such total on the page/document.
    candidates.sort(key=lambda item: (item[0], -item[1]))
    _, page, amount, evidence = candidates[0]
    return _field(amount, page, evidence)


def extract_invoice_fields(path: Path) -> dict[str, Any]:
    """Extract fields explicitly labeled in an invoice; leave uncertain fields blank."""
    lines = _lines_by_page(path)
    if not lines:
        raise ValueError("No selectable text found in the invoice PDF; scanned PDFs need OCR first")
    return {
        "vendor": _label_value(lines, ("vendor", "supplier", "from"), r"(.{2,100}?)\s*(?:\||$)"),
        "invoice_number": _label_value(lines, ("invoice number", "invoice no", "invoice #", "invoice id")),
        "invoice_date": _date_field(lines),
        "po_number": _label_value(lines, ("purchase order", "po number", "po no", "po #")),
        "total": _total_field(lines),
        "tax": _labeled_money(lines, ("tax", "sales tax", "vat", "gst")),
        "line_items": _line_items(lines),
    }


def extract_purchase_order_fields(path: Path) -> dict[str, Any]:
    """Extract explicitly labeled purchase-order fields."""
    lines = _lines_by_page(path)
    if not lines:
        raise ValueError("No selectable text found in the purchase-order PDF; scanned PDFs need OCR first")
    return {
        "vendor": _label_value(lines, ("vendor", "supplier", "to"), r"(.{2,100}?)\s*(?:\||$)"),
        "po_number": _label_value(lines, ("purchase order", "po number", "po no", "po #")),
        "total": _total_field(lines),
        "line_items": _line_items(lines),
    }


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _finding(label: str, status: str, message: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return {"label": label, "status": status, "message": message, "evidence": evidence}


def review_invoice(invoice_path: Path, purchase_order_path: Path) -> dict[str, Any]:
    """Compare invoice header fields against a purchase order, retaining evidence."""
    invoice = extract_invoice_fields(invoice_path)
    purchase_order = extract_purchase_order_fields(purchase_order_path)
    findings = []

    invoice_vendor = invoice["vendor"]["value"]
    po_vendor = purchase_order["vendor"]["value"]
    vendor_evidence = [
        {"document": "Invoice", **invoice["vendor"]},
        {"document": "Purchase order", **purchase_order["vendor"]},
    ]
    if invoice_vendor and po_vendor:
        same_vendor = _normalize_name(invoice_vendor) == _normalize_name(po_vendor)
        findings.append(_finding("Vendor", "matched" if same_vendor else "mismatch",
                                 "Vendor names match." if same_vendor else "Vendor names differ; review the supplier.", vendor_evidence))
    else:
        findings.append(_finding("Vendor", "needs_review", "Could not extract both vendor names confidently.", vendor_evidence))

    invoice_po = invoice["po_number"]["value"]
    order_po = purchase_order["po_number"]["value"]
    po_evidence = [
        {"document": "Invoice", **invoice["po_number"]},
        {"document": "Purchase order", **purchase_order["po_number"]},
    ]
    if invoice_po and order_po:
        same_po = _normalize_name(invoice_po) == _normalize_name(order_po)
        findings.append(_finding("PO number", "matched" if same_po else "mismatch",
                                 "The invoice references this purchase order." if same_po else "The invoice PO number does not match the uploaded purchase order.", po_evidence))
    else:
        findings.append(_finding("PO number", "needs_review", "Could not extract both PO numbers confidently.", po_evidence))

    invoice_total = invoice["total"]["value"]
    po_total = purchase_order["total"]["value"]
    total_evidence = [
        {"document": "Invoice", **invoice["total"]},
        {"document": "Purchase order", **purchase_order["total"]},
    ]
    if invoice_total and po_total:
        invoice_amount, po_amount = float(invoice_total), float(po_total)
        within_order = invoice_amount <= po_amount + 0.01
        findings.append(_finding(
            "Invoice total vs. PO total",
            "matched" if within_order else "mismatch",
            f"Invoice total ${invoice_amount:,.2f} is within the PO amount ${po_amount:,.2f}." if within_order
            else f"Invoice total ${invoice_amount:,.2f} exceeds the PO amount ${po_amount:,.2f}.",
            total_evidence,
        ))
    else:
        findings.append(_finding("Invoice total vs. PO total", "needs_review", "Could not extract both totals confidently.", total_evidence))

    invoice_items = invoice["line_items"]
    po_items = purchase_order["line_items"]
    if invoice_items and po_items:
        po_items_by_name = {_normalize_name(item["description"]): item for item in po_items}
        item_mismatches = []
        item_checks = []
        for item in invoice_items:
            order_item = po_items_by_name.get(_normalize_name(item["description"]))
            if not order_item:
                item_mismatches.append(f"{item['description']} is not listed on the PO")
                item_checks.append({"document": "Invoice", **item})
                continue
            if item["quantity"] > order_item["quantity"] + 0.0001:
                item_mismatches.append(f"{item['description']} quantity exceeds the PO")
            if item["unit_price"] > order_item["unit_price"] + 0.01:
                item_mismatches.append(f"{item['description']} unit price exceeds the PO")
            if abs(item["quantity"] * item["unit_price"] - item["line_total"]) > 0.01:
                item_mismatches.append(f"{item['description']} invoice line total does not match quantity × unit price")
            if abs(order_item["quantity"] * order_item["unit_price"] - order_item["line_total"]) > 0.01:
                item_mismatches.append(f"{item['description']} PO line total does not match quantity × unit price")
            item_checks.extend([
                {"document": "Invoice", **item},
                {"document": "Purchase order", **order_item},
            ])
        if item_mismatches:
            findings.append(_finding("Line items", "mismatch", "; ".join(item_mismatches) + ".", item_checks))
        else:
            findings.append(_finding("Line items", "matched", "Invoice items and unit prices are within the PO quantities and prices.", item_checks))
    else:
        findings.append(_finding("Line items", "needs_review", "Could not extract comparable line-item rows from both PDFs. Use rows formatted as Item: name | Qty: n | Unit Price: 0.00 | Line Total: 0.00 for this prototype.", []))

    return {"invoice": invoice, "purchase_order": purchase_order, "findings": findings}
