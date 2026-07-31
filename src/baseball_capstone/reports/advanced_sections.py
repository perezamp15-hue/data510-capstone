"""HTML and SVG renderers for advanced scouting sections."""
from __future__ import annotations

from html import escape
from typing import Any


PITCH_LABELS = {
    "FF": "Four-Seam", "SI": "Sinker", "FC": "Cutter", "SL": "Slider",
    "ST": "Sweeper", "CU": "Curveball", "KC": "Knuckle Curve",
    "CH": "Changeup", "FS": "Splitter", "KN": "Knuckleball",
}


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if number != number:
        return "—"
    return f"{number:.{digits}f}{suffix}"


def advanced_css() -> str:
    return """
<style id="advanced-scouting-css">
.advanced-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.advanced-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:10px}
.advanced-card{border:1px solid var(--line,#d9e2ea);border-radius:12px;padding:15px;background:#fbfdff}
.advanced-card h3{margin-top:0}.advanced-table-wrap{overflow-x:auto}
.advanced-chart{width:100%;height:auto;display:block}.advanced-caption{color:var(--muted,#657487);font-size:12px}
.heat-grid{display:grid;grid-template-columns:repeat(9,1fr);aspect-ratio:1/1;gap:2px;max-width:440px;margin:auto;background:#d8e0e8;padding:3px;border-radius:9px}
.heat-cell{border-radius:2px;min-width:0}.heat-zone{position:relative;max-width:440px;margin:auto}.heat-zone:after{content:"";position:absolute;left:29.2%;right:29.2%;top:25%;bottom:25%;border:3px solid #17212b;pointer-events:none}
.heat-legend{height:11px;border-radius:8px;background:linear-gradient(90deg,#edf2f7,#9db9d2,#346b9b,#a33a35);margin:10px auto 4px;max-width:300px}
.release-legend{display:flex;flex-wrap:wrap;gap:8px;justify-content:center}.release-key{font-size:12px;padding:4px 8px;border:1px solid var(--line,#d9e2ea);border-radius:999px}
.trend-bars{display:flex;align-items:end;gap:8px;height:190px;padding:16px 8px 28px;border-left:1px solid #aab6c1;border-bottom:1px solid #aab6c1}.trend-bar{flex:1;min-width:26px;text-align:center;position:relative}.trend-bar i{display:block;background:var(--blue,#173d67);border-radius:5px 5px 0 0;min-height:3px}.trend-bar span{display:block;font-size:11px;margin-top:5px}.trend-bar b{font-size:10px;position:absolute;left:50%;transform:translateX(-50%);bottom:calc(100% + 3px)}
@media(max-width:850px){.advanced-grid{grid-template-columns:1fr}}
</style>
"""


def _heat_color(value: float) -> str:
    v = max(0.0, min(1.0, float(value)))
    if v < .33:
        t = v / .33
        return f"rgb({int(237-80*t)},{int(242-35*t)},{int(247-25*t)})"
    if v < .67:
        t = (v-.33)/.34
        return f"rgb({int(157-105*t)},{int(185-78*t)},{int(210-55*t)})"
    t = (v-.67)/.33
    return f"rgb({int(52+111*t)},{int(107-49*t)},{int(155-102*t)})"


def render_heatmap(title: str, heatmap: dict[str, Any]) -> str:
    grid = heatmap.get("grid") or []
    if not grid:
        return f'<div class="advanced-card"><h3>{escape(title)}</h3><p class="advanced-caption">No valid pitch-location samples.</p></div>'
    cells = "".join(
        f'<div class="heat-cell" title="Relative intensity {float(v):.2f}" style="background:{_heat_color(float(v))}"></div>'
        for row in grid for v in row
    )
    return f"""
    <div class="advanced-card"><h3>{escape(title)}</h3>
      <div class="heat-zone"><div class="heat-grid">{cells}</div></div>
      <div class="heat-legend"></div>
      <p class="advanced-caption">Low intensity → high intensity · strike zone outlined · catcher's view</p>
    </div>"""


def render_release_chart(name: str, release: list[dict[str, Any]]) -> str:
    if not release:
        return '<div class="advanced-card"><h3>Pitch Release Points</h3><p class="advanced-caption">No release-position data available.</p></div>'
    xs = [float(r["x"]) for r in release]
    zs = [float(r["z"]) for r in release]
    x_min, x_max = min(xs)-.35, max(xs)+.35
    z_min, z_max = min(zs)-.35, max(zs)+.35
    def sx(x: float) -> float: return 90 + (x-x_min)/max(x_max-x_min,.01)*430
    def sy(z: float) -> float: return 300 - (z-z_min)/max(z_max-z_min,.01)*210
    points=[]; keys=[]
    for idx,row in enumerate(release):
        x,y=sx(float(row['x'])),sy(float(row['z']))
        radius=max(7,min(15,7+float(row.get('count',0))**.5/3))
        shade=35 + (idx*27)%150
        color=f"hsl({shade} 55% 42%)"
        points.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color}" fill-opacity=".78" stroke="#fff" stroke-width="2"><title>{escape(str(row["pitch_type"]))}: x {row["x"]}, z {row["z"]}, n {row["count"]}</title></circle><text x="{x:.1f}" y="{y+4:.1f}" text-anchor="middle" fill="#fff" font-size="10" font-weight="700">{escape(str(row["pitch_type"]))}</text>')
        keys.append(f'<span class="release-key"><b>{escape(str(row["pitch_type"]))}</b> {escape(PITCH_LABELS.get(str(row["pitch_type"]),""))} · SD {float(row["x_sd"])+float(row["z_sd"]):.2f} ft</span>')
    svg=f"""<svg class="advanced-chart" viewBox="0 0 600 390" role="img" aria-label="{escape(name)} release points from catcher's view">
      <rect x="45" y="38" width="510" height="285" rx="14" fill="#f7fafc" stroke="#cbd5e1"/>
      <ellipse cx="300" cy="336" rx="92" ry="22" fill="#b78a55"/><rect x="263" y="326" width="74" height="7" rx="3" fill="#f7f2e8"/>
      <path d="M278 314 L322 314 L310 328 L290 328 Z" fill="#fff" stroke="#7d8790"/><text x="300" y="372" text-anchor="middle" font-size="12" fill="#657487">Mound and rubber shown for orientation · catcher’s view</text>
      <line x1="300" y1="50" x2="300" y2="315" stroke="#d7dee5" stroke-dasharray="5 5"/>{''.join(points)}</svg>"""
    return f'<div class="advanced-card"><h3>{escape(name)} Release Point Profile</h3>{svg}<div class="release-legend">{"".join(keys)}</div></div>'


