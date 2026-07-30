"""Generate the single interactive HTML scouting report."""
from __future__ import annotations
from collections import Counter, defaultdict
from html import escape
from pathlib import Path
from typing import Any

from reports.scouting_charts import decision_tree_html, scatter_svg

PITCH_NAMES = {
    "FF":"Four-Seam Fastball", "SI":"Sinker", "FC":"Cutter", "FA":"Fastball",
    "CH":"Changeup", "FS":"Splitter", "FO":"Forkball", "SL":"Slider",
    "ST":"Sweeper", "CU":"Curveball", "KC":"Knuckle Curve", "SV":"Slurve",
}


def _value(value: Any, digits: int = 1) -> str:
    if value is None: return "—"
    if isinstance(value, float): return f"{value:.{digits}f}"
    return str(value)


def _sequence_text(sequence: dict[str, Any] | None) -> str:
    if not sequence: return "Not enough information"
    return " → ".join(f"{p.get('pitch_type','')} ({p.get('target_zone','')})" for p in sequence.get("pitches", []))


def _team_strategy(lineup: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter(); scores: dict[str,list[float]]=defaultdict(list); targets: dict[str,Counter[str]]=defaultdict(Counter)
    for hitter in lineup:
        pitch=hitter.get("primary_pitch")
        if pitch:
            counts[pitch]+=1; targets[pitch][str(hitter.get("primary_target") or "zone edge")]+=1
        for option in hitter.get("pitch_options",[]):
            code=str(option.get("pitch_type") or "")
            if code: scores[code].append(float(option.get("score") or 0))
    return [{"code":c,"count":n,"average_score":sum(scores.get(c,[0]))/max(1,len(scores.get(c,[]))),"target":targets[c].most_common(1)[0][0]} for c,n in counts.most_common()]


def _dashboard(report: dict[str,Any]) -> str:
    s=report.get("executive_summary") or {}; p=report.get("projections") or {}
    cards=[
        ("Matchup grade",s.get("matchup_grade","—")),("Highest risk",s.get("highest_risk_hitter","—")),
        ("Lowest risk",s.get("lowest_risk_hitter","—")),("Best team pitch",s.get("most_recommended_pitch","—")),
        ("Pitch to limit",s.get("avoid_pitch","—")),("Best tunnel",s.get("best_tunnel","—")),
        ("Expected strikeouts",p.get("expected_strikeouts","—")),("Expected runs",p.get("expected_runs","—")),
    ]
    return '<div class="dashboard">'+''.join(f'<div class="metric"><span>{escape(str(k))}</span><strong>{escape(str(v))}</strong></div>' for k,v in cards)+'</div>'


def _tracking_section(report: dict[str,Any]) -> str:
    tr=report.get("pitcher_tracking") or {}
    move=scatter_svg(tr.get("movement",[]),"horizontal_break","vertical_break","Pitch movement profile","Horizontal break proxy (in)","Induced vertical break proxy (in)")
    release=scatter_svg(tr.get("release",[]),"release_x","release_z","Release-point consistency","Horizontal release (ft)","Release height (ft)")
    tunnel_rows=''.join(f'<tr><td>{escape(x["pitch_a"])} + {escape(x["pitch_b"])}</td><td>{x["score"]}</td><td>{x["release_distance_ft"]}</td><td>{x["velocity_separation_mph"]}</td><td>{x["movement_separation_in"]}</td><td>{escape(x["explanation"])}</td></tr>' for x in report.get("pitch_tunneling",[])) or '<tr><td colspan="6">Not enough tracking data.</td></tr>'
    return f'''<section id="tracking"><h2>Pitch Shape, Release and Tunneling</h2><p class="note">Movement and tunneling values are transparent tracking-data proxies for within-pitcher comparison; they are not a proprietary trajectory model.</p><div class="chart-grid"><article>{move}</article><article>{release}</article></div><h3>Best tunneling-compatible pairs</h3><table><thead><tr><th>Pair</th><th>Score</th><th>Release distance</th><th>Velocity gap</th><th>Movement gap</th><th>Why</th></tr></thead><tbody>{tunnel_rows}</tbody></table></section>'''


def _opponent_scout(scout: dict[str,Any]) -> str:
    if not scout: return ""
    op=scout.get("pitcher",{})
    ar=''.join(f'<tr><td><b>{escape(str(a.get("pitch_type","")))}</b> — {escape(str(a.get("pitch_name","")))}</td><td>{_value(a.get("usage_rate"))}%</td><td>{_value(a.get("average_velocity"))} mph</td><td>{_value(a.get("whiff_rate"))}%</td><td>{_value(a.get("chase_rate"))}%</td><td>{_value(a.get("strike_rate"))}%</td><td>{_value(a.get("xwoba_allowed"),3)}</td></tr>' for a in scout.get("arsenal",[]))
    strengths=''.join(f'<li>{escape(str(x))}</li>' for x in scout.get("strengths",[])); weaknesses=''.join(f'<li>{escape(str(x))}</li>' for x in scout.get("weaknesses",[])); plan=''.join(f'<li>{escape(str(x))}</li>' for x in scout.get("offensive_attack_plan",[]))
    heat=''.join(f'<article class="heat-card pitch-filter-item" data-pitch="{escape(str(x.get("pitch_type","")))}">{x.get("svg","")}</article>' for x in scout.get("heatmaps",[]))
    buttons='<button class="filter active" data-filter="all">All</button>'+''.join(f'<button class="filter" data-filter="{escape(str(x.get("pitch_type","")))}">{escape(str(x.get("pitch_type","")))}</button>' for x in scout.get("heatmaps",[]))
    counts=''.join(f'<tr><td>{escape(str(r.get("count","")))}</td><td>{r.get("sample",0)}</td><td>{escape(", ".join(f"{k} {v:.1f}%" for k,v in r.get("usage",{}).items()))}</td></tr>' for r in scout.get("usage_by_count",[]))
    transitions=''.join(f'<tr><td>{escape(str(r.get("previous_pitch","")))}</td><td>{escape(str(r.get("next_pitch","")))}</td><td>{_value(r.get("probability"))}%</td><td>{r.get("sample",0)}</td></tr>' for r in scout.get("transitions",[]))
    o=scout.get("overall",{})
    return f'''<section id="opponent"><h2>Opposing Pitcher Scouting — {escape(str(op.get("pitcher_name","Opposing Pitcher")))}</h2><div class="dashboard"><div class="metric"><span>Total pitches</span><strong>{o.get("pitch_count",0)}</strong></div><div class="metric"><span>Whiff</span><strong>{_value(o.get("whiff_rate"))}%</strong></div><div class="metric"><span>Chase</span><strong>{_value(o.get("chase_rate"))}%</strong></div><div class="metric"><span>Zone</span><strong>{_value(o.get("zone_rate"))}%</strong></div></div><h3>Arsenal</h3><table><thead><tr><th>Pitch</th><th>Usage</th><th>Velocity</th><th>Whiff</th><th>Chase</th><th>Strike</th><th>xwOBA</th></tr></thead><tbody>{ar}</tbody></table><div class="two-col"><div><h3>Strengths</h3><ul>{strengths}</ul></div><div><h3>Weaknesses to attack</h3><ul>{weaknesses}</ul></div></div><h3>Offensive plan</h3><ul>{plan}</ul><h3>Interactive pitch-location heat maps</h3><div class="filters">{buttons}</div><div class="heat-grid">{heat or '<p>No location sample available.</p>'}</div><details><summary>Usage by count</summary><table><tbody>{counts}</tbody></table></details><details><summary>Pitch-to-pitch tendencies</summary><table><thead><tr><th>Previous</th><th>Next</th><th>Rate</th><th>Sample</th></tr></thead><tbody>{transitions}</tbody></table></details></section>'''


def _ml_section(ml: dict[str,Any]) -> str:
    rows=''.join(f'<tr><td>{escape(str(r.get("label","")))}</td><td>{escape(str(r.get("top_pitch","—")))}</td><td>{_value(r.get("top_probability"))}%</td></tr>' for r in ml.get("count_tendencies",[]))
    return f'''<section id="ml"><h2>Existing Machine-Learning Pitch Tendencies</h2><p><b>Status:</b> {'Active' if ml.get('available') else 'Not active'} · <b>Training pitches:</b> {ml.get('sample_size',0)} · <b>Accuracy:</b> {_value(ml.get('accuracy'),3)} · <b>Baseline:</b> {_value(ml.get('baseline_accuracy'),3)} · <b>Top-2:</b> {_value(ml.get('top2_accuracy'),3)}</p><p class="note">No new machine-learning model was added in this update. This section preserves the existing optional classifier.</p><table><tbody>{rows or '<tr><td>Run with --use-ml to use the existing model.</td></tr>'}</tbody></table></section>'''


def _hitter_card(h: dict[str,Any]) -> str:
    attack=h.get("attack_plan",{}); conf=h.get("confidence",{}); options=h.get("pitch_options",[])[:6]
    rows=''.join(f'<tr><td>{escape(str(o.get("pitch_type","")))}</td><td>{_value(o.get("score"))}</td><td>{escape(str(o.get("zone","")))}</td><td>{escape(str(o.get("rationale","")))}</td><td>{_value(o.get("expected_whiff_rate"))}%</td><td>{_value(o.get("expected_xwoba"),3)}</td></tr>' for o in options)
    reasons=''.join(f'<li>{escape(str(x))}</li>' for x in conf.get("reasons",[]))
    warning=f'<p class="warning">{escape(str(h.get("sample_warning")))}</p>' if h.get("sample_warning") else ''
    return f'''<article class="hitter-card" data-risk="{escape(str(h.get("risk_level","")).lower())}" data-bats="{escape(str(h.get("bats","")).upper())}"><div class="card-header"><h3>#{h.get("batting_order_slot")} {escape(str(h.get("batter_name","")))}</h3><span class="risk {escape(str(h.get("risk_level","")).lower())}">{escape(str(h.get("risk_level","")))} risk</span></div><div class="hitter-summary"><div><p><b>Primary plan:</b> {escape(str(h.get("primary_pitch_name","")))} to {escape(str(h.get("primary_target","")))}</p><p>{escape(str(h.get("primary_rationale","")))}</p><div class="confidence"><div class="confidence-ring" style="--score:{conf.get('score',0)}"><span>{conf.get('score',0)}%</span></div><div><b>{escape(str(conf.get("label","Low")))} confidence</b><ul>{reasons}</ul></div></div>{warning}</div><div>{h.get("target_zone_svg","")}</div></div><div class="count-grid"><div><b>First pitch</b><span>{escape(str(attack.get("first_pitch","—")))}</span></div><div><b>Ahead</b><span>{escape(str(attack.get("ahead_in_count","—")))}</span></div><div><b>Behind</b><span>{escape(str(attack.get("behind_in_count","—")))}</span></div><div><b>Two strikes</b><span>{escape(str(attack.get("two_strike","—")))}</span></div></div><h4>Count-dependent decision tree</h4>{decision_tree_html(h.get("decision_tree",{}))}<div class="tabs"><button class="tab active" data-tab="overall">Overall hot/cold</button><button class="tab" data-tab="pitch">Primary pitch matchup</button><button class="tab" data-tab="scores">Pitch scores</button></div><div class="tab-panel active" data-panel="overall">{h.get("hot_cold_svg","")}</div><div class="tab-panel" data-panel="pitch">{h.get("primary_pitch_hot_cold_svg","")}</div><div class="tab-panel" data-panel="scores"><table><thead><tr><th>Pitch</th><th>Score</th><th>Target</th><th>Why</th><th>Whiff</th><th>xwOBA</th></tr></thead><tbody>{rows}</tbody></table></div><p><b>Static sequence alternative:</b> {escape(_sequence_text(attack.get("primary_sequence")))}</p><p><b>Avoid:</b> {escape(str(attack.get("avoid","—")))}</p></article>'''


def write_html_report(report: dict[str,Any], output_path: Path) -> Path:
    pitcher=report.get("pitcher",{}); lineup=report.get("lineup",[]); arsenal=report.get("pitcher_arsenal",[]); title=f"{pitcher.get('pitcher_name','Pitcher')} vs. {report.get('opponent_team_name','Opponent')}"
    arsenal_rows=''.join(f'<tr><td><b>{escape(str(p.get("pitch_type","")))}</b> — {escape(PITCH_NAMES.get(str(p.get("pitch_type","")),str(p.get("pitch_type",""))))}</td><td>{_value(p.get("usage_rate"))}%</td><td>{_value(p.get("average_velocity"))} mph</td><td>{_value(p.get("whiff_rate"))}%</td><td>{_value(p.get("chase_rate"))}%</td><td>{_value(p.get("zone_rate"))}%</td><td>{_value(p.get("xwoba_allowed"),3)}</td></tr>' for p in arsenal)
    strategy=_team_strategy(lineup); strategy_rows=''.join(f'<tr><td>{escape(x["code"])} — {escape(PITCH_NAMES.get(x["code"],x["code"]))}</td><td>{x["count"]}</td><td>{x["average_score"]:.1f}</td><td>{escape(x["target"])}</td></tr>' for x in strategy)
    hitters=''.join(_hitter_card(h) for h in lineup)
    html=f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><style>
:root{{--navy:#10243e;--ink:#17212b;--muted:#617184;--line:#dce4eb;--panel:#fff;--bg:#f3f6f9}}*{{box-sizing:border-box}}body{{margin:0;font-family:Inter,Arial,sans-serif;background:var(--bg);color:var(--ink)}}header{{background:linear-gradient(120deg,#0b1d33,#173d67);color:#fff;padding:36px max(24px,calc((100vw - 1240px)/2))}}header h1{{margin:0 0 8px;font-size:34px}}nav{{position:sticky;top:0;z-index:5;background:#fff;border-bottom:1px solid var(--line);padding:10px;text-align:center}}nav a{{margin:0 9px;color:#173d67;text-decoration:none;font-weight:700;font-size:13px}}main{{max-width:1240px;margin:auto;padding:24px}}section,.hitter-card{{background:var(--panel);border-radius:14px;padding:22px;margin-bottom:22px;box-shadow:0 3px 14px #10243e12}}h2{{border-bottom:2px solid #e8eef4;padding-bottom:10px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:9px;border-bottom:1px solid var(--line);text-align:left}}th{{background:#edf2f6}}.dashboard{{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px}}.metric{{background:#eef3f7;border-radius:10px;padding:14px}}.metric span{{display:block;color:var(--muted);font-size:12px}}.metric strong{{font-size:20px}}.two-col,.chart-grid,.hitter-summary{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}.heat-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px}}svg{{max-width:100%;height:auto}}.chart-title{{font-size:15px;font-weight:700;fill:#17212b}}.chart-caption,.heat-caption,.axis-label{{font-size:11px;fill:#617184}}.pitch-point{{fill:#d8e8f5;stroke:#173d67;stroke-width:2}}.point-label{{font-size:10px;font-weight:700;fill:#173d67;pointer-events:none}}.card-header{{display:flex;justify-content:space-between;align-items:center}}.risk{{padding:6px 11px;border-radius:18px;font-size:12px;font-weight:800}}.risk.high{{background:#ffd7d7}}.risk.medium{{background:#fff0bd}}.risk.low{{background:#d9f2df}}.count-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}}.count-grid div{{background:#f0f4f7;border-radius:8px;padding:11px}}.count-grid span{{display:block;margin-top:5px}}.confidence{{display:flex;gap:16px;align-items:center}}.confidence-ring{{--score:0;width:82px;height:82px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(#1d6d4e calc(var(--score)*1%),#e2e8ee 0);position:relative}}.confidence-ring:after{{content:"";position:absolute;width:61px;height:61px;background:white;border-radius:50%}}.confidence-ring span{{z-index:1;font-weight:800}}.decision-tree{{padding:12px;background:#f7f9fb;border-radius:10px}}.tree-node{{display:inline-flex;flex-direction:column;background:#173d67;color:white;border-radius:8px;padding:9px 14px;min-width:135px;text-align:center}}.tree-node span{{font-size:12px;margin-top:4px}}.tree-branches{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:18px;border-top:2px solid #b8c5d1;padding-top:14px}}.tree-branches>div{{display:flex;flex-direction:column;gap:10px;align-items:center}}.branch-label{{font-size:12px;color:var(--muted)}}.tabs,.filters{{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}}button{{border:1px solid #b9c6d2;background:white;padding:8px 12px;border-radius:20px;cursor:pointer}}button.active{{background:#173d67;color:white}}.tab-panel{{display:none}}.tab-panel.active{{display:block}}.warning{{background:#fff4d6;padding:10px;border-radius:8px}}.note{{color:var(--muted)}}.empty-chart{{padding:30px;color:var(--muted);text-align:center}}details{{margin-top:12px}}summary{{cursor:pointer;font-weight:700}}@media(max-width:760px){{.two-col,.chart-grid,.hitter-summary,.count-grid,.tree-branches{{grid-template-columns:1fr}}nav{{display:none}}}}@media print{{nav,.filters,.tabs{{display:none}}section,.hitter-card{{break-inside:avoid;box-shadow:none;border:1px solid #ddd}}.tab-panel{{display:block}}}}
</style></head><body><header><h1>{escape(title)}</h1><p>Interactive HTML game-planning report with deterministic scouting analytics, tracking-data visuals and the existing optional ML tendency model. No Monte Carlo simulation.</p></header><nav><a href="#summary">Summary</a><a href="#arsenal">Arsenal</a><a href="#tracking">Shape & tunneling</a><a href="#opponent">Opponent pitcher</a><a href="#hitters">Hitters</a></nav><main><section id="summary"><h2>Executive Game Summary</h2>{_dashboard(report)}</section><section id="arsenal"><h2>Pitcher Arsenal</h2><table><thead><tr><th>Pitch</th><th>Usage</th><th>Velocity</th><th>Whiff</th><th>Chase</th><th>Zone</th><th>xwOBA</th></tr></thead><tbody>{arsenal_rows}</tbody></table><h3>Team-level strategy</h3><table><thead><tr><th>Pitch</th><th>Primary vs.</th><th>Average score</th><th>Common target</th></tr></thead><tbody>{strategy_rows}</tbody></table></section>{_tracking_section(report)}{_opponent_scout(report.get("opposing_pitcher_scout") or {})}{_ml_section(report.get("machine_learning") or {})}<section id="hitters"><h2>Hitter-by-Hitter Attack Plans</h2><div class="filters"><button class="risk-filter active" data-risk="all">All risks</button><button class="risk-filter" data-risk="high">High</button><button class="risk-filter" data-risk="medium">Medium</button><button class="risk-filter" data-risk="low">Low</button></div></section>{hitters}<section><h2>Method and limitations</h2><p>Recommendations combine the pitcher's arsenal quality, the hitter's historical results by pitch type, sample-size regression, target-location rules, count context and transparent pitch-pair compatibility. Hot/cold maps use expected wOBA when available and a batted-ball damage proxy otherwise.</p><p class="note">{escape(str(report.get("methodology_note","")))}</p></section></main><script>
document.querySelectorAll('.tabs').forEach(tabs=>{{tabs.querySelectorAll('.tab').forEach(btn=>btn.addEventListener('click',()=>{{tabs.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));btn.classList.add('active');const card=tabs.closest('.hitter-card');card.querySelectorAll('.tab-panel').forEach(p=>p.classList.toggle('active',p.dataset.panel===btn.dataset.tab));}}));}});
document.querySelectorAll('.filter[data-filter]').forEach(btn=>btn.addEventListener('click',()=>{{document.querySelectorAll('.filter[data-filter]').forEach(b=>b.classList.remove('active'));btn.classList.add('active');document.querySelectorAll('.pitch-filter-item').forEach(x=>x.style.display=(btn.dataset.filter==='all'||x.dataset.pitch===btn.dataset.filter)?'block':'none');}}));
document.querySelectorAll('.risk-filter').forEach(btn=>btn.addEventListener('click',()=>{{document.querySelectorAll('.risk-filter').forEach(b=>b.classList.remove('active'));btn.classList.add('active');document.querySelectorAll('.hitter-card').forEach(x=>x.style.display=(btn.dataset.risk==='all'||x.dataset.risk===btn.dataset.risk)?'block':'none');}}));
</script></body></html>'''
    output_path.parent.mkdir(parents=True,exist_ok=True); output_path.write_text(html,encoding="utf-8"); return output_path
