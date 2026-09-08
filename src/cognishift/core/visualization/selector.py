"""
Deterministic selector and specification builder for the CogniShift Visualization Pipeline.
Parses natural-language user requests into ArtifactRequestContracts and builds
provenanced VisualizationSpecs from real tabular data.
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import openpyxl
import pandas as pd

from cognishift.core.visualization.schemas import (
    ArtifactRequestContract,
    ChartType,
    VisualizationSpec,
)


def parse_artifact_request_contract(query: str) -> ArtifactRequestContract:
    """
    Deterministically parses user query into an authoritative ArtifactRequestContract.
    Extracts deliverables, chart types, counts, and explicit sheet/column hints.
    """
    q_lower = query.lower()
    input_file_pattern = r"\b[\w\.-]+\.(?:pdf|docx|xlsx|xls|csv|txt|pptx|json|yaml|yml)\b"
    def _strip_file_ref(match):
        start = match.start()
        prefix = q_lower[max(0, start - 10):start]
        if re.search(r"\b(?:as|to|into|save\s+as)\s+$", prefix):
            return match.group(0)
        return " "
    clean_q = re.sub(input_file_pattern, _strip_file_ref, q_lower)

    # 1. PDF requirement
    pdf_required = bool(re.search(r"\b(?:pdf|pdf\s+report|report\s+(?:in|as)\s+pdf|pdf\s+summary|summary\s+pdf)\b", clean_q)) or (
        bool(re.search(r"\b(?:create|generate|export|give\s+me)\b", clean_q)) and bool(re.search(r"\bpdf\b", clean_q))
    )
    # If the user specifically said "docx" or "word", pdf is false unless they also asked for pdf
    if any(w in clean_q for w in ["docx", "word format", "in docx", "as docx"]) and not re.search(r"\bpdf\b", clean_q):
        pdf_required = False

    # 2. DOCX requirement
    docx_required = any(w in clean_q for w in ["docx", "word format", "in docx", "as docx"]) or (
        bool(re.search(r"\b(?:create|generate|export|give\s+me)\b", clean_q)) and bool(re.search(r"\b(?:word|docx)\b", clean_q))
    )

    # 3. Excel requirement
    xlsx_required = any(w in clean_q for w in ["convert to excel", "export to excel", "into excel", "as excel", "as xlsx", "as spreadsheet"])

    # 4. PNG / Visualization requirement
    viz_keywords = [
        "visualization", "visualizations", "visualisation", "visualisations",
        "visualize", "visualise", "visualizing", "visualising",
        "graph", "graphs", "chart", "charts", "plot", "plots",
        "bar chart", "bar charts", "bar graph", "bar graphs",
        "line chart", "line charts", "line graph", "line graphs",
        "trend graph", "trend graphs", "trend chart", "trend charts",
        "scatter plot", "scatter plots", "scatter",
        "pie chart", "pie charts", "pie",
        "png", "pngs", "image", "images", "dashboard chart", "dashboard charts"
    ]
    png_required = any(re.search(rf"\b{re.escape(kw)}\b", clean_q) for kw in viz_keywords)

    # 5. PNG Count detection
    png_count = 0
    if png_required:
        two_chart_patterns = [
            r"\b(?:two|2)\s+(?:different\s+)?(?:charts|visualizations|visualisations|graphs|pngs|plots)\b",
            r"\bboth\s+(?:charts|visualizations|graphs)\b",
            r"\b(?:a\s+bar\s+chart\s+and\s+a\s+line\s+chart|bar\s+chart\s+plus\s+line\s+chart)\b",
            r"\b(?:two|2)\s+png\b"
        ]
        if any(re.search(pat, clean_q) for pat in two_chart_patterns):
            png_count = 2
        else:
            png_count = 1

    # 6. Chart Type detection
    requested_chart_type = ChartType.AUTO
    if re.search(r"\b(?:bar\s+chart|bar\s+graph|as\s+(?:a\s+)?bar)\b", clean_q):
        requested_chart_type = ChartType.BAR
    elif re.search(r"\b(?:line\s+chart|line\s+graph|trend\s+graph|numeric\s+trend|time\s+series|as\s+(?:a\s+)?line)\b", clean_q):
        requested_chart_type = ChartType.LINE
    elif re.search(r"\b(?:scatter\s+plot|scatter)\b", clean_q):
        requested_chart_type = ChartType.SCATTER
    elif re.search(r"\b(?:pie\s+chart|pie)\b", clean_q):
        requested_chart_type = ChartType.PIE

    # 7. Explicit sheet extraction
    explicit_sheet = None
    sheet_matches = re.findall(r"\b(?:only\s+the\s+|sheet\s+|from\s+the\s+)?([A-Za-z0-9_\-]+)\s+sheet\b", query, re.IGNORECASE)
    if not sheet_matches:
        sheet_matches = re.findall(r"\bsheet[:\s]+['\"]?([A-Za-z0-9_\-]+)['\"]?\b", query, re.IGNORECASE)
    if sheet_matches:
        explicit_sheet = sheet_matches[0].strip()

    is_deliv = pdf_required or docx_required or xlsx_required or png_required

    return ArtifactRequestContract(
        pdf_required=pdf_required,
        docx_required=docx_required,
        xlsx_required=xlsx_required,
        png_required=png_required,
        png_count=png_count,
        requested_chart_type=requested_chart_type,
        explicit_sheet=explicit_sheet,
        is_deliverable_request=is_deliv
    )


def select_target_sheet(
    workbook_path: Path,
    contract: ArtifactRequestContract,
    query: str
) -> Tuple[str, List[str], List[List[Any]]]:
    """
    Authoritatively selects the target sheet from an XLSX workbook.
    Obeys explicit sheet selection if requested; otherwise scores sheets
    based on query terms, metric names, and numeric data presence.
    """
    wb = openpyxl.load_workbook(str(workbook_path), data_only=True, read_only=True)
    sheet_names = wb.sheetnames

    target_sheet_name = None

    # Exact sheet selection if user requested one
    if contract.explicit_sheet:
        for sname in sheet_names:
            if contract.explicit_sheet.lower() in sname.lower() or sname.lower() in contract.explicit_sheet.lower():
                target_sheet_name = sname
                break
        if not target_sheet_name:
            target_sheet_name = contract.explicit_sheet

    if not target_sheet_name or target_sheet_name not in sheet_names:
        # Score candidate sheets based on query terms and data shape
        best_sheet = sheet_names[0]
        best_score = -1.0
        q_words = set(re.findall(r"\b\w{3,}\b", query.lower()))
        generic_financial_trend = (
            contract.requested_chart_type == ChartType.LINE
            and not contract.explicit_sheet
            and any(term in workbook_path.stem.lower() for term in ("financial", "history", "statement"))
        )

        for sname in sheet_names:
            ws = wb[sname]
            score = 0.0
            # Sheet name relevance
            sname_clean = sname.lower().replace("_", " ")
            if generic_financial_trend and "income statement" in sname_clean:
                # Prefer the primary time-series statement over an arbitrary
                # numerically dense project/CAPEX sheet for a generic trend.
                score += 50.0
            for w in q_words:
                if w in sname_clean:
                    score += 15.0

            # Inspect first 12 rows
            rows_sample = []
            for r_idx, row in enumerate(ws.iter_rows(values_only=True)):
                if r_idx > 12:
                    break
                rows_sample.append([c for c in row if c is not None])

            for row in rows_sample:
                row_str = " ".join(str(c).lower() for c in row)
                for w in q_words:
                    if w in row_str:
                        score += 3.0
                if any("fy" in str(c).lower() or "202" in str(c).lower() for c in row):
                    score += 5.0

            if score > best_score:
                best_score = score
                best_sheet = sname

        target_sheet_name = best_sheet

    # Load selected sheet and extract header and rows
    ws_target = wb[target_sheet_name]
    raw_rows = list(ws_target.iter_rows(values_only=True))
    wb.close()

    if not raw_rows:
        raise ValueError(f"Selected sheet '{target_sheet_name}' is empty.")

    # Header row detection
    header_idx = 0
    max_text_cells = 0
    for idx, r in enumerate(raw_rows[:10]):
        non_empty = [c for c in r if c is not None and str(c).strip()]
        if len(non_empty) > max_text_cells and any("fy" in str(c).lower() or "metric" in str(c).lower() or "tag" in str(c).lower() or "date" in str(c).lower() for c in non_empty):
            max_text_cells = len(non_empty)
            header_idx = idx

    headers = [str(c).strip() if c is not None else f"Col_{i}" for i, c in enumerate(raw_rows[header_idx])]
    data_rows = [list(r) for r in raw_rows[header_idx + 1:] if any(c is not None for c in r)]

    return target_sheet_name, headers, data_rows


def build_visualization_specs(
    file_path: Path,
    contract: ArtifactRequestContract,
    query: str
) -> List[VisualizationSpec]:
    """
    Inspects source tabular file, extracts real numeric/categorical series,
    and returns 1 or 2 ground-truth VisualizationSpecs.
    Never invents numbers or guesses data.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Source file for visualization not found: {file_path}")

    stem_name = file_path.stem
    ext = file_path.suffix.lower()
    sheet_name: Optional[str] = None
    specs: List[VisualizationSpec] = []

    q_lower = query.lower()

    if ext in (".xlsx", ".xls"):
        sheet_name, headers, data_rows = select_target_sheet(file_path, contract, query)
        df = pd.DataFrame(data_rows, columns=headers[:len(data_rows[0])] if data_rows else headers)
    elif ext == ".csv":
        # Robust CSV load
        try:
            df = pd.read_csv(file_path)
        except Exception:
            df = pd.read_csv(file_path, encoding="latin1")
        headers = list(df.columns)
    else:
        raise ValueError(f"Unsupported file format for visualization: {ext}. Expected CSV or XLSX.")

    if df.empty:
        raise ValueError(f"Source dataset '{file_path.name}' contains no rows to visualize.")

    clean_cols = [c for c in df.columns if not str(c).startswith("Unnamed")]

    # --- SPEC 1 GENERATION ---
    spec1 = _generate_single_spec(
        df=df,
        clean_cols=clean_cols,
        file_path=file_path,
        sheet_name=sheet_name,
        contract=contract,
        query=query,
        spec_index=1
    )
    specs.append(spec1)

    # --- SPEC 2 GENERATION (if 2 charts requested) ---
    if contract.png_count >= 2:
        spec2 = _generate_secondary_spec(
            df=df,
            clean_cols=clean_cols,
            file_path=file_path,
            sheet_name=sheet_name,
            contract=contract,
            query=query,
            primary_spec=spec1
        )
        if spec2 is not None:
            specs.append(spec2)

    return specs


