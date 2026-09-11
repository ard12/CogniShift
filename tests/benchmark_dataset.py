"""
Comprehensive Industrial Benchmark Corpus & Ground-Truth Dataset for CogniShift.
Generates 11 realistic multi-page industrial PDFs spanning all 14 evaluation categories:
A. Pure textual SOP retrieval
B. Narrative maintenance reports
C. Dense engineering tables
D. Multi-column tables
E. Scanned tables
F. Charts / trends
G. P&IDs
H. Engineering diagrams
I. Scanned inspection forms
J. Mixed page: paragraph + table + diagram
K. Equipment-tag lookup
L. Numeric-value lookup
M. Cross-document RCA questions
N. Negative queries with NO relevant evidence

Provides 80 deterministically defined queries split into:
- 48 Calibration (60%)
- 16 Validation (20%)
- 16 Holdout (20%)
"""
import math
import random
from pathlib import Path
from typing import List, Dict, Any, Tuple
import pymupdf


def generate_benchmark_corpus(output_dir: Path) -> List[Dict[str, Any]]:
    """Generates 11 realistic industrial PDFs in output_dir and returns catalog metadata."""
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_metadata = []

    # 1. SOP Document (Pure Text)
    f1 = output_dir / "SOP-TURB-001_Turbine_Start_Procedures.pdf"
    doc1 = pymupdf.open()
    p1 = doc1.new_page(width=595, height=842)
    p1.insert_text((50, 70), "REFINERY OPERATIONAL MANUAL — UNIT 100\nSTANDARD OPERATING PROCEDURE: SOP-TURB-001", fontsize=12)
    p1.insert_text((50, 110), 
        "Section 1: Pre-Start Permitting & Lube Oil Circulation\n\n"
        "1.1 Prior to initiating the gas turbine startup sequence, ensure Hot Work Permit PTW-7740 is active.\n"
        "1.2 Verify auxiliary lube oil pump P-102A is energized and header pressure exceeds 3.85 bar.\n"
        "1.3 Confirm lube oil reservoir temperature is maintained between 42°C and 48°C via electric immersion heater.\n"
        "1.4 Inspect hydraulic turning gear TG-101. Verify engagement speed is locked at 120 RPM for minimum 30 minutes.\n"
        "1.5 Safety Interlock I-101: If bearing vibration exceeds 2.8 mm/s RMS during turning, abort sequence immediately.\n",
        fontsize=10
    )
    p2 = doc1.new_page(width=595, height=842)
    p2.insert_text((50, 70), "STANDARD OPERATING PROCEDURE: SOP-TURB-001 (Page 2)", fontsize=12)
    p2.insert_text((50, 110),
        "Section 2: Fuel Gas Purge and Ignition Cycle\n\n"
        "2.1 Open stack damper D-101 to 100% position to establish natural draft purge for 10 minutes.\n"
        "2.2 Ensure fuel gas shutoff valve XV-105 is closed and double-block bleed valve XV-106 is open.\n"
        "2.3 Spark igniters IG-1A and IG-1B must be fired at 600 RPM. Flame detection UV-101 must confirm light-off within 8 seconds.\n"
        "2.4 If flame is not detected within 8.0 seconds, emergency trip solenoid SOV-102 will trip and post-purge starts for 15 minutes.\n"
        "2.5 Normal turbine acceleration rate is 150 RPM/min until reaching idle sync speed of 3000 RPM.\n",
        fontsize=10
    )
    doc1.save(str(f1))
    doc1.close()
    docs_metadata.append({"filename": f1.name, "path": f1, "pages": 2, "type": "SOP"})

    # 2. Narrative Maintenance Report
    f2 = output_dir / "MR-2026-COMP-04_Compressor_Overhaul_Narrative.pdf"
    doc2 = pymupdf.open()
    p2_1 = doc2.new_page(width=595, height=842)
    p2_1.insert_text((50, 70), "PLANT RELIABILITY & MAINTENANCE ENGINEERING REPORT\nWORK ORDER: WO-94102 — COMPRESSOR K-201 OVERHAUL", fontsize=12)
    p2_1.insert_text((50, 110),
        "Incident Summary & Teardown Observations:\n\n"
        "On August 14, 2026, centrifugal compressor K-201 experienced sudden thrust collar temperature spike to 118°C.\n"
        "Lead technician R. Miller commenced teardown inspection. Drive-end dry gas seal DE-DGS exhibited carbon face scoring.\n"
        "Root cause of seal failure traced to dirty seal gas supply filter F-201B which experienced high differential pressure DP > 1.4 bar.\n"
        "Active thrust bearing babbit pad #3 showed 40% thermal wiped surface due to lack of lube oil film thickness.\n",
        fontsize=10
    )
    p2_2 = doc2.new_page(width=595, height=842)
    p2_2.insert_text((50, 70), "WORK ORDER: WO-94102 — REASSEMBLY & CLEARANCE LOGS", fontsize=12)
    p2_2.insert_text((50, 110),
        "Reassembly Specs & Torque Records:\n\n"
        "Rotor float clearance was re-shimmed to nominal 0.38 mm (allowable tolerance: 0.35 mm - 0.42 mm).\n"
        "Coupling spacer bolts were torqued to 340 N*m using calibrated hydraulic wrench HW-12.\n"
        "Replaced seal cartridge with spare unit serial number S/N-DGS-8891-B.\n"
        "Pre-commissioning solo motor run completed successfully: vibration was 0.85 mm/s at 2980 RPM.\n",
        fontsize=10
    )
    doc2.save(str(f2))
    doc2.close()
    docs_metadata.append({"filename": f2.name, "path": f2, "pages": 2, "type": "Narrative"})

    # 3. Dense Engineering Table
    f3 = output_dir / "ENG-TBL-HEX-102_Heat_Exchanger_Tube_Inspection_Grid.pdf"
    doc3 = pymupdf.open()
    p3_1 = doc3.new_page(width=595, height=842)
    p3_1.insert_text((50, 70), "EQUIPMENT INTEGRITY DATA SHEET: HEAT EXCHANGER E-102\nTUBESHEET INSPECTION AND THICKNESS LOG", fontsize=12)
    p3_1.insert_text((50, 110), "Summary: Eddy current testing (ECT) conducted on 1,450 titanium tubes. Grid rows 1-8 listed below.\n", fontsize=10)
    y = 150
    headers = ["Row", "Tube ID", "Nom Thk (mm)", "Min Thk (mm)", "Wall Loss %", "Pit Depth (mm)", "ECT Defect Code", "Status"]
    p3_1.draw_rect(pymupdf.Rect(40, y-15, 550, y+10), color=(0.2, 0.4, 0.8), fill=(0.9, 0.95, 1.0))
    p3_1.insert_text((45, y), " | ".join(headers), fontsize=8)
    rows_data = [
        ("01", "T-0104", "1.65", "1.52", "7.8%", "0.13", "ID-PITTING", "ACCEPTABLE"),
        ("02", "T-0118", "1.65", "1.12", "32.1%", "0.53", "OD-EROSION", "MONITOR"),
        ("03", "T-0209", "1.65", "0.68", "58.7%", "0.97", "CRACK-TUBE", "PLUG_REQUIRED"),
        ("04", "T-0245", "1.65", "1.60", "3.0%", "0.05", "NONE", "PASS"),
        ("05", "T-0312", "1.65", "0.45", "72.7%", "1.20", "THINNING-CRIT", "PLUG_REQUIRED"),
        ("06", "T-0389", "1.65", "1.48", "10.3%", "0.17", "ID-CORROSION", "ACCEPTABLE"),
        ("07", "T-0415", "1.65", "1.55", "6.0%", "0.10", "NONE", "PASS"),
        ("08", "T-0490", "1.65", "0.58", "64.8%", "1.07", "CIRC-CRACK", "PLUG_REQUIRED"),
    ]
    for idx, r in enumerate(rows_data):
        y += 25
        p3_1.insert_text((45, y), f"{r[0]:<4} | {r[1]:<7} | {r[2]:<12} | {r[3]:<12} | {r[4]:<11} | {r[5]:<14} | {r[6]:<15} | {r[7]}", fontsize=8)
        p3_1.draw_line((40, y+5), (550, y+5), color=(0.8, 0.8, 0.8))
    p3_2 = doc3.new_page(width=595, height=842)
    p3_2.insert_text((50, 70), "HEAT EXCHANGER E-102 — TUBE RETIREMENT & PLUGGING SPEC", fontsize=12)
    p3_2.insert_text((50, 110),
        "Plugging Rule ASME Section VIII Div 1:\n"
        "- Any tube exhibiting wall loss > 50% must be plugged using tapered brass or titanium plug P-TUBE-TITAN-16.\n"
        "- Total allowable plugged tubes in bundle E-102 is 145 tubes (10.0% of total bundle capacity).\n"
        "- Current campaign total plugged tubes count: 18 tubes plugged as of 2026 turnaround.\n",
        fontsize=10
    )
    doc3.save(str(f3))
    doc3.close()
    docs_metadata.append({"filename": f3.name, "path": f3, "pages": 2, "type": "Dense Table"})

    # 4. Multi-Column Specifications
    f4 = output_dir / "SPEC-PUMP-401_Centrifugal_Feed_Pumps_MultiColumn_Specs.pdf"
    doc4 = pymupdf.open()
    p4 = doc4.new_page(width=595, height=842)
    p4.insert_text((50, 70), "API 610 CENTRIFUGAL PUMP DATASHEET — P-401A/B/C", fontsize=12)
    col1_x, col2_x, col3_x = 50, 220, 390
    p4.insert_text((col1_x, 110), "OPERATING CONDITIONS:\n\nFluid: Naphtha / Condensate\nSG @ PT: 0.742\nPumping Temp: 65°C\nSuction Pressure: 2.1 bar\nDischarge Pressure: 18.5 bar\nDifferential Head: 224 m\nRated Capacity: 185 m3/h\nNPSH Available: 4.8 m\nNPSH Required: 3.2 m", fontsize=9)
    p4.insert_text((col2_x, 110), "HYDRAULIC DESIGN:\n\nPump Type: BB2 Double Suction\nImpeller Diameter: 320 mm\nNumber of Stages: 2\nBest Efficiency (BEP): 78.4%\nMinimum Flow: 45 m3/h\nShutoff Head: 268 m\nCasing Design: Carbon Steel A216 WCB\nWear Ring Clearance: 0.28 mm\nMechanical Seal: Plan 53A Dual", fontsize=9)
    p4.insert_text((col3_x, 110), "ELECTRIC MOTOR DRIVE:\n\nMotor Tag: M-401A\nRating: 160 kW\nVoltage: 415 V 3-Phase\nFull Load Current: 265 A\nSynchronous Speed: 3000 RPM\nFull Load Speed: 2975 RPM\nInsulation Class: Class F / B Rise\nEnclosure: Ex d IIC T4 Gb\nBearing Type: DE 6314 / NDE 6314", fontsize=9)
    doc4.save(str(f4))
    doc4.close()
    docs_metadata.append({"filename": f4.name, "path": f4, "pages": 1, "type": "Multi-Column"})

    # 5. Scanned-style Log with Stamps & Noise
    f5 = output_dir / "SCAN-LOG-BOILER-2025_Boiler_Drum_Daily_Logs.pdf"
    doc5 = pymupdf.open()
    p5 = doc5.new_page(width=595, height=842)
    p5.insert_text((60, 80), "BOILER UTILITY UNIT 5 — SHIFT HANDOVER LOG SHEET [SCANNED ARCHIVE]", fontsize=11)
    p5.draw_rect(pymupdf.Rect(50, 110, 540, 450), color=(0.4, 0.4, 0.4), width=1.5)
    p5.insert_text((65, 140), "Shift: Night (22:00 - 06:00) | Date: 11-Nov-2025 | Boiler: B-501 High Pressure Steam Drum", fontsize=9)
    p5.insert_text((65, 180), "Hourly Drum Level Records:\n- 23:00 Level: +12 mm WC, Steam Flow: 82 TPH, Feedwater Flow: 83 TPH\n- 01:00 Level: -05 mm WC, Steam Flow: 84 TPH, Feedwater Flow: 84 TPH\n- 03:00 Level: -18 mm WC (Operator manually adjusted blowdown valve BD-501)\n- 05:00 Level: +02 mm WC, TDS: 1450 ppm, Phosphate: 8.2 ppm", fontsize=9)
    p5.draw_rect(pymupdf.Rect(350, 320, 510, 400), color=(0.8, 0.1, 0.1), width=2.0)
    p5.insert_text((360, 345), "[CHIEF OPERATOR STAMP]\nVERIFIED & SIGNED\nOPERATOR: H. SHARMA\nBADGE: CS-99412", fontsize=9, color=(0.8, 0.1, 0.1))
    doc5.save(str(f5))
    doc5.close()
    docs_metadata.append({"filename": f5.name, "path": f5, "pages": 1, "type": "Scanned Log"})

    # 6. Performance Curves & Charts
    f6 = output_dir / "CURVE-COMP-K201_Performance_Curves_and_Surge_Envelope.pdf"
    doc6 = pymupdf.open()
    p6 = doc6.new_page(width=595, height=842)
    p6.insert_text((50, 70), "COMPRESSOR K-201: AERODYNAMIC PERFORMANCE & SURGE MAP", fontsize=12)
    origin = (80, 450)
    p6.draw_line(origin, (520, 450), color=(0, 0, 0), width=1.5)
    p6.draw_line(origin, (80, 150), color=(0, 0, 0), width=1.5)
    p6.insert_text((250, 475), "Inlet Volumetric Flow Q (m3/min)", fontsize=9)
    p6.insert_text((20, 280), "Pressure Ratio", fontsize=9, rotate=90)
    p6.draw_line((120, 200), (220, 420), color=(0.9, 0.1, 0.1), width=2.5)
    p6.insert_text((130, 220), "Surge Line (Trip Zone)", color=(0.9, 0.1, 0.1), fontsize=8)
    p6.draw_bezier((150, 240), (280, 260), (400, 320), (480, 410), color=(0.1, 0.5, 0.9), width=2.0)
    p6.insert_text((420, 310), "105% Speed (10,500 RPM)", color=(0.1, 0.5, 0.9), fontsize=8)
    p6.draw_bezier((140, 280), (260, 300), (380, 360), (450, 430), color=(0.1, 0.7, 0.3), width=2.0)
    p6.insert_text((390, 350), "100% Rated Speed (10,000 RPM)", color=(0.1, 0.7, 0.3), fontsize=8)
    p6.insert_text((50, 520),
        "Key Aerodynamic Boundaries:\n"
        "- Minimum surge margin threshold: 12.5% flow distance from surge control line.\n"
        "- Maximum continuous operating speed: 10,800 RPM (Trip setpoint: 11,200 RPM).\n"
        "- Rated design point: 340 m3/min at 3.65 pressure ratio, requiring 4,250 kW shaft power.\n",
        fontsize=9
    )
    doc6.save(str(f6))
    doc6.close()
    docs_metadata.append({"filename": f6.name, "path": f6, "pages": 1, "type": "Chart/Trend"})

    # 7. P&ID Blueprint
    f7 = output_dir / "PID-REACT-301_Hydrocracker_Reactor_Feed_Instrumentation.pdf"
    doc7 = pymupdf.open()
    p7 = doc7.new_page(width=842, height=595)
    p7.insert_text((50, 50), "PIPING & INSTRUMENTATION DIAGRAM — HYDROCRACKER UNIT 300\nDRAWING NUMBER: PID-R-301-REV-04", fontsize=12)
    p7.draw_rect(pymupdf.Rect(450, 120, 600, 450), color=(0, 0, 0), width=2.0)
    p7.insert_text((480, 150), "REACTOR\nR-301", fontsize=14)
    p7.draw_line((80, 280), (450, 280), color=(0.1, 0.3, 0.7), width=3.0)
    p7.insert_text((100, 270), "Line 12\"-HC-3001-A1A (Heavy Gas Oil Feed)", fontsize=9)
    p7.draw_circle((180, 280), 22, color=(0, 0, 0), fill=(1, 1, 1), width=1.5)
    p7.insert_text((168, 283), "FT-302", fontsize=7)
    p7.draw_rect(pymupdf.Rect(260, 265, 300, 295), color=(0, 0, 0), fill=(0.9, 0.9, 0.9), width=1.5)
    p7.insert_text((265, 282), "FV-302", fontsize=7)
    p7.draw_circle((525, 80), 22, color=(0, 0, 0), fill=(1, 1, 1), width=1.5)
    p7.draw_line((525, 102), (525, 120), color=(0, 0, 0), width=1.5)
    p7.insert_text((513, 83), "PT-301", fontsize=7)
    p7.draw_circle((575, 80), 22, color=(0.8, 0.1, 0.1), fill=(1, 1, 1), width=1.5)
    p7.draw_line((575, 102), (575, 120), color=(0, 0, 0), width=1.5)
    p7.insert_text((560, 83), "PSV-301", fontsize=6, color=(0.8, 0.1, 0.1))
    p7.insert_text((50, 480),
        "P&ID Notes & Interlocks:\n"
        "1. High pressure trip interlock I-301 trips FV-302 closed when PT-301 > 142.5 bar.\n"
        "2. PSV-301 setpoint: 155.0 bar, venting directly to flare header FL-101.\n"
        "3. Hydrogen quench valve HV-305 injects between bed 1 and bed 2 on high DT > 18°C.\n",
        fontsize=8
    )
    doc7.save(str(f7))
    doc7.close()
    docs_metadata.append({"filename": f7.name, "path": f7, "pages": 1, "type": "P&ID"})

    # 8. Mechanical Assembly Cross Section Diagram
    f8 = output_dir / "DWG-MECH-SEAL-88_Mechanical_Seal_Assembly_CrossSection.pdf"
    doc8 = pymupdf.open()
    p8 = doc8.new_page(width=595, height=842)
    p8.insert_text((50, 70), "MECHANICAL SEAL CARTRIDGE ASSEMBLY: DRAWING DWG-SEAL-88", fontsize=12)
    p8.draw_rect(pymupdf.Rect(100, 150, 480, 400), color=(0.2, 0.2, 0.2), width=1.5)
    p8.insert_text((120, 180), "[SCHEMATIC SECTION VIEW: DUAL CARTRIDGE SEAL TYPE B]", fontsize=9)
    parts = [
        (150, 220, "Item 1: Stationary Silicon Carbide Seat (Part #SiC-8801)"),
        (150, 260, "Item 2: Rotating Carbon Face Ring (Part #C-8802)"),
        (150, 300, "Item 3: Hastelloy C-276 Multi-Springs (Part #SPG-8803)"),
        (150, 340, "Item 4: Kalrez 6375 Perfluoroelastomer O-Ring (Part #OR-KLZ-42)"),
        (150, 380, "Item 5: Barrier Fluid Port Flush 3/8\" NPT (Barrier Plan 53B)"),
    ]
    for px, py, text in parts:
        p8.draw_circle((px-20, py-5), 4, color=(0.1, 0.4, 0.8), fill=(0.1, 0.4, 0.8))
        p8.draw_line((px-20, py-5), (px-5, py-5), color=(0.1, 0.4, 0.8))
        p8.insert_text((px, py), text, fontsize=9)
    p8.insert_text((50, 600),
        "Assembly Specification:\n"
        "- Spring working compression: 4.5 mm +/- 0.2 mm.\n"
        "- Gland bolt torque: 55 N*m in star pattern.\n"
        "- Maximum allowable shaft runout at seal sleeve: 0.025 mm TIR.\n",
        fontsize=9
    )
    doc8.save(str(f8))
    doc8.close()
    docs_metadata.append({"filename": f8.name, "path": f8, "pages": 1, "type": "Diagram"})

    # 9. Scanned ASME Inspection Form
    f9 = output_dir / "SCAN-FORM-ASME-2026_Pressure_Vessel_Thickness_Checklist.pdf"
    doc9 = pymupdf.open()
    p9 = doc9.new_page(width=595, height=842)
    p9.insert_text((50, 70), "ASME SECTION VIII VESSEL PERIODIC ULTRASONIC INSPECTION REPORT", fontsize=11)
    p9.draw_rect(pymupdf.Rect(40, 100, 550, 600), color=(0.3, 0.3, 0.3), width=1.0)
    p9.insert_text((50, 130), "Vessel Tag: V-201 Stripper Column | National Board # NB-449102 | Design Pressure: 25.0 bar", fontsize=9)
    checks = [
        ("Top Head Shell Thickness", "Nom: 18.0 mm", "Actual: 17.4 mm", "[X] COMPLIANT"),
        ("Middle Shell Course #2", "Nom: 22.0 mm", "Actual: 19.8 mm", "[X] COMPLIANT (Corrosion Allow: 3.0 mm)"),
        ("Bottom Sump Cone", "Nom: 24.0 mm", "Actual: 20.2 mm", "[!] RE-INSPECTION 6-MO (Remaining CA: 0.2 mm)"),
        ("Nozzle N1 Inlet 10\"", "Nom: 12.5 mm", "Actual: 12.1 mm", "[X] COMPLIANT"),
        ("Nozzle N4 Reboiler Return", "Nom: 14.0 mm", "Actual: 11.2 mm", "[!] EROSION OBSERVED AT WELD SEAM"),
    ]
    cy = 170
    for title, nom, act, stat in checks:
        p9.insert_text((50, cy), f"- {title:<25} | {nom:<14} | {act:<14} | {stat}", fontsize=8)
        p9.draw_line((40, cy+5), (550, cy+5), color=(0.85, 0.85, 0.85))
        cy += 35
    p9.insert_text((50, 520),
        "NDT Inspector Certification:\n"
        "Certified ASNT Level II Ultrasonic Inspector: K. Patel (Cert # UT-88319)\n"
        "Calibration block step wedge ASTM E797 SN-7740 used for zero calibration.\n",
        fontsize=8
    )
    doc9.save(str(f9))
    doc9.close()
    docs_metadata.append({"filename": f9.name, "path": f9, "pages": 1, "type": "Scanned Form"})

    # 10. Mixed Layout Page
    f10 = output_dir / "MIXED-UNIT-500_Distillation_Tower_Reflux_Drum_Summary.pdf"
    doc10 = pymupdf.open()
    p10 = doc10.new_page(width=595, height=842)
    p10.insert_text((50, 60), "DISTILLATION UNIT 500 — REFLUX ACCUMULATOR DRUM D-501", fontsize=12)
    p10.insert_text((50, 90),
        "The overhead vapor from debutanizer tower T-501 condenses in air-fin cooler E-501 and collects\n"
        "in reflux drum D-501. Hydrocarbon liquid is pumped via reflux pumps P-501A/B back to Tray 1\n"
        "with excess product sent to LPG storage spheroids TK-901.\n",
        fontsize=9
    )
    p10.draw_rect(pymupdf.Rect(45, 145, 545, 235), color=(0.2, 0.4, 0.7), fill=(0.95, 0.97, 1.0))
    p10.insert_text((55, 165), "Reflux Pump P-501 Operating Setpoints Table:", fontsize=9)
    p10.insert_text((55, 185), "Parameter               | Normal Value | High Alarm | High-High Trip", fontsize=8)
    p10.insert_text((55, 205), "Liquid Level (LT-501)   | 55% span     | 75% span   | 88% span (Trip P-501)", fontsize=8)
    p10.insert_text((55, 225), "Discharge Press (PT-505)| 14.2 bar     | 16.5 bar   | 18.0 bar", fontsize=8)
    p10.draw_rect(pymupdf.Rect(45, 260, 545, 480), color=(0.4, 0.4, 0.4))
    p10.insert_text((55, 280), "[NOZZLE ORIENTATION SCHEMATIC: DRUM D-501]", fontsize=9)
    p10.draw_rect(pymupdf.Rect(180, 310, 380, 420), color=(0, 0, 0), width=1.5)
    p10.insert_text((220, 360), "VESSEL D-501\n(Horizontal Drum)", fontsize=10)
    p10.insert_text((65, 330), "Nozzle N1 (Inlet 8\" 300#) ──▶", fontsize=8)
    p10.insert_text((390, 330), "◀── Nozzle N2 (Vapor Off-gas 4\")", fontsize=8)
    p10.insert_text((65, 400), "Nozzle N3 (Boot Water Drain 2\") ──▶", fontsize=8)
    p10.insert_text((390, 400), "◀── Nozzle N4 (Pump Suction 6\")", fontsize=8)
    doc10.save(str(f10))
    doc10.close()
    docs_metadata.append({"filename": f10.name, "path": f10, "pages": 1, "type": "Mixed Layout"})

    # 11. RCA Cross-Document Incident Investigation
    f11 = output_dir / "RCA-INCIDENT-2026-08_Hydrocracker_Trip_Incident_Investigation.pdf"
    doc11 = pymupdf.open()
    p11_1 = doc11.new_page(width=595, height=842)
    p11_1.insert_text((50, 70), "ROOT CAUSE ANALYSIS REPORT: RCA-2026-08\nSUBJECT: HYDROCRACKER REACTOR R-301 EMERGENCY DEPRESSURING", fontsize=12)
    p11_1.insert_text((50, 110),
        "1. Chronology of Events:\n"
        "- 03:14 AM: Feed valve FV-302 spurious closure triggered by faulty wire terminal in junction box JB-102.\n"
        "- 03:15 AM: Loss of cold feed caused rapid thermal runaway; Bed 1 delta-T jumped to 24.5°C.\n"
        "- 03:16 AM: Emergency quench valve HV-305 failed to open due to seized actuator solenoid SOV-305.\n"
        "- 03:17 AM: High pressure trip interlock I-301 activated at 143.8 bar, opening depressuring valve BDV-301 to flare.\n",
        fontsize=9
    )
    p11_2 = doc11.new_page(width=595, height=842)
    p11_2.insert_text((50, 70), "RCA-2026-08: ROOT CAUSE FINDINGS & INTER-DOCUMENT MAPPING", fontsize=12)
    p11_2.insert_text((50, 110),
        "2. Contributing Factors Cross-Referenced to Plant Baselines:\n"
        "- As documented in PID-REACT-301, interlock I-301 took automatic action per design; however,\n"
        "  quench bypass line was not inspected during WO-94102 turnaround as required by SOP-TURB-001.\n"
        "- Inspection log SCAN-LOG-BOILER-2025 indicated utility steam fluctuation 15 minutes before trip,\n"
        "  destabilizing the feed preheat furnace temperature control loop.\n"
        "Corrective Action CAPA-881: Replace solenoid SOV-305 with fail-safe de-energize-to-trip model.\n",
        fontsize=9
    )
    doc11.save(str(f11))
    doc11.close()
    docs_metadata.append({"filename": f11.name, "path": f11, "pages": 2, "type": "RCA Case"})

    return docs_metadata


