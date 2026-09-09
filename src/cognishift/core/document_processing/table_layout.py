"""Recover ruled table cells from image geometry, without language-model guesses."""
import cv2
import numpy as np


def detect_ruled_tables(image_bytes, blocks):
    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return []
    ink = cv2.threshold(image, 180, 255, cv2.THRESH_BINARY_INV)[1]
    h, w = image.shape
    horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, w//25), 1)))
    vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(30, h//35))))
    grid = cv2.dilate(horizontal | vertical, np.ones((3, 3), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(grid)
    tables = []
    for x, y, width, height, area in stats[1:]:
        if width < w*.2 or height < h*.06 or area < 200:
            continue
        region = grid[y:y+height, x:x+width]
        _, _, holes, _ = cv2.connectedComponentsWithStats(255-region)
        cells = []
        for cx, cy, cw, ch, ca in holes[1:]:
            if cx == 0 or cy == 0 or cx+cw >= width or cy+ch >= height:
                continue
            if cw < 20 or ch < 15 or ca < cw*ch*.8:
                continue
            cells.append({'bbox':[int(x+cx),int(y+cy),int(x+cx+cw),int(y+cy+ch)]})
        if len(cells) < 4:
            continue
        def boundaries(values):
            groups=[]
            for value in sorted(values):
                if groups and value-groups[-1][-1] < 10:
                    groups[-1].append(value)
                else:
                    groups.append([value])
            return [sum(g)/len(g) for g in groups]
        xs=boundaries([c['bbox'][i] for c in cells for i in (0,2)])
        ys=boundaries([c['bbox'][i] for c in cells for i in (1,3)])
        for cell in cells:
            left,top,right,bottom=cell['bbox']
            col=min(range(len(xs)), key=lambda i:abs(xs[i]-left))
            row=min(range(len(ys)), key=lambda i:abs(ys[i]-top))
            end_col=min(range(len(xs)), key=lambda i:abs(xs[i]-right))
            end_row=min(range(len(ys)), key=lambda i:abs(ys[i]-bottom))
            contained=[b for b in blocks if b.bbox and left <= (b.bbox.x1+b.bbox.x2)/2 <= right and top <= (b.bbox.y1+b.bbox.y2)/2 <= bottom]
            contained.sort(key=lambda b:(b.bbox.y1,b.bbox.x1))
            cell.update(row=row,column=col,rowspan=max(1,end_row-row),colspan=max(1,end_col-col),
                        text=' '.join(b.text.strip() for b in contained), blocks=contained)
        tables.append({'bbox':[int(x),int(y),int(x+width),int(y+height)],
                       'rows':len(ys)-1,'columns':len(xs)-1,'cells':cells})
    return sorted(tables,key=lambda t:t['bbox'][1])
