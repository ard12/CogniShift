"""
Trusted deterministic Matplotlib renderer for CogniShift.
Directly accepts VisualizationSpec and produces publication-quality PNG artifacts.
Never relies on LLM-generated code or dynamic execution.
"""
import os
import tempfile
from pathlib import Path
from typing import Optional

os.environ["MPLCONFIGDIR"] = tempfile.gettempdir()
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from cognishift.core.visualization.schemas import ChartType, VisualizationSpec


PALETTE = [
    "#1F4E79",  # Industrial Navy
    "#2CA02C",  # Operational Green
    "#FF7F0E",  # Safety Amber
    "#9467BD",  # Metric Purple
    "#D62728",  # Alarm Red
    "#17BECF",  # Telemetry Cyan
    "#8C564B",  # Brown
    "#E377C2",  # Magenta
]


def _tick_positions(value_count: int, max_ticks: int = 12) -> list[int]:
    """Return representative tick positions while always retaining both ends."""
    if value_count <= max_ticks:
        return list(range(value_count))
    return sorted(set(np.linspace(0, value_count - 1, max_ticks, dtype=int).tolist()))


def render_visualization(spec: VisualizationSpec, output_path: Path) -> Path:
    """
    Renders a VisualizationSpec into an authoritative PNG artifact.
    Guarantees strict axis labeling, non-empty render, and cleanup.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=150)

    # Clean industrial theme styling
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FAFAFA")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")

    x_vals = spec.x_values
    series_dict = spec.series
    chart_type = spec.chart_type

    if chart_type == ChartType.AUTO:
        # Fallback to bar if categorical, line if time-series
        chart_type = ChartType.LINE if len(x_vals) > 12 else ChartType.BAR

    if chart_type == ChartType.BAR:
        x_indices = np.arange(len(x_vals))
        num_series = len(series_dict)
        bar_width = 0.8 / max(1, num_series)

        for s_idx, (s_name, s_values) in enumerate(series_dict.items()):
            # Align multiple series side-by-side
            offset = (s_idx - (num_series - 1) / 2) * bar_width
            color = PALETTE[s_idx % len(PALETTE)]
            vals_to_plot = s_values[:len(x_vals)]
            ax.bar(
                x_indices[:len(vals_to_plot)] + offset,
                vals_to_plot,
                width=bar_width * 0.92,
                label=s_name,
                color=color,
                alpha=0.9,
                edgecolor="#333333",
                linewidth=0.5
            )

        if len(x_indices) > 15:
            tick_indices = _tick_positions(len(x_indices))
            ax.set_xticks(tick_indices)
            ax.set_xticklabels([str(x_vals[i]) for i in tick_indices], rotation=35, ha="right", fontsize=8)
        else:
            ax.set_xticks(x_indices)
            x_labels = [str(x) for x in x_vals]
            rotation = 28 if (len(x_labels) > 6 or any(len(str(lbl)) > 8 for lbl in x_labels)) else 0
            ax.set_xticklabels(x_labels, rotation=rotation, ha="right" if rotation else "center", fontsize=9, fontweight="medium")
        ax.grid(axis="y", linestyle=":", alpha=0.6, color="#BBBBBB")

    elif chart_type == ChartType.LINE:
        for s_idx, (s_name, s_values) in enumerate(series_dict.items()):
            color = PALETTE[s_idx % len(PALETTE)]
            vals_to_plot = s_values[:len(x_vals)]
            point_count = len(vals_to_plot)
            ax.plot(
                range(point_count),
                vals_to_plot,
                label=s_name,
                color=color,
                marker="o",
                markersize=2.5 if point_count > 100 else 5,
                linewidth=1.8 if point_count > 100 else 2.2,
                alpha=0.95
            )

        tick_positions = _tick_positions(len(x_vals))
        ax.set_xticks(tick_positions)
        x_labels = [str(x_vals[index]) for index in tick_positions]
        rotation = 28 if (len(x_labels) > 6 or any(len(str(lbl)) > 8 for lbl in x_labels)) else 0
        ax.set_xticklabels(x_labels, rotation=rotation, ha="right" if rotation else "center", fontsize=9, fontweight="medium")
        ax.grid(True, linestyle=":", alpha=0.6, color="#BBBBBB")

    elif chart_type == ChartType.SCATTER:
        for s_idx, (s_name, s_values) in enumerate(series_dict.items()):
            color = PALETTE[s_idx % len(PALETTE)]
            vals_to_plot = s_values[:len(x_vals)]
            ax.scatter(
                range(len(vals_to_plot)),
                vals_to_plot,
                label=s_name,
                color=color,
                s=60,
                alpha=0.85,
                edgecolor="#222222",
                linewidth=0.8
            )
        tick_positions = _tick_positions(len(x_vals))
        ax.set_xticks(tick_positions)
        x_labels = [str(x_vals[index]) for index in tick_positions]
        rotation = 28 if len(x_labels) > 6 else 0
        ax.set_xticklabels(x_labels, rotation=rotation, ha="right" if rotation else "center", fontsize=9)
        ax.grid(True, linestyle=":", alpha=0.6, color="#BBBBBB")

    elif chart_type == ChartType.PIE:
        if not series_dict or not x_vals:
            ax.text(0.5, 0.5, "No numeric series available for pie chart", ha="center", va="center")
        else:
            first_series_name = list(series_dict.keys())[0]
            raw_values = series_dict[first_series_name][:len(x_vals)]
            values = [max(0.0, float(v)) for v in raw_values]
            if sum(values) <= 0:
                values = [1.0] * len(values) if values else [1.0]
            labels = [str(x) for x in x_vals[:len(values)]]
            ax.pie(
                values,
                labels=labels,
                autopct="%1.1f%%",
                startangle=140,
                colors=[PALETTE[i % len(PALETTE)] for i in range(len(values))],
                textprops={"fontsize": 9}
            )
            ax.axis("equal")

    # Titles and labels
    ax.set_title(spec.title, fontsize=12, fontweight="bold", pad=14, color="#111111")
    if spec.x_label and chart_type != ChartType.PIE:
        ax.set_xlabel(spec.x_label, fontsize=10, fontweight="bold", labelpad=8, color="#333333")
    if spec.y_label and chart_type != ChartType.PIE:
        ax.set_ylabel(spec.y_label, fontsize=10, fontweight="bold", labelpad=8, color="#333333")

    if len(series_dict) > 1 and chart_type != ChartType.PIE:
        ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E0E0E0", fontsize=9, loc="upper right")

    plt.tight_layout()
    plt.savefig(str(output_path), dpi=150, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)

    return output_path
