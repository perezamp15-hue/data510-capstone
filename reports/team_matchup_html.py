"""Render a combined offensive-and-defensive team matchup HTML report."""
from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

from reports.html_report import PITCH_NAMES, _value, _sequence_text
from reports.scouting_charts import decision_tree_html, scatter_svg


def _arsenal_table(report: dict[str, Any]) -> str:
    rows = "".join(
        f"<tr><td><b>{escape(str(p.get('pitch_type','')))}</b> — "
        f"{escape(PITCH_NAMES.get(str(p.get('pitch_type','')), str(p.get('pitch_type',''))))}</td>"
        f"<td>{_value(p.get('usage_rate'))}%</td>"
        f"<td>{_value(p.get('average_velocity'))} mph</td>"
        f"<td>{_value(p.get('whiff_rate'))}%</td>"
        f"<td>{_value(p.get('chase_rate'))}%</td>"
        f"<td>{_value(p.get('zone_rate'))}%</td>"
        f"<td>{_value(p.get('xwoba_allowed'),3)}</td></tr>"
        for p in report.get("pitcher_arsenal", [])
    )
    return (
        "<table><thead><tr><th>Pitch</th><th>Usage</th><th>Velocity</th>"
        "<th>Whiff</th><th>Chase</th><th>Zone</th><th>xwOBA</th></tr></thead>"
        f"<tbody>{rows or '<tr><td colspan=7>No arsenal sample.</td></tr>'}</tbody></table>"
    )


def _tracking(report: dict[str, Any], prefix: str) -> str:
    tracking = report.get("pitcher_tracking") or {}
    movement = scatter_svg(
        tracking.get("movement", []),
        "horizontal_break",
        "vertical_break",
        "Pitch movement profile",
        "Horizontal break proxy (in)",
        "Induced vertical break proxy (in)",
    )
    release = scatter_svg(
        tracking.get("release", []),
        "release_x",
        "release_z",
        "Release-point consistency",
        "Horizontal release (ft)",
        "Release height (ft)",
    )
    tunnels = "".join(
        f"<tr><td>{escape(str(x.get('pitch_a','')))} + {escape(str(x.get('pitch_b','')))}</td>"
        f"<td>{_value(x.get('score'))}</td><td>{_value(x.get('release_distance_ft'))}</td>"
        f"<td>{_value(x.get('velocity_separation_mph'))}</td>"
        f"<td>{_value(x.get('movement_separation_in'))}</td>"
        f"<td>{escape(str(x.get('explanation','')))}</td></tr>"
        for x in report.get("pitch_tunneling", [])[:8]
    )
    return f"""
    <div class="chart-grid"><article>{movement}</article><article>{release}</article></div>
    <details><summary>Pitch tunneling pairs</summary>
    <table><thead><tr><th>Pair</th><th>Score</th><th>Release gap</th><th>Velocity gap</th><th>Movement gap</th><th>Why</th></tr></thead>
    <tbody>{tunnels or '<tr><td colspan=6>Not enough tracking data.</td></tr>'}</tbody></table></details>
    """


def _ml(report: dict[str, Any], title: str) -> str:
    ml = report.get("machine_learning") or {}
    rows = "".join(
        f"<tr><td>{escape(str(row.get('label','')))}</td>"
        f"<td>{escape(str(row.get('top_pitch','—')))}</td>"
        f"<td>{_value(row.get('top_probability'))}%</td></tr>"
        for row in ml.get("count_tendencies", [])
    )
    return f"""
    <details class="ml-box"><summary>{escape(title)}</summary>
      <p><b>Status:</b> {'Active' if ml.get('available') else 'Not active'} ·
      <b>Training pitches:</b> {ml.get('sample_size',0)} ·
      <b>Accuracy:</b> {_value(ml.get('accuracy'),3)} ·
      <b>Baseline:</b> {_value(ml.get('baseline_accuracy'),3)} ·
      <b>Top-2:</b> {_value(ml.get('top2_accuracy'),3)}</p>
      <table><tbody>{rows or '<tr><td>No tendency output available.</td></tr>'}</tbody></table>
    </details>
    """