def render_inning_section(name: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return f'<section id="pitcher-progression"><h2>{escape(name)} Performance by Inning</h2><p>No inning data available.</p></section>'
    max_ops=max(float(r.get('ops_proxy') or 0) for r in rows) or 1
    bars=''.join(f'<div class="trend-bar"><b>{_fmt(r.get("ops_proxy"),3)}</b><i style="height:{max(3,145*float(r.get("ops_proxy") or 0)/max_ops):.1f}px"></i><span>{int(r["inning"])}</span></div>' for r in rows)
    table=''.join(f'<tr><td>{r["inning"]}</td><td>{r["pitches"]}</td><td>{r["pa"]}</td><td>{_fmt(r["avg"],3)}</td><td>{_fmt(r["ops_proxy"],3)}</td><td>{_fmt(r["k_pct"],1,"%")}</td><td>{_fmt(r["bb_pct"],1,"%")}</td><td>{_fmt(r["velo"],1)}</td><td>{_fmt(r["spin"],0)}</td><td>{_fmt(r["whiff_pct"],1,"%")}</td><td>{_fmt(r["hard_hit_pct"],1,"%")}</td></tr>' for r in rows)
    return f"""<section id="pitcher-progression"><h2>{escape(name)} Performance by Inning</h2>
    <p class="advanced-caption">OPS proxy is used because the pitch warehouse does not necessarily contain official earned-run attribution.</p>
    <div class="advanced-grid"><div class="advanced-card"><h3>Opponent OPS Proxy by Inning</h3><div class="trend-bars">{bars}</div><p class="advanced-caption">Lower is better for the pitcher.</p></div>
    <div class="advanced-table-wrap"><table><thead><tr><th>Inn</th><th>Pitches</th><th>PA</th><th>AVG</th><th>OPS proxy</th><th>K%</th><th>BB%</th><th>Velo</th><th>Spin</th><th>Whiff%</th><th>Hard-hit%</th></tr></thead><tbody>{table}</tbody></table></div></div></section>"""


def render_team_overview(name: str, values: dict[str, Any]) -> str:
    season=values.get('season') or {}; rolling=values.get('rolling') or []
    cards=''.join(f'<div class="metric"><span>{label}</span><strong>{value}</strong></div>' for label,value in [
        ('Season AVG',_fmt(season.get('avg'),3)),('Season OBP',_fmt(season.get('obp'),3)),('Season SLG',_fmt(season.get('slg'),3)),('Season OPS',_fmt(season.get('ops'),3)),('Strikeout rate',_fmt(season.get('k_pct'),1,'%')),('Walk rate',_fmt(season.get('bb_pct'),1,'%')),('Hard-hit rate',_fmt(season.get('hard_hit_pct'),1,'%')),('Average exit velocity',_fmt(season.get('avg_ev'),1,' mph'))])
    rows=''.join(f'<tr><td><b>{escape(str(r.get("window")))}</b></td><td>{r.get("games",0)}</td><td>{_fmt(r.get("avg"),3)}</td><td>{_fmt(r.get("obp"),3)}</td><td>{_fmt(r.get("slg"),3)}</td><td>{_fmt(r.get("ops"),3)}</td><td>{_fmt(r.get("k_pct"),1,"%")}</td><td>{_fmt(r.get("bb_pct"),1,"%")}</td><td>{_fmt(r.get("hard_hit_pct"),1,"%")}</td><td>{_fmt(r.get("avg_ev"),1)}</td></tr>' for r in rolling)
    return f"""<section id="opponent-overview"><h2>{escape(name)} Offensive Introduction and Rolling Form</h2><div class="dashboard">{cards}</div>
    <h3>Rolling Averages</h3><div class="advanced-table-wrap"><table><thead><tr><th>Window</th><th>Games</th><th>AVG</th><th>OBP</th><th>SLG</th><th>OPS</th><th>K%</th><th>BB%</th><th>Hard-hit%</th><th>Avg EV</th></tr></thead><tbody>{rows}</tbody></table></div></section>"""


def render_all_sections(*, pitcher_name: str, team_name: str, inning_rows: list[dict[str,Any]], release_rows: list[dict[str,Any]], heatmaps: dict[str,dict[str,Any]], team_values: dict[str,Any]) -> str:
    return ''.join([
        render_team_overview(team_name, team_values),
        render_inning_section(pitcher_name, inning_rows),
        f'<section id="enhanced-heatmaps"><h2>Enhanced Pitch Location Heat Maps</h2><div class="advanced-grid">{render_heatmap("Pitch Frequency",heatmaps["frequency"])}{render_heatmap("Whiff Locations",heatmaps["whiff"])}{render_heatmap("Damage Allowed",heatmaps["damage"])}</div></section>',
        f'<section id="release-points"><h2>Pitch Release Mechanics</h2>{render_release_chart(pitcher_name, release_rows)}</section>',
    ])