def _generate_single_spec(
    df: pd.DataFrame,
    clean_cols: List[str],
    file_path: Path,
    sheet_name: Optional[str],
    contract: ArtifactRequestContract,
    query: str,
    spec_index: int = 1
) -> VisualizationSpec:
    """Builds a primary visualization spec matching query constraints."""
    q_lower = query.lower()
    stem = file_path.stem

    # Strategy 1: Horizontal Metric Row in Financial Matrix (e.g. Operating EBITDA across FY columns)
    first_col = clean_cols[0] if clean_cols else df.columns[0]
    metric_rows = df[first_col].dropna().astype(str).tolist()
    fy_cols = [c for c in clean_cols if re.search(r"\bfy\b|\b20\d\d\b", str(c).lower())]

    # Check if user mentioned a specific row item (e.g. Operating EBITDA, Gross Revenue)
    matched_row_idx = None
    requested_metric = any(
        term in q_lower
        for term in ("ebitda", "revenue", "turnover", "profit after tax", " pat ")
    )
    if not requested_metric and contract.requested_chart_type == ChartType.LINE:
        matched_row_idx = next(
            (idx for idx, value in enumerate(metric_rows) if "operating ebitda" in value.lower()),
            None,
        )
    for r_idx, val in enumerate(metric_rows):
        val_clean = val.lower()
        if any(term in val_clean for term in ["operating ebitda", "ebitda", "gross revenue", "revenue from operations", "pat", "profit after tax"]):
            if any(term in q_lower for term in ["ebitda", "operating ebitda"]) and "ebitda" in val_clean:
                matched_row_idx = r_idx
                break
            elif any(term in q_lower for term in ["revenue", "turnover"]) and "revenue" in val_clean:
                matched_row_idx = r_idx
                break
            elif matched_row_idx is None:
                matched_row_idx = r_idx

    if matched_row_idx is not None and len(fy_cols) >= 3:
        row_label = str(df.iloc[matched_row_idx][first_col]).strip()
        row_vals = []
        clean_fy = []
        for c in fy_cols:
            raw_v = df.iloc[matched_row_idx][c]
            try:
                # Clean numeric value
                num_v = float(str(raw_v).replace(",", "").replace("%", "").replace("₹", "").strip())
                row_vals.append(num_v)
                clean_fy.append(str(c).replace("FY ", "FY").strip())
            except (ValueError, TypeError):
                continue

        if len(row_vals) >= 3:
            chart_t = contract.requested_chart_type
            if chart_t == ChartType.AUTO:
                chart_t = ChartType.LINE

            filename = f"{stem}_ebitda_trend.png" if "ebitda" in row_label.lower() else f"{stem}_{chart_t.value}.png"
            return VisualizationSpec(
                title=f"{row_label} Trajectory ({sheet_name or stem})",
                source_file=file_path.name,
                source_sheet=sheet_name,
                chart_type=chart_t,
                x_column="Fiscal Period",
                y_columns=[row_label],
                x_values=clean_fy,
                series={row_label: row_vals},
                x_label="Fiscal Period",
                y_label="Value (INR Crores)",
                output_filename=filename,
                provenance={
                    "source_file": file_path.name,
                    "source_sheet": sheet_name,
                    "x_column": "Fiscal Period",
                    "y_columns": [row_label],
                    "transformation": f"ROW_FILTER('{row_label}') across {len(clean_fy)} fiscal periods",
                    "chart_type": chart_t.value,
                    "row_count": len(clean_fy)
                }
            )

    # Strategy 2: Group By Categorical Column (e.g. Equipment Tag, Health Status, Order Type)
    # Search for matching column in query
    group_col = None
    target_metric_col = None

    # Find group column (e.g. equipment, health, status, plant section, unit)
    candidate_group_cols = [
        c for c in clean_cols
        if any(k in str(c).lower() for k in ["equipment_tag", "tag_number", "health_integrity_status", "status", "order_type", "instrument_type", "plant_unit_code", "plant_section", "priority"])
    ]

    # If query mentions a specific column, prioritize it
    for c in candidate_group_cols:
        col_clean = str(c).lower().replace("_", " ")
        if any(word in q_lower for word in col_clean.split()):
            group_col = c
            break

    if not group_col and candidate_group_cols:
        group_col = candidate_group_cols[0]

    # Find metric column (e.g. cost, downtime, pressure)
    candidate_metric_cols = [
        c for c in clean_cols
        if any(k in str(c).lower() for k in ["total_cost", "cost", "downtime_hours", "operating_pressure", "design_pressure", "value", "reading"])
    ]

    for c in candidate_metric_cols:
        col_clean = str(c).lower().replace("_", " ")
        if any(word in q_lower for word in col_clean.split()):
            target_metric_col = c
            break

    if group_col:
        # If cost/metric requested specifically:
        if ("cost" in q_lower or target_metric_col) and target_metric_col:
            agg_df = df.groupby(group_col)[target_metric_col].sum().sort_values(ascending=False).head(8)
            x_vals = [str(x) for x in agg_df.index]
            y_vals = [round(float(y), 2) for y in agg_df.values]
            y_label = f"Total {target_metric_col.replace('_', ' ')}"
            title = f"{y_label} by {group_col.replace('_', ' ')}"
            chart_t = contract.requested_chart_type if contract.requested_chart_type != ChartType.AUTO else ChartType.BAR
            filename = f"{stem}_cost_by_equipment.png" if "cost" in q_lower else f"{stem}_{group_col}_metric.png"
            transformation = f"GROUP_BY({group_col}) -> SUM({target_metric_col})"
        else:
            # Value counts (Frequency / Work Order Count / Instrument Count)
            agg_df = df[group_col].value_counts().head(8)
            x_vals = [str(x) for x in agg_df.index]
            y_vals = [int(y) for y in agg_df.values]
            y_label = "Record / Work Order Count"
            title = f"Distribution by {group_col.replace('_', ' ')}"
            chart_t = contract.requested_chart_type if contract.requested_chart_type != ChartType.AUTO else ChartType.BAR
            filename = f"{stem}_{group_col}_distribution.png"
            transformation = f"GROUP_BY({group_col}) -> COUNT(*)"

        return VisualizationSpec(
            title=title,
            source_file=file_path.name,
            source_sheet=sheet_name,
            chart_type=chart_t,
            x_column=group_col,
            y_columns=[y_label],
            x_values=x_vals,
            series={y_label: y_vals},
            x_label=group_col.replace("_", " ").title(),
            y_label=y_label,
            output_filename=filename,
            provenance={
                "source_file": file_path.name,
                "source_sheet": sheet_name,
                "x_column": group_col,
                "y_columns": [y_label],
                "transformation": transformation,
                "chart_type": chart_t.value,
                "row_count": len(x_vals)
            }
        )

    # Strategy 3: General numeric fallback from first 2 numeric columns
    numeric_cols = [c for c in clean_cols if pd.api.types.is_numeric_dtype(df[c])]
    if numeric_cols:
        num_col = numeric_cols[0]
        label_col = clean_cols[0] if clean_cols[0] != num_col else "Index"
        sample_df = df.head(10)
        x_vals = [str(x) for x in (sample_df[label_col].tolist() if label_col != "Index" else range(1, len(sample_df) + 1))]
        y_vals = [float(y) for y in sample_df[num_col].tolist()]
        chart_t = contract.requested_chart_type if contract.requested_chart_type != ChartType.AUTO else ChartType.LINE
        return VisualizationSpec(
            title=f"{num_col.replace('_', ' ')} Trend",
            source_file=file_path.name,
            source_sheet=sheet_name,
            chart_type=chart_t,
            x_column=label_col,
            y_columns=[num_col],
            x_values=x_vals,
            series={num_col: y_vals},
            x_label=label_col.replace("_", " ").title(),
            y_label=num_col.replace("_", " ").title(),
            output_filename=f"{stem}_metric_trend.png",
            provenance={
                "source_file": file_path.name,
                "source_sheet": sheet_name,
                "x_column": label_col,
                "y_columns": [num_col],
                "transformation": f"HEAD(10) on {num_col}",
                "chart_type": chart_t.value,
                "row_count": len(x_vals)
            }
        )

    raise ValueError(f"No suitable numeric or categorical series found in '{file_path.name}' to generate a truthful visualization without fabrication.")