def _offensive_approach(hitter: dict[str, Any], opposing_pitcher_name: str) -> str:
    pitch = hitter.get("primary_pitch_name") or hitter.get("primary_pitch") or "best pitch"
    target = str(hitter.get("primary_target") or "the zone edge")
    outside_words = ("below", "away", "outside", "above")
    if any(word in target.lower() for word in outside_words):
        discipline = f"Do not expand early toward {target}; force this pitch into the strike zone."
    else:
        discipline = f"Be ready when {pitch} leaks into {target}."
    return (
        f"{opposing_pitcher_name}'s strongest matchup option is {pitch} toward {target}. "
        f"{discipline} Use the hot/cold maps to identify the hitter's preferred damage zone."
    )


def _offensive_card(hitter: dict[str, Any], opposing_pitcher_name: str) -> str:
    confidence = hitter.get("confidence") or {}
    options = hitter.get("pitch_options", [])[:5]
    rows = "".join(
        f"<tr><td>{escape(str(o.get('pitch_type','')))}</td>"
        f"<td>{_value(o.get('score'))}</td><td>{escape(str(o.get('zone','')))}</td>"
        f"<td>{_value(o.get('expected_whiff_rate'))}%</td>"
        f"<td>{_value(o.get('expected_xwoba'),3)}</td></tr>"
        for o in options
    )
    return f"""
    <article class="hitter-card offensive-card" data-risk="{escape(str(hitter.get('risk_level','')).lower())}">
      <div class="card-header"><h3>#{hitter.get('batting_order_slot')} {escape(str(hitter.get('batter_name','')))}</h3>
      <span class="risk {escape(str(hitter.get('risk_level','')).lower())}">{escape(str(hitter.get('risk_level','')))} matchup</span></div>
      <div class="hitter-summary">
        <div><h4>What to expect from the opposing pitcher</h4>
        <p>{escape(_offensive_approach(hitter, opposing_pitcher_name))}</p>
        <p><b>Matchup-confidence sample:</b> {confidence.get('score',0)}% — {escape(str(confidence.get('label','Low')))}</p></div>
        <div>{hitter.get('target_zone_svg','')}</div>
      </div>
      <div class="tabs"><button class="tab active" data-tab="overall">Overall hot/cold</button>
      <button class="tab" data-tab="pitch">Against expected pitch</button>
      <button class="tab" data-tab="scores">Pitch threats</button></div>
      <div class="tab-panel active" data-panel="overall">{hitter.get('hot_cold_svg','')}</div>
      <div class="tab-panel" data-panel="pitch">{hitter.get('primary_pitch_hot_cold_svg','')}</div>
      <div class="tab-panel" data-panel="scores"><table><thead><tr><th>Pitch</th><th>Threat score</th><th>Likely target</th><th>Whiff</th><th>xwOBA</th></tr></thead><tbody>{rows}</tbody></table></div>
    </article>
    """


