"""Conservative geometric OCR formatting; never rewrite recognized facts."""
import re
from statistics import median


def format_ocr_blocks(blocks, threshold=0.8, detect_columns=True):
    """Order rows geometrically and retain separated cells and paragraph gaps.

    This is a row-first layout, not a semantic multi-column/table classifier.
    Missing coordinates retain provider order rather than inventing positions.
    """
    blocks = [b for b in blocks if b.text.strip()]
    warnings = []
    if not blocks:
        return "", [], ["No readable text detected; inspect the original page."]
    if detect_columns and all(b.bbox for b in blocks) and len(blocks) >= 8:
        height = median(max(1,b.bbox.y2-b.bbox.y1) for b in blocks)
        width = max(b.bbox.x2 for b in blocks)-min(b.bbox.x1 for b in blocks)
        narrow = [b for b in blocks if b.bbox.x2-b.bbox.x1 < width*.7]
        groups=[]
        for block in sorted(narrow,key=lambda b:b.bbox.x1):
            if groups and block.bbox.x1-max(b.bbox.x2 for b in groups[-1]) < height*1.5:
                groups[-1].append(block)
            else:
                groups.append([block])
        if 2 <= len(groups) <= 4 and all(len(g)>=3 for g in groups):
            top=min(b.bbox.y1 for b in narrow)
            bottom=max(b.bbox.y2 for b in narrow)
            spanning=[b for b in blocks if b not in narrow]
            # Mixed full-width text inside columns is ambiguous; retain row fallback.
            if not any(top < b.bbox.y1 < bottom for b in spanning):
                sections=[[b for b in spanning if b.bbox.y1<=top]]+groups+[[b for b in spanning if b.bbox.y1>=bottom]]
                texts=[]
                ordered=[]
                for section in sections:
                    if section:
                        text, sequence, notes=format_ocr_blocks(section,threshold,False)
                        texts.append(text); ordered.extend(sequence); warnings.extend(notes)
                return '\n\n'.join(texts), ordered, list(dict.fromkeys(warnings))
    if any(b.bbox is None for b in blocks):
        warnings.append("Layout coordinates missing; original recognition order retained.")
        rows = [[b] for b in blocks]
        height = 1
    else:
        height = median(max(1, b.bbox.y2 - b.bbox.y1) for b in blocks)
        rows = []
        for block in sorted(blocks, key=lambda b: (b.bbox.y1, b.bbox.x1)):
            center = (block.bbox.y1 + block.bbox.y2) / 2
            if rows and abs(center - median((b.bbox.y1+b.bbox.y2)/2 for b in rows[-1])) <= height * 0.45:
                rows[-1].append(block)
            else:
                rows.append([block])
        rows = [sorted(row, key=lambda b: b.bbox.x1) for row in rows]
    lines = []
    ordered = []
    previous_bottom = None
    for row in rows:
        positioned = all(b.bbox is not None for b in row)
        if positioned and previous_bottom is not None and min(b.bbox.y1 for b in row) - previous_bottom > height * 0.8:
            lines.append("")
        line = ""
        for index, block in enumerate(row):
            text = re.sub(r"\s+", " ", block.text).strip()
            suspect_measurement = bool(re.search(r'(?<!\w)[A-Za-z]+\d+(?:\.\d+)?\s*(?:kPa|Pa|PSI|bar|C|mm/s)\b',text,re.I))
            if block.confidence is None or block.confidence < threshold or suspect_measurement:
                text += " [OCR uncertain]"
                if "Low-confidence text requires source verification." not in warnings:
                    warnings.append("Low-confidence text requires source verification.")
            if index:
                gap = block.bbox.x1 - row[index-1].bbox.x2 if positioned else 0
                line += " | " if gap > height * 1.5 else " "
                if gap > height * 1.5 and "Separated cells/columns preserved row-wise; verify reading order against the page." not in warnings:
                    warnings.append("Separated cells/columns preserved row-wise; verify reading order against the page.")
            line += text
            ordered.append(block)
        lines.append(line)
        previous_bottom = max(b.bbox.y2 for b in row) if positioned else None
    return "\n".join(lines).strip(), ordered, warnings