def _generate_secondary_spec(
    df: pd.DataFrame,
    clean_cols: List[str],
    file_path: Path,
    sheet_name: Optional[str],
    contract: ArtifactRequestContract,
    query: str,
    primary_spec: VisualizationSpec
) -> Optional[VisualizationSpec]:
    """Builds a distinct secondary visualization spec when 2 charts are requested."""
    stem = file_path.stem
    primary_x = primary_spec.x_column

    # Find another categorical or metric column distinct from primary
    alternative_cols = [c for c in clean_cols if c != primary_x and any(k in str(c).lower() for k in ["priority", "order_type", "plant_section", "plant_unit_code", "instrument_type", "total_cost", "downtime_hours"])]

    if alternative_cols:
        sec_col = alternative_cols[0]
        # Alternate chart type (LINE if primary was BAR, or vice-versa)
        alt_chart_t = ChartType.LINE if primary_spec.chart_type == ChartType.BAR else ChartType.BAR

        if any(k in sec_col.lower() for k in ["cost", "hours"]):
            # Metric aggregation by primary X or top items
            agg_df = df.groupby(primary_x)[sec_col].sum().sort_values(ascending=False).head(8)
            x_vals = [str(x) for x in agg_df.index]
            y_vals = [round(float(y), 2) for y in agg_df.values]
            y_label = f"Total {sec_col.replace('_', ' ')}"
            title = f"{y_label} across {primary_x.replace('_', ' ')}"
            trans = f"GROUP_BY({primary_x}) -> SUM({sec_col})"
        else:
            agg_df = df[sec_col].value_counts().head(8)
            x_vals = [str(x) for x in agg_df.index]
            y_vals = [int(y) for y in agg_df.values]
            y_label = "Distribution Count"
            title = f"Operational Breakdown by {sec_col.replace('_', ' ')}"
            trans = f"GROUP_BY({sec_col}) -> COUNT(*)"

        return VisualizationSpec(
            title=title,
            source_file=file_path.name,
            source_sheet=sheet_name,
            chart_type=alt_chart_t,
            x_column=sec_col,
            y_columns=[y_label],
            x_values=x_vals,
            series={y_label: y_vals},
            x_label=sec_col.replace("_", " ").title(),
            y_label=y_label,
            output_filename=f"{stem}_secondary_{alt_chart_t.value}.png",
            provenance={
                "source_file": file_path.name,
                "source_sheet": sheet_name,
                "x_column": sec_col,
                "y_columns": [y_label],
                "transformation": trans,
                "chart_type": alt_chart_t.value,
                "row_count": len(x_vals)
            }
        )

    # Return None if no legitimate independent second chart can be derived (fail closed)
    return None