def _defensive_card(hitter: dict[str, Any]) -> str:
    attack = hitter.get("attack_plan") or {}
    confidence = hitter.get("confidence") or {}
    options = hitter.get("pitch_options", [])[:6]
    rows = "".join(
        f"<tr><td>{escape(str(o.get('pitch_type','')))}</td><td>{_value(o.get('score'))}</td>"
        f"<td>{escape(str(o.get('zone','')))}</td><td>{escape(str(o.get('rationale','')))}</td>"
        f"<td>{_value(o.get('expected_whiff_rate'))}%</td><td>{_value(o.get('expected_xwoba'),3)}</td></tr>"
        for o in options
    )
    reasons = "".join(f"<li>{escape(str(x))}</li>" for x in confidence.get("reasons", []))
    warning = (
        f"<p class='warning'>{escape(str(hitter.get('sample_warning')))}</p>"
        if hitter.get("sample_warning") else ""
    )
    return f"""
    <article class="hitter-card defensive-card" data-risk="{escape(str(hitter.get('risk_level','')).lower())}">
      <div class="card-header"><h3>#{hitter.get('batting_order_slot')} {escape(str(hitter.get('batter_name','')))}</h3>
      <span class="risk {escape(str(hitter.get('risk_level','')).lower())}">{escape(str(hitter.get('risk_level','')))} risk</span></div>
      <div class="hitter-summary"><div>
        <p><b>Primary plan:</b> {escape(str(hitter.get('primary_pitch_name','')))} to {escape(str(hitter.get('primary_target','')))}</p>
        <p>{escape(str(hitter.get('primary_rationale','')))}</p>
        <p><b>Confidence:</b> {confidence.get('score',0)}% — {escape(str(confidence.get('label','Low')))}</p>
        <ul>{reasons}</ul>{warning}</div><div>{hitter.get('target_zone_svg','')}</div></div>
      <div class="count-grid"><div><b>First pitch</b><span>{escape(str(attack.get('first_pitch','—')))}</span></div>
      <div><b>Ahead</b><span>{escape(str(attack.get('ahead_in_count','—')))}</span></div>
      <div><b>Behind</b><span>{escape(str(attack.get('behind_in_count','—')))}</span></div>
      <div><b>Two strikes</b><span>{escape(str(attack.get('two_strike','—')))}</span></div></div>
      <h4>Count-dependent decision tree</h4>{decision_tree_html(hitter.get('decision_tree',{}))}
      <div class="tabs"><button class="tab active" data-tab="overall">Overall hot/cold</button>
      <button class="tab" data-tab="pitch">Primary pitch matchup</button><button class="tab" data-tab="scores">Pitch scores</button></div>
      <div class="tab-panel active" data-panel="overall">{hitter.get('hot_cold_svg','')}</div>
      <div class="tab-panel" data-panel="pitch">{hitter.get('primary_pitch_hot_cold_svg','')}</div>
      <div class="tab-panel" data-panel="scores"><table><thead><tr><th>Pitch</th><th>Score</th><th>Target</th><th>Why</th><th>Whiff</th><th>xwOBA</th></tr></thead><tbody>{rows}</tbody></table></div>
      <p><b>Static sequence reference:</b> {escape(_sequence_text(attack.get('primary_sequence')))}</p>
      <p><b>Avoid:</b> {escape(str(attack.get('avoid','—')))}</p>
    </article>
    """


def _summary(matchup: dict[str, Any]) -> str:
    offense = matchup["offensive_report"]
    defense = matchup["defensive_report"]
    op = offense.get("executive_summary") or {}
    dp = defense.get("executive_summary") or {}
    projections = defense.get("projections") or {}
    cards = [
        ("Our pitcher", matchup["our_pitcher"].get("full_name", "—")),
        ("Opposing pitcher", matchup["opposing_pitcher"].get("full_name", "—")),
        ("Defensive grade", dp.get("matchup_grade", "—")),
        ("Highest-risk opponent", dp.get("highest_risk_hitter", "—")),
        (f"Best {matchup["our_pitcher"].get("full_name", "our pitcher")} pitch", dp.get("most_recommended_pitch", "—")),
        ("Best tunnel", dp.get("best_tunnel", "—")),
        ("Expected strikeouts", projections.get("expected_strikeouts", "—")),
        (f"{matchup["opposing_pitcher"].get("full_name", "Opposing pitcher")} danger pitch", op.get("most_recommended_pitch", "—")),
    ]
    return '<div class="dashboard">' + ''.join(
        f'<div class="metric"><span>{escape(str(label))}</span><strong>{escape(str(value))}</strong></div>'
        for label, value in cards
    ) + '</div>'


