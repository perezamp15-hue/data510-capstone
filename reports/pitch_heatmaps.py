"""Build inline SVG pitch-location heat maps for HTML reports.

No PNG/PDF files are created. Each chart is returned as SVG markup and is
embedded directly in the final HTML report.
"""
from __future__ import annotations
from html import escape
from typing import Any
import numpy as np
import pandas as pd


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def build_location_heatmaps(
    pitches: pd.DataFrame,
    pitch_names: dict[str, str],
    *,
    minimum_pitches: int = 15,
    bins_x: int = 7,
    bins_z: int = 7,
) -> list[dict[str, Any]]:
    """Return one density heat map per pitch type as inline SVG.

    Coordinates use the catcher/umpire view. The strike-zone rectangle is a
    standardized visual reference; individual Statcast strike-zone heights
    vary by hitter.
    """
    if pitches.empty or "pitch_type" not in pitches:
        return []
    data = pitches.copy()
    data["plate_x"] = _numeric(data, "plate_x")
    data["plate_z"] = _numeric(data, "plate_z")
    data = data.dropna(subset=["pitch_type", "plate_x", "plate_z"])
    # Remove obvious tracking errors while retaining waste pitches.
    data = data[data["plate_x"].between(-2.5, 2.5) & data["plate_z"].between(0.0, 5.5)]
    rows: list[dict[str, Any]] = []
    for code, group in data.groupby("pitch_type"):
        if len(group) < minimum_pitches:
            continue
        svg = _heatmap_svg(group, str(code), pitch_names.get(str(code), str(code)), bins_x, bins_z)
        rows.append({
            "pitch_type": str(code),
            "pitch_name": pitch_names.get(str(code), str(code)),
            "pitch_count": int(len(group)),
            "svg": svg,
        })
    return sorted(rows, key=lambda item: item["pitch_count"], reverse=True)


def _heatmap_svg(group: pd.DataFrame, code: str, name: str, bins_x: int, bins_z: int) -> str:
    x_min, x_max = -2.0, 2.0
    z_min, z_max = 0.5, 4.5
    hist, x_edges, z_edges = np.histogram2d(
        group["plate_x"].to_numpy(),
        group["plate_z"].to_numpy(),
        bins=[bins_x, bins_z],
        range=[[x_min, x_max], [z_min, z_max]],
    )
    maximum = float(hist.max()) or 1.0
    width, height = 330, 350
    left, top, plot_w, plot_h = 42, 40, 250, 250
    cell_w, cell_h = plot_w / bins_x, plot_h / bins_z
    pieces = [
        f'<svg class="pitch-heatmap" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{escape(name)} pitch location heat map">',
        f'<text x="{width/2}" y="20" text-anchor="middle" class="heat-title">{escape(code)} — {escape(name)}</text>',
        f'<text x="{width/2}" y="338" text-anchor="middle" class="heat-caption">Catcher view · n={len(group)}</text>',
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#f8fafc" stroke="#ccd5df"/>',
    ]
    # Low density is light; high density is dark blue. Inline RGB avoids image files.
    for ix in range(bins_x):
        for iz in range(bins_z):
            density = float(hist[ix, iz]) / maximum
            if density <= 0:
                continue
            # SVG y is inverted relative to Statcast z.
            x = left + ix * cell_w
            y = top + (bins_z - 1 - iz) * cell_h
            opacity = 0.12 + 0.80 * density
            pieces.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell_w+0.3:.2f}" height="{cell_h+0.3:.2f}" '
                f'fill="rgb(20,74,122)" fill-opacity="{opacity:.3f}"/>'
            )
    # Standardized strike zone: x +/- 17/24 ft and z 1.5 to 3.5 ft.
    zone_x = left + ((-17/24 - x_min) / (x_max-x_min)) * plot_w
    zone_w = ((34/24) / (x_max-x_min)) * plot_w
    zone_y = top + ((z_max - 3.5) / (z_max-z_min)) * plot_h
    zone_h = ((3.5 - 1.5) / (z_max-z_min)) * plot_h
    pieces += [
        f'<rect x="{zone_x:.2f}" y="{zone_y:.2f}" width="{zone_w:.2f}" height="{zone_h:.2f}" fill="none" stroke="#111827" stroke-width="2"/>',
        f'<line x1="{left+plot_w/2:.2f}" y1="{top}" x2="{left+plot_w/2:.2f}" y2="{top+plot_h}" stroke="#ffffff" stroke-opacity=".45"/>',
        '<text x="18" y="168" text-anchor="middle" transform="rotate(-90 18 168)" class="axis-label">Pitch height</text>',
        f'<text x="{left}" y="310" class="axis-label">Glove side</text>',
        f'<text x="{left+plot_w}" y="310" text-anchor="end" class="axis-label">Arm side</text>',
        '</svg>',
    ]
    return ''.join(pieces)
