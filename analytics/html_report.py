"""Convert the pitcher-versus-team analytics dictionary into one HTML report."""
from __future__ import annotations
from collections import Counter, defaultdict
from html import escape
from pathlib import Path
from typing import Any

PITCH_NAMES = {
    "FF":"Four-Seam Fastball", "SI":"Sinker", "FC":"Cutter", "FA":"Fastball",
    "CH":"Changeup", "FS":"Splitter", "FO":"Forkball", "SL":"Slider",
    "ST":"Sweeper", "CU":"Curveball", "KC":"Knuckle Curve", "SV":"Slurve",
}


def _value(value: Any, digits: int = 1) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _sequence_text(sequence: dict[str, Any] | None) -> str:
    if not sequence:
        return "Not enough information"
    return " → ".join(
        f"{p.get('pitch_type', '')} ({p.get('target_zone', '')})"
        for p in sequence.get("pitches", [])
    )


def _team_strategy(lineup: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    scores: dict[str, list[float]] = defaultdict(list)
    targets: dict[str, Counter[str]] = defaultdict(Counter)
    for hitter in lineup:
        pitch = hitter.get("primary_pitch")
        if pitch:
            counts[pitch] += 1
            targets[pitch][str(hitter.get("primary_target") or "zone edge")] += 1
        for option in hitter.get("pitch_options", []):
            code = str(option.get("pitch_type") or "")
            if code:
                scores[code].append(float(option.get("score") or 0))
    rows = []
    for code, count in counts.most_common():
        average = sum(scores.get(code, [0])) / max(1, len(scores.get(code, [])))
        target = targets[code].most_common(1)[0][0]
        rows.append({"code": code, "count": count, "average_score": average, "target": target})
    return rows


def write_html_report(report: dict[str, Any], output_path: Path) -> Path:
    pitcher = report.get("pitcher", {})
    lineup = report.get("lineup", [])
    arsenal = report.get("pitcher_arsenal", [])
    team_strategy = _team_strategy(lineup)
    title = f"{pitcher.get('pitcher_name', 'Pitcher')} vs. {report.get('opponent_team_name', 'Opponent')}"

    arsenal_rows = "".join(
        f"<tr><td><b>{escape(str(p.get('pitch_type','')))}</b> — {escape(PITCH_NAMES.get(str(p.get('pitch_type','')), str(p.get('pitch_type',''))))}</td>"
        f"<td>{_value(p.get('usage_rate'))}%</td><td>{_value(p.get('average_velocity'))} mph</td>"
        f"<td>{_value(p.get('whiff_rate'))}%</td><td>{_value(p.get('chase_rate'))}%</td>"
        f"<td>{_value(p.get('zone_rate'))}%</td><td>{_value(p.get('xwoba_allowed'),3)}</td></tr>"
        for p in arsenal
    )
    strategy_rows = "".join(
        f"<tr><td><b>{escape(r['code'])}</b> — {escape(PITCH_NAMES.get(r['code'], r['code']))}</td>"
        f"<td>{r['count']} hitters</td><td>{r['average_score']:.1f}</td><td>{escape(r['target'])}</td></tr>"
        for r in team_strategy
    ) or '<tr><td colspan="4">No team strategy could be calculated.</td></tr>'

    scout = report.get("opposing_pitcher_scout") or {}
    scout_html = ""
    if scout:
        op = scout.get("pitcher", {})
        op_arsenal_rows = "".join(
            f"<tr><td><b>{escape(str(a.get('pitch_type','')))}</b> — {escape(str(a.get('pitch_name','')))}</td>"
            f"<td>{_value(a.get('usage_rate'))}%</td><td>{_value(a.get('average_velocity'))} mph</td>"
            f"<td>{_value(a.get('whiff_rate'))}%</td><td>{_value(a.get('chase_rate'))}%</td>"
            f"<td>{_value(a.get('strike_rate'))}%</td><td>{_value(a.get('xwoba_allowed'),3)}</td></tr>"
            for a in scout.get("arsenal", [])
        )
        strengths = "".join(f"<li>{escape(str(x))}</li>" for x in scout.get("strengths", []))
        weaknesses = "".join(f"<li>{escape(str(x))}</li>" for x in scout.get("weaknesses", []))
        count_rows = "".join(
            f"<tr><td>{escape(str(r.get('count','')))}</td><td>{r.get('sample',0)}</td>"
            f"<td>{escape(', '.join(f'{k} {v:.1f}%' for k,v in r.get('usage',{}).items()))}</td></tr>"
            for r in scout.get("usage_by_count", [])
        )
        offensive_plan = "".join(f"<li>{escape(str(x))}</li>" for x in scout.get("offensive_attack_plan", []))
        heatmap_cards = "".join(
            f'<article class="heat-card">{item.get("svg", "")}</article>'
            for item in scout.get("heatmaps", [])
        )
        transition_rows = "".join(
            f"<tr><td>{escape(str(r.get('previous_pitch','')))}</td><td>{escape(str(r.get('next_pitch','')))}</td>"
            f"<td>{_value(r.get('probability'))}%</td><td>{r.get('sample',0)}</td></tr>"
            for r in scout.get("transitions", [])
        )
        scout_html = f"""
<section><h2>3. Opposing Pitcher Scouting — {escape(str(op.get('pitcher_name','Opposing Pitcher')))}</h2>
<div class="grid"><div><b>Total pitches</b><br>{scout.get('overall',{}).get('pitch_count',0)}</div>
<div><b>Whiff rate</b><br>{_value(scout.get('overall',{}).get('whiff_rate'))}%</div>
<div><b>Chase rate</b><br>{_value(scout.get('overall',{}).get('chase_rate'))}%</div>
<div><b>Zone rate</b><br>{_value(scout.get('overall',{}).get('zone_rate'))}%</div></div>
<h3>Arsenal</h3><table><thead><tr><th>Pitch</th><th>Usage</th><th>Velocity</th><th>Whiff</th><th>Chase</th><th>Strike</th><th>xwOBA</th></tr></thead><tbody>{op_arsenal_rows}</tbody></table>
<div class="two-col"><div><h3>Strengths</h3><ul>{strengths}</ul></div><div><h3>Weaknesses to Attack</h3><ul>{weaknesses}</ul></div></div>
<h3>How Hitters Should Attack</h3><ul class="attack-list">{offensive_plan}</ul>
<h3>Pitch Location Heat Maps</h3><p class="note">Catcher/umpire view. Darker cells indicate where the opposing pitcher throws that pitch most often. The outlined box is a standardized strike-zone reference.</p>
<div class="heat-grid">{heatmap_cards or '<p>No pitch type met the minimum location sample.</p>'}</div>
<details><summary>Pitch usage by count</summary><table><thead><tr><th>Count</th><th>Sample</th><th>Top usage</th></tr></thead><tbody>{count_rows}</tbody></table></details>
<details><summary>Common pitch-to-pitch transitions</summary><table><thead><tr><th>Previous</th><th>Most common next</th><th>Rate</th><th>Sample</th></tr></thead><tbody>{transition_rows}</tbody></table></details>
</section>"""

    ml = report.get("machine_learning", {})
    ml_rows = "".join(
        f"<tr><td>{escape(str(r.get('label','')))}</td><td>{escape(str(r.get('top_pitch','—')))}</td>"
        f"<td>{_value(r.get('top_probability'))}%</td></tr>"
        for r in ml.get("count_tendencies", [])
    )
    ml_html = f"""
<section><h2>4. Machine-Learning Pitch Tendencies</h2>
<p><b>Status:</b> {'Active' if ml.get('available') else 'Not active'} | <b>Training pitches:</b> {ml.get('sample_size',0)} | <b>Holdout accuracy:</b> {_value(ml.get('accuracy'),3)} | <b>Most-common baseline:</b> {_value(ml.get('baseline_accuracy'),3)} | <b>Top-2 accuracy:</b> {_value(ml.get('top2_accuracy'),3)}</p>
<p class="note">{escape(str(ml.get('note','')))} The model predicts pitch-type probability from count, base state, inning, score, batter side, and the previous pitch. It does not simulate games.</p>
<table><thead><tr><th>Situation</th><th>Most likely pitch</th><th>Probability</th></tr></thead><tbody>{ml_rows or '<tr><td colspan="3">Run with --use-ml to train the model.</td></tr>'}</tbody></table>
</section>"""

    hitter_cards = []
    for hitter in lineup:
        attack = hitter.get("attack_plan", {})
        options = hitter.get("pitch_options", [])[:3]
        options_html = "".join(
            f"<tr><td>{escape(str(o.get('pitch_type','')))}</td><td>{_value(o.get('score'))}</td>"
            f"<td>{escape(str(o.get('zone','')))}</td><td>{escape(str(o.get('rationale','')))}</td></tr>"
            for o in options
        )
        warning = hitter.get("sample_warning")
        warning_html = f'<p class="warning">{escape(str(warning))}</p>' if warning else ""
        hitter_cards.append(f"""
        <article class="card">
          <div class="card-header"><h3>#{hitter.get('batting_order_slot')} {escape(str(hitter.get('batter_name','')))}</h3>
          <span class="risk {str(hitter.get('risk_level','')).lower()}">{escape(str(hitter.get('risk_level','')))} risk</span></div>
          <p><b>Primary plan:</b> {escape(str(hitter.get('primary_pitch_name','')))} to {escape(str(hitter.get('primary_target','')))}</p>
          <p>{escape(str(hitter.get('primary_rationale','')))}</p>
          <div class="grid">
            <div><b>First pitch</b><br>{escape(str(attack.get('first_pitch','—')))}</div>
            <div><b>Ahead</b><br>{escape(str(attack.get('ahead_in_count','—')))}</div>
            <div><b>Behind</b><br>{escape(str(attack.get('behind_in_count','—')))}</div>
            <div><b>Two strikes</b><br>{escape(str(attack.get('two_strike','—')))}</div>
          </div>
          <p><b>Recommended sequence:</b> {escape(_sequence_text(attack.get('primary_sequence')))}</p>
          <p><b>Avoid:</b> {escape(str(attack.get('avoid','—')))}</p>
          {warning_html}
          <details><summary>Top pitch scores</summary>
            <table><thead><tr><th>Pitch</th><th>Score</th><th>Target</th><th>Reason</th></tr></thead><tbody>{options_html}</tbody></table>
          </details>
        </article>""")

    html = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>
body{{font-family:Arial,sans-serif;margin:0;background:#f4f6f8;color:#18212b}} header{{background:#132238;color:white;padding:32px}}
main{{max-width:1200px;margin:auto;padding:24px}} section{{background:white;border-radius:12px;padding:20px;margin-bottom:22px;box-shadow:0 2px 9px #0001}}
table{{border-collapse:collapse;width:100%;font-size:14px}} th,td{{padding:10px;border-bottom:1px solid #dde3e8;text-align:left}} th{{background:#eef2f5}}
.card{{background:white;border-radius:12px;padding:20px;margin-bottom:18px;box-shadow:0 2px 9px #0001}} .card-header{{display:flex;justify-content:space-between;align-items:center}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:14px 0}} .grid div{{background:#f1f4f7;padding:12px;border-radius:8px}}
.risk{{padding:6px 10px;border-radius:20px;font-size:12px;font-weight:bold;background:#dde3e8}} .risk.high{{background:#ffd8d8}} .risk.medium{{background:#fff0bd}} .risk.low{{background:#d9f3df}}
.two-col{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}} .heat-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}} .heat-card{{border:1px solid #dbe3ea;border-radius:10px;padding:8px;background:#fff}} .pitch-heatmap{{width:100%;height:auto;display:block}} .heat-title{{font-size:15px;font-weight:700;fill:#18212b}} .heat-caption,.axis-label{{font-size:11px;fill:#586675}} .attack-list li{{margin-bottom:8px}} .warning{{background:#fff4d6;padding:10px;border-radius:8px}} .note{{color:#586675}} h1,h2,h3{{margin-top:0}}
</style></head><body><header><h1>{escape(title)}</h1><p>Pitcher arsenal and team attack plan — historical analysis with optional machine-learning pitch tendencies; no Monte Carlo simulation.</p></header><main>
<section><h2>1. Pitcher Arsenal</h2><table><thead><tr><th>Pitch</th><th>Usage</th><th>Velocity</th><th>Whiff</th><th>Chase</th><th>Zone</th><th>xwOBA</th></tr></thead><tbody>{arsenal_rows}</tbody></table></section>
<section><h2>2. Team-Level Pitch Strategy</h2><p class="note">This summarizes which primary pitch is recommended most often across the lineup.</p><table><thead><tr><th>Pitch</th><th>Primary vs.</th><th>Average Score</th><th>Common Target</th></tr></thead><tbody>{strategy_rows}</tbody></table></section>
{scout_html}
{ml_html}
<section><h2>5. Hitter-by-Hitter Attack Plans</h2><p class="note">Open “Top pitch scores” under each hitter for more detail.</p></section>
{''.join(hitter_cards)}
<section><h2>6. How the recommendation works</h2><p>The program compares the pitcher’s historical results for each pitch with each hitter’s historical performance against that pitch type. It rewards whiffs and chase, penalizes damaging contact, recommends a target zone based on pitch shape and batter side, and creates pitch sequences that change pitch families and finish with the best put-away option.</p><p class="note">{escape(str(report.get('methodology_note','')))}</p></section>
</main></body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
