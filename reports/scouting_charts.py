"""Inline SVG charts for the HTML-only scouting report."""
from __future__ import annotations
from html import escape
from typing import Any
import hashlib
import re
import numpy as np
import pandas as pd


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    if col not in frame:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[col], errors="coerce")


def target_zone_svg(target: str, pitch_code: str = "") -> str:
    width, height = 260, 265
    left, top, pw, ph = 42, 28, 176, 190
    zone_x, zone_y, zone_w, zone_h = 72, 66, 116, 116
    target = (target or "zone edge").lower()
    coords = {
        "upper third": (130, 82), "down and away": (166, 164), "down and in": (94, 164),
        "below the zone": (130, 202), "arm-side edge": (184, 132), "glove-side edge": (76, 132),
        "zone edge": (176, 132),
    }
    x, y = coords.get(target, coords["zone edge"])
    return f'''<svg class="target-zone" viewBox="0 0 {width} {height}" role="img" aria-label="Recommended target {escape(target)}">
<text x="130" y="18" text-anchor="middle" class="chart-title">{escape(pitch_code)} target: {escape(target)}</text>
<rect x="{left}" y="{top}" width="{pw}" height="{ph}" rx="8" fill="#f8fafc" stroke="#cbd5e1"/>
<rect x="{zone_x}" y="{zone_y}" width="{zone_w}" height="{zone_h}" fill="none" stroke="#1f2937" stroke-width="2"/>
<line x1="130" y1="{zone_y}" x2="130" y2="{zone_y+zone_h}" stroke="#d1d5db"/><line x1="{zone_x}" y1="124" x2="{zone_x+zone_w}" y2="124" stroke="#d1d5db"/>
<circle cx="{x}" cy="{y}" r="19" fill="#dc2626" fill-opacity=".18"/><circle cx="{x}" cy="{y}" r="8" fill="#dc2626"/><circle cx="{x}" cy="{y}" r="3" fill="white"/>
<text x="130" y="250" text-anchor="middle" class="chart-caption">Catcher view</text></svg>'''


def batter_hot_cold_svg(
    pitches: pd.DataFrame,
    title: str,
    pitch_type: str | None = None,
    bins: int = 5,
) -> str:
    """Render a compact interactive batter hot/cold SVG.

    The SVG retains its full internal coordinate system for sharp rendering and
    accurate hover targets. The HTML stylesheet limits the displayed width to
    250px so hitter cards remain compact.
    """
    data = pitches.copy()
    if pitch_type and "pitch_type" in data:
        data = data[data["pitch_type"].astype(str) == str(pitch_type)]
    data["plate_x"] = _num(data, "plate_x")
    data["plate_z"] = _num(data, "plate_z")
    data["damage"] = _num(data, "expected_woba")
    fallback = _num(data, "exit_velocity") / 250.0
    data["damage"] = data["damage"].fillna(fallback)
    data = data.dropna(subset=["plate_x", "plate_z", "damage"])
    data = data[data["plate_x"].between(-2, 2) & data["plate_z"].between(.5, 4.5)]
    if len(data) < 12:
        return '<div class="empty-chart">Not enough located batted-ball history for this view.</div>'
    x_edges = np.linspace(-2, 2, bins + 1); z_edges = np.linspace(.5, 4.5, bins + 1)
    sums = np.zeros((bins, bins)); counts = np.zeros((bins, bins))
    xi = np.clip(np.digitize(data["plate_x"], x_edges)-1, 0, bins-1)
    zi = np.clip(np.digitize(data["plate_z"], z_edges)-1, 0, bins-1)
    for x, z, d in zip(xi, zi, data["damage"]):
        sums[x,z] += float(d); counts[x,z] += 1
    means = np.divide(sums, counts, out=np.full_like(sums, np.nan), where=counts>0)
    width, height = 320, 365; left, top, pw, ph = 42, 40, 240, 240; cw, ch = pw/bins, ph/bins
    # Each inline SVG needs a unique gradient ID because IDs share the same HTML document namespace.
    gradient_seed = f"{title}|{pitch_type or 'overall'}"
    gradient_id = "heat-gradient-" + hashlib.sha1(gradient_seed.encode("utf-8")).hexdigest()[:10]
    pieces=[f'<svg class="hot-cold" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)} hot and cold zones">',
            f'<defs><linearGradient id="{gradient_id}" x1="0%" y1="0%" x2="100%" y2="0%">'
            '<stop offset="0%" stop-color="rgb(35,95,190)"/>'
            '<stop offset="50%" stop-color="rgb(130,73,123)"/>'
            '<stop offset="100%" stop-color="rgb(225,50,55)"/>'
            '</linearGradient></defs>',
            f'<text x="160" y="20" text-anchor="middle" class="chart-title">{escape(title)}</text>',
            f'<rect x="{left}" y="{top}" width="{pw}" height="{ph}" fill="#f8fafc" stroke="#cbd5e1"/>']
    for ix in range(bins):
        for iz in range(bins):
            if np.isnan(means[ix,iz]): continue
            value=float(means[ix,iz]); normalized=max(0,min(1,(value-.18)/.28))
            # Blue = cold, red = hot.
            r=int(35+190*normalized); g=int(95-45*normalized); b=int(190-135*normalized)
            x=left+ix*cw; y=top+(bins-1-iz)*ch
            pieces.append(f'<rect class="zone-cell" data-value="{value:.3f}" x="{x:.1f}" y="{y:.1f}" width="{cw+.2:.1f}" height="{ch+.2:.1f}" fill="rgb({r},{g},{b})"><title>xwOBA/damage proxy {value:.3f}; n={int(counts[ix,iz])}</title></rect>')
    zx=left+((-17/24+2)/4)*pw; zw=(34/24/4)*pw; zy=top+((4.5-3.5)/4)*ph; zh=(2/4)*ph
    pieces += [
        f'<rect x="{zx:.1f}" y="{zy:.1f}" width="{zw:.1f}" height="{zh:.1f}" fill="none" stroke="#111827" stroke-width="2"/>',
        '<text x="160" y="300" text-anchor="middle" class="chart-caption">Damage scale · catcher view</text>',
        f'<rect x="58" y="310" width="204" height="13" rx="6.5" fill="url(#{gradient_id})" stroke="#cbd5e1"/>',
        '<line x1="58" y1="323" x2="58" y2="328" stroke="#64748b"/>',
        '<line x1="160" y1="323" x2="160" y2="328" stroke="#64748b"/>',
        '<line x1="262" y1="323" x2="262" y2="328" stroke="#64748b"/>',
        '<text x="58" y="341" text-anchor="start" class="heat-caption">Lower damage</text>',
        '<text x="160" y="341" text-anchor="middle" class="heat-caption">Neutral</text>',
        '<text x="262" y="341" text-anchor="end" class="heat-caption">Higher damage</text>',
        '<text x="58" y="357" text-anchor="start" class="heat-caption">≤ .180</text>',
        '<text x="160" y="357" text-anchor="middle" class="heat-caption">.320</text>',
        '<text x="262" y="357" text-anchor="end" class="heat-caption">≥ .460</text>',
        '</svg>'
    ]
    return ''.join(pieces)