def get_ground_truth_benchmark_queries() -> List[Dict[str, Any]]:
    """Returns 80 deterministically curated evaluation queries spanning 14 industrial categories."""
    return [
        # --- Category A: Pure Textual SOP Retrieval (6 queries) ---
        {"id": "Q01", "category": "SOP", "query": "What is the minimum header pressure for lube oil pump P-102A before turbine startup?",
         "expected_filename": "SOP-TURB-001_Turbine_Start_Procedures.pdf", "expected_page": 1, "evidence_type": "text", "expected_keywords": ["P-102A", "3.85 bar"]},
        {"id": "Q02", "category": "SOP", "query": "What speed must turning gear TG-101 be locked at and for how long?",
         "expected_filename": "SOP-TURB-001_Turbine_Start_Procedures.pdf", "expected_page": 1, "evidence_type": "text", "expected_keywords": ["120 RPM", "30 minutes"]},
        {"id": "Q03", "category": "SOP", "query": "What is the vibration trip limit during turning gear operation in SOP-TURB-001?",
         "expected_filename": "SOP-TURB-001_Turbine_Start_Procedures.pdf", "expected_page": 1, "evidence_type": "text", "expected_keywords": ["2.8 mm/s", "I-101"]},
        {"id": "Q04", "category": "SOP", "query": "How long must stack damper D-101 be opened for natural draft purge?",
         "expected_filename": "SOP-TURB-001_Turbine_Start_Procedures.pdf", "expected_page": 2, "evidence_type": "text", "expected_keywords": ["10 minutes", "damper D-101"]},
        {"id": "Q05", "category": "SOP", "query": "Within how many seconds must flame detector UV-101 confirm light-off?",
         "expected_filename": "SOP-TURB-001_Turbine_Start_Procedures.pdf", "expected_page": 2, "evidence_type": "text", "expected_keywords": ["8.0 seconds", "UV-101"]},
        {"id": "Q06", "category": "SOP", "query": "What is the normal turbine acceleration rate up to 3000 RPM?",
         "expected_filename": "SOP-TURB-001_Turbine_Start_Procedures.pdf", "expected_page": 2, "evidence_type": "text", "expected_keywords": ["150 RPM/min", "3000 RPM"]},

        # --- Category B: Narrative Maintenance Reports (6 queries) ---
        {"id": "Q07", "category": "Narrative", "query": "Why did compressor K-201 experience a sudden thrust collar temperature spike on August 14?",
         "expected_filename": "MR-2026-COMP-04_Compressor_Overhaul_Narrative.pdf", "expected_page": 1, "evidence_type": "text", "expected_keywords": ["K-201", "118°C", "seal gas"]},
        {"id": "Q08", "category": "Narrative", "query": "What differential pressure was observed across seal gas supply filter F-201B?",
         "expected_filename": "MR-2026-COMP-04_Compressor_Overhaul_Narrative.pdf", "expected_page": 1, "evidence_type": "text", "expected_keywords": ["F-201B", "1.4 bar"]},
        {"id": "Q09", "category": "Narrative", "query": "What percentage of thrust bearing pad babbit was wiped during the K-201 teardown?",
         "expected_filename": "MR-2026-COMP-04_Compressor_Overhaul_Narrative.pdf", "expected_page": 1, "evidence_type": "text", "expected_keywords": ["40%", "pad #3"]},
        {"id": "Q10", "category": "Narrative", "query": "What was the re-shimmed rotor float clearance for compressor K-201?",
         "expected_filename": "MR-2026-COMP-04_Compressor_Overhaul_Narrative.pdf", "expected_page": 2, "evidence_type": "text", "expected_keywords": ["0.38 mm", "float clearance"]},
        {"id": "Q11", "category": "Narrative", "query": "What torque was applied to coupling spacer bolts during K-201 reassembly?",
         "expected_filename": "MR-2026-COMP-04_Compressor_Overhaul_Narrative.pdf", "expected_page": 2, "evidence_type": "text", "expected_keywords": ["340 N*m", "HW-12"]},
        {"id": "Q12", "category": "Narrative", "query": "What was the serial number of the replacement dry gas seal cartridge installed on K-201?",
         "expected_filename": "MR-2026-COMP-04_Compressor_Overhaul_Narrative.pdf", "expected_page": 2, "evidence_type": "text", "expected_keywords": ["S/N-DGS-8891-B"]},

        # --- Category C: Dense Engineering Tables (6 queries) ---
        {"id": "Q13", "category": "Dense Table", "query": "In the E-102 tubesheet inspection table, what is the wall loss percentage for tube T-0209?",
         "expected_filename": "ENG-TBL-HEX-102_Heat_Exchanger_Tube_Inspection_Grid.pdf", "expected_page": 1, "evidence_type": "table", "expected_keywords": ["T-0209", "58.7%"]},
        {"id": "Q14", "category": "Dense Table", "query": "What ECT defect code is recorded for tube T-0312 in heat exchanger E-102?",
         "expected_filename": "ENG-TBL-HEX-102_Heat_Exchanger_Tube_Inspection_Grid.pdf", "expected_page": 1, "evidence_type": "table", "expected_keywords": ["T-0312", "THINNING-CRIT"]},
        {"id": "Q15", "category": "Dense Table", "query": "Look at the inspection grid for E-102: which tube has a minimum thickness of 0.58 mm?",
         "expected_filename": "ENG-TBL-HEX-102_Heat_Exchanger_Tube_Inspection_Grid.pdf", "expected_page": 1, "evidence_type": "table", "expected_keywords": ["T-0490", "0.58"]},
        {"id": "Q16", "category": "Dense Table", "query": "What is the measured pit depth for tube T-0118 in exchanger E-102?",
         "expected_filename": "ENG-TBL-HEX-102_Heat_Exchanger_Tube_Inspection_Grid.pdf", "expected_page": 1, "evidence_type": "table", "expected_keywords": ["T-0118", "0.53"]},
        {"id": "Q17", "category": "Dense Table", "query": "What is the allowable plugged tube limit percentage for heat exchanger bundle E-102?",
         "expected_filename": "ENG-TBL-HEX-102_Heat_Exchanger_Tube_Inspection_Grid.pdf", "expected_page": 2, "evidence_type": "table", "expected_keywords": ["10.0%", "145 tubes"]},
        {"id": "Q18", "category": "Dense Table", "query": "What part number plug is specified for plugging tubes exceeding 50% wall loss in E-102?",
         "expected_filename": "ENG-TBL-HEX-102_Heat_Exchanger_Tube_Inspection_Grid.pdf", "expected_page": 2, "evidence_type": "table", "expected_keywords": ["P-TUBE-TITAN-16"]},

        # --- Category D: Multi-Column Specifications (6 queries) ---
        {"id": "Q19", "category": "Multi-Column", "query": "What is the rated capacity and differential head for pump P-401?",
         "expected_filename": "SPEC-PUMP-401_Centrifugal_Feed_Pumps_MultiColumn_Specs.pdf", "expected_page": 1, "evidence_type": "table", "expected_keywords": ["185 m3/h", "224 m"]},
        {"id": "Q20", "category": "Multi-Column", "query": "What is the NPSH required (NPSHr) value for feed pump P-401?",
         "expected_filename": "SPEC-PUMP-401_Centrifugal_Feed_Pumps_MultiColumn_Specs.pdf", "expected_page": 1, "evidence_type": "table", "expected_keywords": ["3.2 m", "NPSH Required"]},
        {"id": "Q21", "category": "Multi-Column", "query": "What impeller diameter is installed on pump P-401 in the hydraulic column?",
         "expected_filename": "SPEC-PUMP-401_Centrifugal_Feed_Pumps_MultiColumn_Specs.pdf", "expected_page": 1, "evidence_type": "table", "expected_keywords": ["320 mm", "Impeller Diameter"]},
        {"id": "Q22", "category": "Multi-Column", "query": "What is the API mechanical seal flush plan specified for P-401?",
         "expected_filename": "SPEC-PUMP-401_Centrifugal_Feed_Pumps_MultiColumn_Specs.pdf", "expected_page": 1, "evidence_type": "table", "expected_keywords": ["Plan 53A", "Dual"]},
        {"id": "Q23", "category": "Multi-Column", "query": "What is the electric motor drive power rating and full load current for M-401A?",
         "expected_filename": "SPEC-PUMP-401_Centrifugal_Feed_Pumps_MultiColumn_Specs.pdf", "expected_page": 1, "evidence_type": "table", "expected_keywords": ["160 kW", "265 A"]},
        {"id": "Q24", "category": "Multi-Column", "query": "What bearing models are used on drive-end and non-drive-end of motor M-401A?",
         "expected_filename": "SPEC-PUMP-401_Centrifugal_Feed_Pumps_MultiColumn_Specs.pdf", "expected_page": 1, "evidence_type": "table", "expected_keywords": ["DE 6314", "NDE 6314"]},

        # --- Category E: Scanned Tables & Logs (6 queries) ---
        {"id": "Q25", "category": "Scanned Table", "query": "In the scanned boiler shift log for B-501, what was the drum level at 03:00?",
         "expected_filename": "SCAN-LOG-BOILER-2025_Boiler_Drum_Daily_Logs.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["-18 mm WC", "BD-501"]},
        {"id": "Q26", "category": "Scanned Table", "query": "What was the phosphate concentration recorded at 05:00 on boiler B-501?",
         "expected_filename": "SCAN-LOG-BOILER-2025_Boiler_Drum_Daily_Logs.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["8.2 ppm", "Phosphate"]},
        {"id": "Q27", "category": "Scanned Table", "query": "What total dissolved solids (TDS) reading was logged at 05:00 on boiler B-501?",
         "expected_filename": "SCAN-LOG-BOILER-2025_Boiler_Drum_Daily_Logs.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["1450 ppm", "TDS"]},
        {"id": "Q28", "category": "Scanned Table", "query": "Who signed the chief operator verification stamp on the boiler shift sheet?",
         "expected_filename": "SCAN-LOG-BOILER-2025_Boiler_Drum_Daily_Logs.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["H. SHARMA", "CS-99412"]},
        {"id": "Q29", "category": "Scanned Table", "query": "What was the steam flow rate in TPH at 23:00 on boiler drum B-501?",
         "expected_filename": "SCAN-LOG-BOILER-2025_Boiler_Drum_Daily_Logs.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["82 TPH", "23:00"]},
        {"id": "Q30", "category": "Scanned Table", "query": "Which blowdown valve was manually adjusted at 03:00 according to the scanned sheet?",
         "expected_filename": "SCAN-LOG-BOILER-2025_Boiler_Drum_Daily_Logs.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["BD-501", "blowdown"]},

        # --- Category F: Charts & Curves (6 queries) ---
        {"id": "Q31", "category": "Chart/Trend", "query": "On the aerodynamic performance map for K-201, what is the minimum surge margin threshold?",
         "expected_filename": "CURVE-COMP-K201_Performance_Curves_and_Surge_Envelope.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["12.5%", "surge margin"]},
        {"id": "Q32", "category": "Chart/Trend", "query": "What is the maximum continuous operating speed and trip setpoint on the K-201 curve?",
         "expected_filename": "CURVE-COMP-K201_Performance_Curves_and_Surge_Envelope.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["10,800 RPM", "11,200 RPM"]},
        {"id": "Q33", "category": "Chart/Trend", "query": "What is the rated design inlet volumetric flow and pressure ratio on the K-201 map?",
         "expected_filename": "CURVE-COMP-K201_Performance_Curves_and_Surge_Envelope.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["340 m3/min", "3.65"]},
        {"id": "Q34", "category": "Chart/Trend", "query": "Look at the K-201 surge curve diagram: what color represents the 105% speed line?",
         "expected_filename": "CURVE-COMP-K201_Performance_Curves_and_Surge_Envelope.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["10,500 RPM", "105% Speed"]},
        {"id": "Q35", "category": "Chart/Trend", "query": "What shaft power in kW is required at the rated design point for compressor K-201?",
         "expected_filename": "CURVE-COMP-K201_Performance_Curves_and_Surge_Envelope.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["4,250 kW", "shaft power"]},
        {"id": "Q36", "category": "Chart/Trend", "query": "What red curve marks the trip boundary on the K-201 aerodynamic chart?",
         "expected_filename": "CURVE-COMP-K201_Performance_Curves_and_Surge_Envelope.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["Surge Line", "Trip Zone"]},

        # --- Category G: P&IDs (6 queries) ---
        {"id": "Q37", "category": "P&ID", "query": "On P&ID drawing PID-R-301, what flow transmitter is on the reactor feed line?",
         "expected_filename": "PID-REACT-301_Hydrocracker_Reactor_Feed_Instrumentation.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["FT-302", "feed line"]},
        {"id": "Q38", "category": "P&ID", "query": "What is the line number and size for the heavy gas oil feed into reactor R-301 on the P&ID?",
         "expected_filename": "PID-REACT-301_Hydrocracker_Reactor_Feed_Instrumentation.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["12-inch-HC-3001-A1A"]},
        {"id": "Q39", "category": "P&ID", "query": "What pressure transmitter tag is mounted on top of reactor vessel R-301 on the blueprint?",
         "expected_filename": "PID-REACT-301_Hydrocracker_Reactor_Feed_Instrumentation.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["PT-301", "R-301"]},
        {"id": "Q40", "category": "P&ID", "query": "What is the relief valve tag and setpoint on the top head of reactor R-301?",
         "expected_filename": "PID-REACT-301_Hydrocracker_Reactor_Feed_Instrumentation.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["PSV-301", "155.0 bar"]},
        {"id": "Q41", "category": "P&ID", "query": "What trip pressure setpoint on PT-301 causes interlock I-301 to trip valve FV-302?",
         "expected_filename": "PID-REACT-301_Hydrocracker_Reactor_Feed_Instrumentation.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["142.5 bar", "I-301", "FV-302"]},
        {"id": "Q42", "category": "P&ID", "query": "Which hydrogen quench valve injects between bed 1 and bed 2 on high temperature difference?",
         "expected_filename": "PID-REACT-301_Hydrocracker_Reactor_Feed_Instrumentation.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["HV-305", "quench valve"]},

        # --- Category H: Engineering Diagrams (6 queries) ---
        {"id": "Q43", "category": "Diagram", "query": "In mechanical seal assembly DWG-SEAL-88, what part number is the stationary silicon carbide seat?",
         "expected_filename": "DWG-MECH-SEAL-88_Mechanical_Seal_Assembly_CrossSection.pdf", "expected_page": 1, "evidence_type": "diagram", "expected_keywords": ["SiC-8801", "Item 1"]},
        {"id": "Q44", "category": "Diagram", "query": "What elastomer material and part number is specified for O-ring Item 4 on DWG-SEAL-88?",
         "expected_filename": "DWG-MECH-SEAL-88_Mechanical_Seal_Assembly_CrossSection.pdf", "expected_page": 1, "evidence_type": "diagram", "expected_keywords": ["Kalrez 6375", "OR-KLZ-42"]},
        {"id": "Q45", "category": "Diagram", "query": "What spring material is used for Item 3 on the mechanical seal drawing?",
         "expected_filename": "DWG-MECH-SEAL-88_Mechanical_Seal_Assembly_CrossSection.pdf", "expected_page": 1, "evidence_type": "diagram", "expected_keywords": ["Hastelloy C-276", "SPG-8803"]},
        {"id": "Q46", "category": "Diagram", "query": "What barrier fluid flush plan and port size is indicated for Item 5 on the seal diagram?",
         "expected_filename": "DWG-MECH-SEAL-88_Mechanical_Seal_Assembly_CrossSection.pdf", "expected_page": 1, "evidence_type": "diagram", "expected_keywords": ["Plan 53B", "3/8-inch NPT"]},
        {"id": "Q47", "category": "Diagram", "query": "What is the required gland bolt torque in star pattern on assembly drawing DWG-SEAL-88?",
         "expected_filename": "DWG-MECH-SEAL-88_Mechanical_Seal_Assembly_CrossSection.pdf", "expected_page": 1, "evidence_type": "diagram", "expected_keywords": ["55 N*m", "star pattern"]},
        {"id": "Q48", "category": "Diagram", "query": "What is the maximum allowable shaft runout at the seal sleeve in DWG-SEAL-88?",
         "expected_filename": "DWG-MECH-SEAL-88_Mechanical_Seal_Assembly_CrossSection.pdf", "expected_page": 1, "evidence_type": "diagram", "expected_keywords": ["0.025 mm", "runout"]},

        # --- Category I: Scanned Inspection Forms (6 queries) ---
        {"id": "Q49", "category": "Scanned Form", "query": "On the scanned ASME inspection report for vessel V-201, what is the actual measured thickness of the bottom sump cone?",
         "expected_filename": "SCAN-FORM-ASME-2026_Pressure_Vessel_Thickness_Checklist.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["20.2 mm", "Bottom Sump Cone"]},
        {"id": "Q50", "category": "Scanned Form", "query": "What observation was noted for nozzle N4 reboiler return on vessel V-201?",
         "expected_filename": "SCAN-FORM-ASME-2026_Pressure_Vessel_Thickness_Checklist.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["EROSION OBSERVED", "11.2 mm"]},
        {"id": "Q51", "category": "Scanned Form", "query": "What is the National Board number recorded on the V-201 vessel inspection form?",
         "expected_filename": "SCAN-FORM-ASME-2026_Pressure_Vessel_Thickness_Checklist.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["NB-449102", "V-201"]},
        {"id": "Q52", "category": "Scanned Form", "query": "What remaining corrosion allowance is left on the bottom sump cone of stripper column V-201?",
         "expected_filename": "SCAN-FORM-ASME-2026_Pressure_Vessel_Thickness_Checklist.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["0.2 mm", "Remaining CA"]},
        {"id": "Q53", "category": "Scanned Form", "query": "Who is the certified ASNT Level II ultrasonic inspector named on the V-201 form?",
         "expected_filename": "SCAN-FORM-ASME-2026_Pressure_Vessel_Thickness_Checklist.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["K. Patel", "UT-88319"]},
        {"id": "Q54", "category": "Scanned Form", "query": "What calibration block standard was used for zero calibration on the ASME vessel checklist?",
         "expected_filename": "SCAN-FORM-ASME-2026_Pressure_Vessel_Thickness_Checklist.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["ASTM E797", "SN-7740"]},

        # --- Category J: Mixed Layout (6 queries) ---
        {"id": "Q55", "category": "Mixed Layout", "query": "On the debutanizer drum D-501 sheet, where is excess liquid pumped after reflux?",
         "expected_filename": "MIXED-UNIT-500_Distillation_Tower_Reflux_Drum_Summary.pdf", "expected_page": 1, "evidence_type": "mixed", "expected_keywords": ["LPG storage", "TK-901"]},
        {"id": "Q56", "category": "Mixed Layout", "query": "What is the High-High liquid level trip setpoint for pump P-501 in the setpoint table?",
         "expected_filename": "MIXED-UNIT-500_Distillation_Tower_Reflux_Drum_Summary.pdf", "expected_page": 1, "evidence_type": "mixed", "expected_keywords": ["88% span", "LT-501"]},
        {"id": "Q57", "category": "Mixed Layout", "query": "What is the high alarm discharge pressure for pump P-501 in the drum D-501 table?",
         "expected_filename": "MIXED-UNIT-500_Distillation_Tower_Reflux_Drum_Summary.pdf", "expected_page": 1, "evidence_type": "mixed", "expected_keywords": ["16.5 bar", "PT-505"]},
        {"id": "Q58", "category": "Mixed Layout", "query": "Look at the nozzle orientation schematic for drum D-501: what size and purpose is Nozzle N1?",
         "expected_filename": "MIXED-UNIT-500_Distillation_Tower_Reflux_Drum_Summary.pdf", "expected_page": 1, "evidence_type": "mixed", "expected_keywords": ["Inlet 8-inch 300#", "Nozzle N1"]},
        {"id": "Q59", "category": "Mixed Layout", "query": "What nozzle is designated for the boot water drain on vessel D-501?",
         "expected_filename": "MIXED-UNIT-500_Distillation_Tower_Reflux_Drum_Summary.pdf", "expected_page": 1, "evidence_type": "mixed", "expected_keywords": ["Nozzle N3", "Boot Water Drain"]},
        {"id": "Q60", "category": "Mixed Layout", "query": "Which nozzle on drum D-501 feeds the pump suction lines?",
         "expected_filename": "MIXED-UNIT-500_Distillation_Tower_Reflux_Drum_Summary.pdf", "expected_page": 1, "evidence_type": "mixed", "expected_keywords": ["Nozzle N4", "Pump Suction 6-inch"]},

        # --- Category K: Tag Lookups (5 queries) ---
        {"id": "Q61", "category": "Tag Lookup", "query": "What is the function and equipment code for tag XV-105?",
         "expected_filename": "SOP-TURB-001_Turbine_Start_Procedures.pdf", "expected_page": 2, "evidence_type": "text", "expected_keywords": ["fuel gas shutoff valve", "XV-105"]},
        {"id": "Q62", "category": "Tag Lookup", "query": "What is the equipment service for tag P-102A?",
         "expected_filename": "SOP-TURB-001_Turbine_Start_Procedures.pdf", "expected_page": 1, "evidence_type": "text", "expected_keywords": ["auxiliary lube oil pump", "P-102A"]},
        {"id": "Q63", "category": "Tag Lookup", "query": "What device is identified by tag SOV-102 in the turbine procedure?",
         "expected_filename": "SOP-TURB-001_Turbine_Start_Procedures.pdf", "expected_page": 2, "evidence_type": "text", "expected_keywords": ["emergency trip solenoid", "SOV-102"]},
        {"id": "Q64", "category": "Tag Lookup", "query": "What instrument is tagged as PT-505 in distillation unit 500?",
         "expected_filename": "MIXED-UNIT-500_Distillation_Tower_Reflux_Drum_Summary.pdf", "expected_page": 1, "evidence_type": "table", "expected_keywords": ["Discharge Press", "PT-505"]},
        {"id": "Q65", "category": "Tag Lookup", "query": "What valve is identified by tag BDV-301 in the hydrocracker unit?",
         "expected_filename": "RCA-INCIDENT-2026-08_Hydrocracker_Trip_Incident_Investigation.pdf", "expected_page": 1, "evidence_type": "text", "expected_keywords": ["depressuring valve", "BDV-301"]},

        # --- Category L: Numeric Value Lookups (5 queries) ---
        {"id": "Q66", "category": "Numeric Lookup", "query": "What is the exact specific gravity SG value for fluid in pump P-401?",
         "expected_filename": "SPEC-PUMP-401_Centrifugal_Feed_Pumps_MultiColumn_Specs.pdf", "expected_page": 1, "evidence_type": "table", "expected_keywords": ["0.742", "SG"]},
        {"id": "Q67", "category": "Numeric Lookup", "query": "What is the shutoff head in meters for pump P-401?",
         "expected_filename": "SPEC-PUMP-401_Centrifugal_Feed_Pumps_MultiColumn_Specs.pdf", "expected_page": 1, "evidence_type": "table", "expected_keywords": ["268 m", "Shutoff Head"]},
        {"id": "Q68", "category": "Numeric Lookup", "query": "What is the spring compression tolerance in millimeters in DWG-SEAL-88?",
         "expected_filename": "DWG-MECH-SEAL-88_Mechanical_Seal_Assembly_CrossSection.pdf", "expected_page": 1, "evidence_type": "diagram", "expected_keywords": ["4.5 mm", "+/- 0.2 mm"]},
        {"id": "Q69", "category": "Numeric Lookup", "query": "What is the nominal head shell thickness in mm on vessel V-201?",
         "expected_filename": "SCAN-FORM-ASME-2026_Pressure_Vessel_Thickness_Checklist.pdf", "expected_page": 1, "evidence_type": "visual", "expected_keywords": ["18.0 mm", "Top Head"]},
        {"id": "Q70", "category": "Numeric Lookup", "query": "What was the measured vibration in mm/s RMS on motor M-401A during solo run?",
         "expected_filename": "MR-2026-COMP-04_Compressor_Overhaul_Narrative.pdf", "expected_page": 2, "evidence_type": "text", "expected_keywords": ["0.85 mm/s", "2980 RPM"]},

        # --- Category M: Cross-Document RCA Scenarios (5 queries) ---
        {"id": "Q71", "category": "RCA", "query": "Why did hydrocracker reactor R-301 experience thermal runaway and high pressure trip in RCA-2026-08?",
         "expected_filename": "RCA-INCIDENT-2026-08_Hydrocracker_Trip_Incident_Investigation.pdf", "expected_page": 1, "evidence_type": "rca_multichannel", "expected_keywords": ["FV-302", "SOV-305", "runaway"]},
        {"id": "Q72", "category": "RCA", "query": "What failure in junction box JB-102 initiated the reactor trip sequence?",
         "expected_filename": "RCA-INCIDENT-2026-08_Hydrocracker_Trip_Incident_Investigation.pdf", "expected_page": 1, "evidence_type": "rca_multichannel", "expected_keywords": ["JB-102", "spurious closure", "FV-302"]},
        {"id": "Q73", "category": "RCA", "query": "Why did emergency quench valve HV-305 fail to inject hydrogen into reactor R-301 during the incident?",
         "expected_filename": "RCA-INCIDENT-2026-08_Hydrocracker_Trip_Incident_Investigation.pdf", "expected_page": 1, "evidence_type": "rca_multichannel", "expected_keywords": ["SOV-305", "seized actuator"]},
        {"id": "Q74", "category": "RCA", "query": "What corrective action CAPA was issued regarding solenoid SOV-305 after the R-301 incident?",
         "expected_filename": "RCA-INCIDENT-2026-08_Hydrocracker_Trip_Incident_Investigation.pdf", "expected_page": 2, "evidence_type": "rca_multichannel", "expected_keywords": ["CAPA-881", "fail-safe de-energize"]},
        {"id": "Q75", "category": "RCA", "query": "How did utility steam fluctuations from boiler B-501 contribute to the hydrocracker trip?",
         "expected_filename": "RCA-INCIDENT-2026-08_Hydrocracker_Trip_Incident_Investigation.pdf", "expected_page": 2, "evidence_type": "rca_multichannel", "expected_keywords": ["SCAN-LOG-BOILER-2025", "preheat furnace"]},

        # --- Category N: Negative Out-Of-Distribution Queries (5 queries) ---
        {"id": "Q76", "category": "Negative", "query": "What is the catalyst regeneration temperature for fluid catalytic cracking unit FCC-700?",
         "expected_filename": None, "expected_page": None, "evidence_type": "none", "expected_keywords": []},
        {"id": "Q77", "category": "Negative", "query": "What is the chlorine dosage rate in the cooling tower biocidal treatment basin?",
         "expected_filename": None, "expected_page": None, "evidence_type": "none", "expected_keywords": []},
        {"id": "Q78", "category": "Negative", "query": "Where is the nitrogen purge connection on amine regenerator column C-801?",
         "expected_filename": None, "expected_page": None, "evidence_type": "none", "expected_keywords": []},
        {"id": "Q79", "category": "Negative", "query": "What is the emergency phone extension for the offshore marine terminal dockmaster?",
         "expected_filename": None, "expected_page": None, "evidence_type": "none", "expected_keywords": []},
        {"id": "Q80", "category": "Negative", "query": "What is the lubrication grease specification for crude tank mixer MX-12?",
         "expected_filename": None, "expected_page": None, "evidence_type": "none", "expected_keywords": []},
    ]


def split_benchmark_dataset(queries: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Splits 80 queries into 60% Calibration (48), 20% Validation (16), 20% Holdout (16).
    Guarantees deterministic, category-stratified distribution.
    """
    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for q in queries:
        by_cat.setdefault(q["category"], []).append(q)

    calibration = []
    validation = []
    holdout = []

    rng = random.Random(42)

    for cat, items in sorted(by_cat.items()):
        shuffled = list(items)
        rng.shuffle(shuffled)
        n = len(shuffled)
        
        n_holdout = max(1, round(n * 0.20))
        n_val = max(1, round(n * 0.20))
        n_calib = n - n_holdout - n_val
        if n_calib < 1:
            n_calib = 1
            if n_holdout > 1:
                n_holdout -= 1
            elif n_val > 1:
                n_val -= 1

        calib_items = shuffled[:n_calib]
        val_items = shuffled[n_calib:n_calib + n_val]
        holdout_items = shuffled[n_calib + n_val:]

        calibration.extend(calib_items)
        validation.extend(val_items)
        holdout.extend(holdout_items)

    return calibration, validation, holdout
