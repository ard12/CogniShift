import io
import pytest
from PIL import Image, ImageDraw, ImageFont
from cognishift.core.document_processing.layout import format_ocr_blocks
from cognishift.core.document_processing.schemas import OCRTextBlock, BoundingBox
from cognishift.core.document_processing.ocr_provider import RapidOCREngine


def block(text, x, y, width=100, confidence=0.99):
    return OCRTextBlock(text=text, confidence=confidence,
        bbox=BoundingBox(x1=x, y1=y, x2=x+width, y2=y+20))


def test_scrambled_rows_and_paragraphs():
    text, ordered, warnings = format_ocr_blocks([
        block('Final finding.', 10, 130), block('REPORT', 10, 10),
        block('Pressure: 492.5 PSI', 10, 60), block('Temperature: 92.1 C', 10, 85)])
    assert text == 'REPORT\n\nPressure: 492.5 PSI\nTemperature: 92.1 C\n\nFinal finding.'
    assert ordered[0].text == 'REPORT'
    assert not warnings


def test_cells_stay_on_their_row():
    text, _, warnings = format_ocr_blocks([
        block('492.5 PSI', 250, 51), block('Pressure', 10, 50),
        block('Reading', 250, 10), block('Parameter', 10, 10)])
    assert 'Parameter | Reading' in text
    assert 'Pressure | 492.5 PSI' in text
    assert warnings


def test_uncertainty_not_hidden_by_other_confident_blocks():
    text, _, warnings = format_ocr_blocks([block('492.5 PSI', 10, 10, confidence=0.4)])
    assert text == '492.5 PSI [OCR uncertain]'
    assert warnings


def test_missing_coordinates_and_empty_page():
    text, _, warnings = format_ocr_blocks([OCRTextBlock(text='Original order', confidence=0.99)])
    assert text == 'Original order' and warnings
    assert format_ocr_blocks([])[0] == ''
    assert format_ocr_blocks([])[2]


@pytest.mark.asyncio
async def test_real_ocr_ordered_inspection_sheet():
    image = Image.new('RGB', (1000, 600), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 30)
    for y, text in [(30, 'INSPECTION REPORT'), (130, 'Pump: P-101A'),
                    (190, 'Pressure: 492.5 PSI'), (250, 'Temperature: 92.1 C'),
                    (370, 'Recommendation: Inspect the seal.')]:
        draw.text((40, y), text, font=font, fill='black')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    result = await RapidOCREngine().extract(buffer.getvalue())
    assert result.text.index('INSPECTION') < result.text.index('Pressure') < result.text.index('Recommendation')
    assert '492.5' in result.text and '92.1' in result.text
    assert '\n\n' in result.text
    assert result.raw_text and result.blocks