def scatter_svg(points: list[dict[str, Any]], x_key: str, y_key: str, title: str, x_label: str, y_label: str) -> str:
    if not points:
        return '<div class="empty-chart">Not enough tracking data.</div>'
    xs=[float(p[x_key]) for p in points]; ys=[float(p[y_key]) for p in points]
    xmin,xmax=min(xs),max(xs); ymin,ymax=min(ys),max(ys)
    if xmin==xmax: xmin-=1; xmax+=1
    if ymin==ymax: ymin-=1; ymax+=1
    padx=(xmax-xmin)*.18; pady=(ymax-ymin)*.18; xmin-=padx;xmax+=padx;ymin-=pady;ymax+=pady
    w,h=500,360;l,t,pw,ph=66,42,390,255
    sx=lambda x:l+(x-xmin)/(xmax-xmin)*pw
    sy=lambda y:t+ph-(y-ymin)/(ymax-ymin)*ph
    pieces=[f'<svg class="scatter-chart" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">',f'<text x="250" y="21" text-anchor="middle" class="chart-title">{escape(title)}</text>',f'<rect x="{l}" y="{t}" width="{pw}" height="{ph}" fill="#f8fafc" stroke="#cbd5e1"/>']
    if xmin<0<xmax: pieces.append(f'<line x1="{sx(0):.1f}" y1="{t}" x2="{sx(0):.1f}" y2="{t+ph}" stroke="#d1d5db"/>')
    if ymin<0<ymax: pieces.append(f'<line x1="{l}" y1="{sy(0):.1f}" x2="{l+pw}" y2="{sy(0):.1f}" stroke="#d1d5db"/>')
    for p in points:
        x,y=sx(float(p[x_key])),sy(float(p[y_key])); code=str(p.get("pitch_type", ""))
        pieces.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="10" class="pitch-point"><title>{escape(code)} — {escape(str(p.get("pitch_name",code)))}; n={p.get("sample",0)}</title></circle><text x="{x:.1f}" y="{y+4:.1f}" text-anchor="middle" class="point-label">{escape(code)}</text>')
    pieces += [f'<text x="{l+pw/2}" y="338" text-anchor="middle" class="chart-caption">{escape(x_label)}</text>',f'<text x="18" y="{t+ph/2}" text-anchor="middle" transform="rotate(-90 18 {t+ph/2})" class="chart-caption">{escape(y_label)}</text>','</svg>']
    return ''.join(pieces)


def decision_tree_html(tree: dict[str, Any]) -> str:
    if not tree: return '<p>No decision tree available.</p>'
    def node(key: str) -> str:
        n=tree.get(key,{})
        return f'<div class="tree-node"><b>{escape(str(n.get("label","")))}</b><span>{escape(str(n.get("pitch","—")))} · {escape(str(n.get("target","—")))}</span></div>'
    return f'<div class="decision-tree">{node("start")}<div class="tree-branches"><div><span class="branch-label">Strike / foul</span>{node("called_strike_or_foul")}{node("two_strikes")}</div><div><span class="branch-label">Ball</span>{node("ball")}</div></div></div>'
