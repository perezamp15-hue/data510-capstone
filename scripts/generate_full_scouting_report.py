"""Generate the complete two-pitcher, all-hitter capstone HTML scouting report."""
from __future__ import annotations
import argparse
import sys
from datetime import date
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baseball_capstone.analytics.full_scouting_report import build_full_report
from baseball_capstone.models.final_strategy import FinalStrategyBundle
from baseball_capstone.reports.html_report import render_full_scouting_report


def ids(value: str) -> list[int]:
    result = [int(item.strip()) for item in value.split(",") if item.strip()]
    if len(result) != 9:
        raise argparse.ArgumentTypeError("Supply exactly nine comma-separated MLB player IDs.")
    return result


def arguments() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate a full lineup scouting report.")
    p.add_argument("--input", type=Path, default=Path("output/model_features_2025_2026.parquet"))
    p.add_argument("--model", type=Path, default=Path("artifacts/models/final_strategy_bundle.joblib"))
    p.add_argument("--output", type=Path, default=Path("output/full_scouting_report.html"))
    p.add_argument("--our-team", required=True); p.add_argument("--opponent-team", required=True)
    p.add_argument("--our-pitcher-id", type=int, required=True); p.add_argument("--opposing-pitcher-id", type=int, required=True)
    p.add_argument("--our-lineup-ids", type=ids, required=True); p.add_argument("--opponent-lineup-ids", type=ids, required=True)
    p.add_argument("--start-date", type=date.fromisoformat, required=True); p.add_argument("--end-date", type=date.fromisoformat, required=True)
    return p.parse_args()


def main() -> int:
    args = arguments()
    bundle = FinalStrategyBundle.load(args.model)
    features = pd.read_parquet(args.input)
    report = build_full_report(our_team=args.our_team, opponent_team=args.opponent_team,
        our_pitcher_id=args.our_pitcher_id, opposing_pitcher_id=args.opposing_pitcher_id,
        our_lineup_ids=args.our_lineup_ids, opponent_lineup_ids=args.opponent_lineup_ids,
        start_date=args.start_date, end_date=args.end_date, bundle=bundle, features=features)
    path = render_full_scouting_report(output_path=args.output, report_data=report)
    print(f"Full scouting report created: {path.resolve()}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