def write_team_matchup_html(matchup: dict[str, Any], output_path: Path) -> Path:
    our_team = str(matchup["our_team"].get("team_name", "Our Team"))
    opponent_team = str(matchup["opponent_team"].get("team_name", "Opponent"))
    our_pitcher = str(matchup["our_pitcher"].get("full_name", "Our Pitcher"))
    opposing_pitcher = str(matchup["opposing_pitcher"].get("full_name", "Opposing Pitcher"))
    offense = matchup["offensive_report"]
    defense = matchup["defensive_report"]
    title = f"{our_team} vs. {opponent_team} Game Plan"

    offense_cards = "".join(_offensive_card(h, opposing_pitcher) for h in offense.get("lineup", []))
    defense_cards = "".join(_defensive_card(h) for h in defense.get("lineup", []))

    html = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>
:root{{--navy:#10243e;--blue:#173d67;--ink:#17212b;--muted:#617184;--line:#dce4eb;--panel:#fff;--bg:#f3f6f9;--offense:#7b3f00;--defense:#173d67}}*{{box-sizing:border-box}}body{{margin:0;font-family:Inter,Arial,sans-serif;background:var(--bg);color:var(--ink)}}header{{background:linear-gradient(120deg,#081a2f,#174b78);color:#fff;padding:38px max(24px,calc((100vw - 1260px)/2))}}header h1{{margin:0 0 8px;font-size:36px}}nav{{position:sticky;top:0;z-index:10;background:#fff;border-bottom:1px solid var(--line);padding:11px;text-align:center}}nav a{{margin:0 10px;color:var(--blue);text-decoration:none;font-weight:800;font-size:13px}}main{{max-width:1260px;margin:auto;padding:24px}}section,.hitter-card{{background:var(--panel);border-radius:14px;padding:22px;margin-bottom:22px;box-shadow:0 3px 14px #10243e12}}.section-title{{display:flex;align-items:center;gap:12px}}.badge{{padding:7px 11px;border-radius:18px;color:#fff;font-size:12px;font-weight:800}}.badge.offense{{background:var(--offense)}}.badge.defense{{background:var(--defense)}}h2{{border-bottom:2px solid #e8eef4;padding-bottom:10px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:9px;border-bottom:1px solid var(--line);text-align:left}}th{{background:#edf2f6}}.dashboard{{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:12px}}.metric{{background:#eef3f7;border-radius:10px;padding:14px}}.metric span{{display:block;color:var(--muted);font-size:12px}}.metric strong{{font-size:19px}}.chart-grid,.hitter-summary{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}svg{{max-width:100%;height:auto}}.hot-cold{{display:block;width:min(100%,250px);margin:0 auto}}.tab-panel[data-panel="overall"],.tab-panel[data-panel="pitch"]{{text-align:center}}.chart-title{{font-size:15px;font-weight:700;fill:#17212b}}.chart-caption,.heat-caption,.axis-label{{font-size:11px;fill:#617184}}.pitch-point{{fill:#d8e8f5;stroke:#173d67;stroke-width:2}}.point-label{{font-size:10px;font-weight:700;fill:#173d67;pointer-events:none}}.card-header{{display:flex;justify-content:space-between;align-items:center}}.risk{{padding:6px 11px;border-radius:18px;font-size:12px;font-weight:800}}.risk.high{{background:#ffd7d7}}.risk.medium{{background:#fff0bd}}.risk.low{{background:#d9f2df}}.count-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}}.count-grid div{{background:#f0f4f7;border-radius:8px;padding:11px}}.count-grid span{{display:block;margin-top:5px}}.decision-tree{{padding:12px;background:#f7f9fb;border-radius:10px}}.tree-node{{display:inline-flex;flex-direction:column;background:#173d67;color:#fff;border-radius:8px;padding:9px 14px;min-width:135px;text-align:center}}.tree-node span{{font-size:12px;margin-top:4px}}.tree-branches{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:18px;border-top:2px solid #b8c5d1;padding-top:14px}}.tree-branches>div{{display:flex;flex-direction:column;gap:10px;align-items:center}}.branch-label{{font-size:12px;color:var(--muted)}}.tabs{{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}}button{{border:1px solid #b9c6d2;background:#fff;padding:8px 12px;border-radius:20px;cursor:pointer}}button.active{{background:#173d67;color:#fff}}.tab-panel{{display:none}}.tab-panel.active{{display:block}}.warning{{background:#fff4d6;padding:10px;border-radius:8px}}.note{{color:var(--muted)}}details{{margin-top:13px}}summary{{cursor:pointer;font-weight:800}}.offensive-card{{border-left:5px solid var(--offense)}}.defensive-card{{border-left:5px solid var(--defense)}}@media(max-width:760px){{.chart-grid,.hitter-summary,.count-grid,.tree-branches{{grid-template-columns:1fr}}nav{{display:none}}}}
</style></head><body>
<header><h1>{escape(title)}</h1><p><b>Offense:</b> {escape(our_team)} hitters vs. {escape(opposing_pitcher)} · <b>Defense:</b> {escape(our_pitcher)} vs. {escape(opponent_team)} hitters</p><p>Interactive HTML-only report.</p></header>
<nav><a href="#summary">Summary</a><a href="#offense">Offense vs. {escape(opposing_pitcher)}</a><a href="#defense">{escape(our_pitcher)} plan</a><a href="#method">Method</a></nav>
<main><section id="summary"><h2>Combined Game Summary</h2>{_summary(matchup)}</section>
<section id="offense"><div class="section-title"><span class="badge offense">OFFENSIVE PLAN</span><h2>{escape(our_team)} Hitters vs. {escape(opposing_pitcher)}</h2></div>
<p>This side treats {escape(opposing_pitcher)} as the pitcher we are facing. The pitch rankings show the opposing pitcher’s strongest historical matchup options against each hitter, helping the offense anticipate the pitch type and target location most likely to create trouble.</p>
<h3>{escape(opposing_pitcher)} Arsenal</h3>{_arsenal_table(offense)}
<h3>Movement, release and tunneling</h3>{_tracking(offense,'offense')}{_ml(offense, f'{opposing_pitcher} pitch tendencies by count')}</section>
{offense_cards}
<section id="defense"><div class="section-title"><span class="badge defense">DEFENSIVE PLAN</span><h2>{escape(our_pitcher)} vs. {escape(opponent_team)} Hitters</h2></div>
<p>This side recommends what our pitcher should throw, where it should be located, how to change plans by count, and which pitch pairs tunnel well.</p>
<h3>{escape(our_pitcher)} Arsenal</h3>{_arsenal_table(defense)}
<h3>Movement, release and tunneling</h3>{_tracking(defense,'defense')}{_ml(defense, f'{our_pitcher} pitch tendencies by count')}</section>
{defense_cards}
<section id="method"><h2>Method and limitations</h2><p>The same deterministic matchup engine is run twice. First, it models the opposing pitcher against our batting order so hitters can anticipate his strongest matchup choices. Second, it models our pitcher against the opposing batting order to create the defensive pitch plan. Recommendations combine arsenal performance, hitter history by pitch type, count context, target-location rules, sample-size regression, hot/cold zones, movement, release consistency and tunneling compatibility.</p><p class="note">Historical decision support only; recommendations are not guaranteed outcomes. Preset lineups are editable examples and should be replaced with the confirmed batting orders for a specific game.</p></section></main>
<script>document.querySelectorAll('.tabs').forEach(tabs=>{{tabs.querySelectorAll('.tab').forEach(btn=>btn.addEventListener('click',()=>{{tabs.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));btn.classList.add('active');const card=tabs.closest('.hitter-card');card.querySelectorAll('.tab-panel').forEach(p=>p.classList.toggle('active',p.dataset.panel===btn.dataset.tab));}}));}});</script>
</body></html>'''
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
