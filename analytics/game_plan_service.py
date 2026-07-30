from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

from analytics.game_plan_repository import GamePlanRepository, HistoryFilters
from analytics.ml_pitch_model import train_pitch_model, count_tendencies
from analytics.pitch_outcome_model import train_outcome_model, scenario_scores
from analytics.contextual_analysis import (
    recent_games, home_away_splits, game_state_splits, pitcher_self_comparison,
    bullpen_summary,
)
from analytics.opponent_pitcher_scout import build_opponent_pitcher_scout
from analytics.scouting_visuals import (
    build_decision_tree, executive_summary, movement_and_release_summary,
    recommendation_confidence, tunneling_pairs,
)
from reports.scouting_charts import batter_hot_cold_svg, target_zone_svg
from analytics.pitch_sequence_engine import (
    build_sequences, score_pitch_options, summarize_batter,
    summarize_batter_by_pitch, summarize_direct_matchup,
    summarize_pitcher_arsenal,
)


class GamePlanService:
    def __init__(self, repository: GamePlanRepository | None = None) -> None:
        self.repository = repository or GamePlanRepository()

    def build_game_plan(
        self, pitcher_id: int, game_pk: int | None = None,
        opponent_team_id: int | None = None, pitcher_team_id: int | None = None,
        park_id: int | None = None, lineup_ids: list[int] | None = None,
        season: int | None = None, start_date: str | None = None,
        end_date: str | None = None, opposing_pitcher_id: int | None = None,
        use_ml: bool = False, validate_rosters: bool = True,
    ) -> dict[str, Any]:
        pitcher = self.repository.get_pitcher_metadata(pitcher_id)
        if game_pk is not None:
            context = self.repository.get_game_context(game_pk)
            opponent_id = opponent_team_id or self._infer_opponent_team(
                context, pitcher, game_pk, pitcher_id, pitcher_team_id
            )
        else:
            if opponent_team_id is None:
                raise ValueError("opponent_team_id is required without game_pk")
            opponent_id = int(opponent_team_id)
            context = self._manual_context(opponent_id, pitcher_team_id, park_id, season)

        lineup = (
            self.repository.get_manual_lineup(lineup_ids, opponent_id)
            if lineup_ids else self.repository.get_lineup(int(game_pk), opponent_id)
        )
        if lineup_ids and validate_rosters:
            mismatches = lineup.loc[
                lineup["actual_team_id"].notna()
                & lineup["actual_team_id"].astype(int).ne(int(opponent_id))
            ] if "actual_team_id" in lineup else pd.DataFrame()
            if not mismatches.empty:
                details = ", ".join(
                    f"{row.batter_name} (listed with {row.actual_team_name or 'another team'})"
                    for row in mismatches.itertuples(index=False)
                )
                raise ValueError(
                    f"Lineup validation failed for team_id={opponent_id}: {details}. "
                    "Correct the IDs or run with --skip-roster-validation for historical/transaction edge cases."
                )
        filters = HistoryFilters(season=season, start_date=start_date, end_date=end_date)
        print(f"  Loading pitcher history for {pitcher_id}...", flush=True)
        pitcher_history = self.repository.get_pitcher_history(pitcher_id, filters)
        print(f"  Loaded {len(pitcher_history):,} pitcher pitches.", flush=True)
        if pitcher_history.empty:
            raise RuntimeError(f"No pitch history was found for pitcher_id={pitcher_id}.")

        batter_ids = lineup["player_id"].dropna().astype(int).tolist()
        print(f"  Loading history for {len(batter_ids)} hitters...", flush=True)
        batter_history = self.repository.get_batter_histories(batter_ids, filters)
        print(f"  Loaded {len(batter_history):,} batter pitches.", flush=True)
        print("  Loading direct matchup history...", flush=True)
        direct_history = self.repository.get_direct_matchups(pitcher_id, batter_ids, filters)
        print(f"  Loaded {len(direct_history):,} direct matchup pitches.", flush=True)
        arsenal = summarize_pitcher_arsenal(pitcher_history)
        arsenal_lookup = {str(p.get("pitch_type")): p for p in arsenal}
        pitcher_allowed = summarize_batter(pitcher_history)
        pitcher_tracking = movement_and_release_summary(pitcher_history)
        tunnel_rankings = tunneling_pairs(pitcher_history)

        rows=[]
        for lineup_row in lineup.to_dict("records"):
            print(f"  Analyzing {lineup_row.get('batter_name') or lineup_row.get('player_id')}...", flush=True)
            batter_id=int(lineup_row["player_id"])
            bp=batter_history.loc[batter_history["batter_id"] == batter_id].copy()
            dp=direct_history.loc[direct_history["batter_id"] == batter_id].copy()
            summary=summarize_batter(bp)
            by_pitch=summarize_batter_by_pitch(bp)
            direct=summarize_direct_matchup(dp)
            options=score_pitch_options(arsenal, by_pitch, str(lineup_row.get("bats") or ""))
            sequences=build_sequences(options, maximum=3)
            outcome=self._matchup_probabilities(summary, pitcher_allowed, direct)
            primary=options[0] if options else None
            risk=self._risk_score(summary,direct)
            option_dicts = [o.__dict__ for o in options[:6]]
            primary_batter_sample = int(by_pitch.get(primary.pitch_type, {}).get("pitches") or 0) if primary else 0
            primary_pitcher_sample = int(arsenal_lookup.get(primary.pitch_type, {}).get("pitch_count") or 0) if primary else 0
            confidence = recommendation_confidence(
                primary.__dict__ if primary else None,
                primary_batter_sample,
                primary_pitcher_sample,
            )
            decision_tree = build_decision_tree(option_dicts)
            rows.append({
                "batting_order_slot": int(lineup_row["batting_order_slot"]),
                "batter_id": batter_id,
                "batter_name": lineup_row.get("batter_name") or f"Batter {batter_id}",
                "bats": lineup_row.get("bats") or "",
                "field_position": lineup_row.get("field_position") or lineup_row.get("position_code") or "",
                "history": summary, "direct_matchup": direct, "outcome_probabilities": outcome,
                "risk_score": risk, "risk_level": self._risk_level(risk),
                "primary_pitch": primary.pitch_type if primary else "",
                "primary_pitch_name": self._pitch_name(primary.pitch_type) if primary else "",
                "primary_target": primary.zone if primary else "",
                "primary_rationale": primary.rationale if primary else "Insufficient history",
                "pitch_options": option_dicts,
                "recommended_sequences": sequences,
                "attack_plan": self._attack_plan(options, sequences),
                "decision_tree": decision_tree,
                "confidence": confidence,
                "target_zone_svg": target_zone_svg(primary.zone, primary.pitch_type) if primary else "",
                "hot_cold_svg": batter_hot_cold_svg(bp, f"{lineup_row.get('batter_name') or batter_id} overall hot/cold"),
                "primary_pitch_hot_cold_svg": batter_hot_cold_svg(
                    bp, f"Vs {self._pitch_name(primary.pitch_type)}", primary.pitch_type
                ) if primary else "",
                "sample_warning": self._sample_warning(summary, direct),
                "recent_form": recent_games(bp, 5),
                "game_state_splits": game_state_splits(bp),
            })

        opponent_name = ""
        if "team_name" in lineup and lineup["team_name"].notna().any():
            opponent_name=str(lineup["team_name"].dropna().iloc[0])
        if not opponent_name:
            opponent_name=self.repository.get_team_metadata(opponent_id).get("team_name","")
        projections=self._project_lineup_outcomes(rows)
        summary_dashboard = executive_summary(rows, arsenal, tunnel_rankings)
        ml_result = train_pitch_model(pitcher_history) if use_ml else None
        ml_summary = {
            "enabled": bool(use_ml),
            "available": bool(ml_result and ml_result.available),
            "sample_size": ml_result.sample_size if ml_result else 0,
            "accuracy": ml_result.accuracy if ml_result else None,
            "baseline_accuracy": ml_result.baseline_accuracy if ml_result else None,
            "top2_accuracy": ml_result.top2_accuracy if ml_result else None,
            "note": ml_result.note if ml_result else "Machine learning was not requested.",
            "count_tendencies": count_tendencies(ml_result, "R") if ml_result and ml_result.available else [],
        }
        # Expanded context: recent form, self-comparison, location, game state, peer ranks, bullpen, and outcome ML.
        contextual = {
            "recent_form": recent_games(pitcher_history, 5),
            "self_comparison": pitcher_self_comparison(pitcher_history, 5),
            "home_away": home_away_splits(pitcher_history, pitcher_team_id),
            "game_state": game_state_splits(pitcher_history),
            "location_label": (
                "Home" if pitcher_team_id is not None and context.get("home_team_id") == pitcher_team_id
                else "Away" if pitcher_team_id is not None and context.get("away_team_id") == pitcher_team_id
                else "Not specified"
            ),
        }
        peer_comparison = {
            "similar": [],
            "rankings": [],
            "note": "Similar-player and league-wide peer analysis are disabled. The report uses the selected players' own historical performance.",
        }
        try:
            bullpen_frame = self.repository.get_team_bullpen_history(int(pitcher_team_id), filters) if pitcher_team_id else pd.DataFrame()
            # Remove the selected starter from the relief candidate list.
            if not bullpen_frame.empty:
                bullpen_frame = bullpen_frame[bullpen_frame["pitcher_id"].ne(int(pitcher_id))]
            bullpen = bullpen_summary(bullpen_frame)
        except Exception as exc:
            bullpen = []
        outcome_result = train_outcome_model(pitcher_history) if use_ml else None
        outcome_summary = {
            "enabled": bool(use_ml),
            "available": bool(outcome_result and outcome_result.available),
            "sample_size": outcome_result.sample_size if outcome_result else 0,
            "accuracy": outcome_result.accuracy if outcome_result else None,
            "log_loss": outcome_result.log_loss if outcome_result else None,
            "note": outcome_result.note if outcome_result else "Pitch-outcome ML was not requested.",
            "candidate_scores": scenario_scores(
                outcome_result, [str(x.get("pitch_type")) for x in arsenal],
                str(lineup.iloc[0].get("bats") or "R") if not lineup.empty else "R",
            ) if outcome_result and outcome_result.available else [],
        }

        opposing_scout = None
        if opposing_pitcher_id is not None:
            opposing_meta = self.repository.get_pitcher_metadata(opposing_pitcher_id)
            if validate_rosters and opposing_meta.get("current_team_id") is not None and int(opposing_meta["current_team_id"]) != int(opponent_id):
                raise ValueError(
                    f"Opposing-pitcher validation failed: {opposing_meta.get('pitcher_name')} is listed with "
                    f"{opposing_meta.get('team_name') or 'another team'}, not {opponent_name}. "
                    "Correct --opposing-pitcher-id or use --skip-roster-validation for historical games."
                )
            opposing_history = self.repository.get_pitcher_history(opposing_pitcher_id, filters)
            if not opposing_history.empty:
                opposing_scout = build_opponent_pitcher_scout(opposing_meta, opposing_history)
        return {
            "report_type":"pitcher_lineup_game_plan_v2", "pitcher":pitcher, "game":context,
            "opponent_team_id":opponent_id, "opponent_team_name":opponent_name,
            "lineup":rows, "pitcher_arsenal":arsenal, "projections":projections,
            "executive_summary": summary_dashboard,
            "pitcher_tracking": pitcher_tracking,
            "pitch_tunneling": tunnel_rankings,
            "opposing_pitcher_scout": opposing_scout, "machine_learning": ml_summary,
            "pitch_outcome_model": outcome_summary,
            "contextual_analysis": contextual,
            "peer_comparison": peer_comparison,
            "bullpen": bullpen,
            "methodology_note":"Historical matchup estimates and rule-based pitch recommendations for decision support; not guaranteed outcomes.",
        }

    def _manual_context(self, opponent_id:int, pitcher_team_id:int|None, park_id:int|None, season:int|None)->dict[str,Any]:
        park=self.repository.get_park_metadata(park_id) if park_id else {}
        return {"game_pk":None,"game_date":None,"season":season,"scheduled_start":None,
                "park_id":park_id,"park_name":park.get("park_name","Location not specified"),
                "park_elevation":park.get("park_elevation"),"home_team_id":None,"away_team_id":None,
                "day_night_type":None,"temperature_f":None,"sky_condition":None,
                "wind_speed_mph":None,"wind_direction":None,"pitcher_team_id":pitcher_team_id,
                "opponent_team_id":opponent_id}

    def _infer_opponent_team(self, context, pitcher, game_pk, pitcher_id, pitcher_team_id=None)->int:
        home,away=context.get("home_team_id"),context.get("away_team_id")
        candidate=pitcher_team_id or pitcher.get("current_team_id")
        if candidate is not None:
            candidate=int(candidate)
            if candidate==home:return int(away)
            if candidate==away:return int(home)
        faced=self.repository.get_opponent_team_from_game_pitches(game_pk,pitcher_id)
        if faced is not None:return faced
        raise RuntimeError("Could not infer opponent. Provide --opponent-team-id or --pitcher-team-id.")

    @staticmethod
    def _pitch_name(code:str)->str:
        from analytics.pitch_sequence_engine import PITCH_NAMES
        return PITCH_NAMES.get(code,code)

    @staticmethod
    def _matchup_probabilities(batter:dict[str,Any], pitcher:dict[str,Any], direct:dict[str,Any])->dict[str,float]:
        def rate(source,key,default): return float(source.get(key) if source.get(key) is not None else default)/100.0
        k=.55*rate(batter,"strikeout_rate",22)+.45*rate(pitcher,"strikeout_rate",22)
        bb=.55*rate(batter,"walk_rate",8)+.45*rate(pitcher,"walk_rate",8)
        hit=.55*rate(batter,"hit_rate",23)+.45*rate(pitcher,"hit_rate",23)
        xw=float(batter.get("xwoba") or .320); pxw=float(pitcher.get("xwoba") or .320)
        if int(direct.get("plate_appearances") or 0)>=8 and direct.get("xwoba") is not None:
            blend=.70*(.55*xw+.45*pxw)+.30*float(direct["xwoba"])
        else: blend=.55*xw+.45*pxw
        hr=max(.015,min(.12,.025+(blend-.300)*.22))
        xbh=max(hr,min(.25,hit*(.30+max(0,blend-.300))))
        out={"strikeout":k,"walk":bb,"hit":hit,"extra_base_hit":xbh,"home_run":hr,"estimated_xwoba":blend}
        return {key:round(value*100,1) if key!="estimated_xwoba" else round(value,3) for key,value in out.items()}

    @staticmethod
    def _attack_plan(options,sequences):
        if not options:return {}
        first=options[0]; second=options[1] if len(options)>1 else first
        putaway=max(options,key=lambda o:o.expected_whiff_rate)
        avoid=max(options,key=lambda o:(o.expected_xwoba or .320))
        return {
            "first_pitch":f"{first.pitch_type} — {first.zone}",
            "ahead_in_count":f"{putaway.pitch_type} — {putaway.zone}",
            "behind_in_count":f"{second.pitch_type} — {second.zone}",
            "two_strike":f"{putaway.pitch_type} — {putaway.zone}",
            "avoid":f"Avoid predictable {avoid.pitch_type} in the middle of the zone",
            "primary_sequence":sequences[0] if sequences else None,
            "alternative_sequence":sequences[1] if len(sequences)>1 else None,
        }

    @staticmethod
    def _sample_warning(summary,direct):
        pa=int(summary.get("plate_appearances") or 0); dpa=int(direct.get("plate_appearances") or 0)
        if pa<40:return "Low batter-history sample; recommendations are heavily regressed toward pitcher tendencies."
        if 0<dpa<8:return "Direct matchup history is shown but receives minimal weight because the sample is small."
        return ""

    @staticmethod
    def _risk_score(summary,direct):
        x=float(summary.get("xwoba") or .320); hit=float(summary.get("hit_rate") or 0); bb=float(summary.get("walk_rate") or 0)
        hard=float(summary.get("hard_hit_rate") or 0); k=float(summary.get("strikeout_rate") or 0)
        score=45+(x-.320)*150+hit*.35+bb*.45+hard*.20-k*.25
        if int(direct.get("plate_appearances") or 0)>=8 and direct.get("xwoba") is not None: score+=(float(direct["xwoba"])-.320)*40
        return round(max(0,min(100,score)),1)

    @staticmethod
    def _risk_level(score): return "High" if score>=67 else "Medium" if score>=40 else "Low"

    @staticmethod
    def _project_lineup_outcomes(lineup):
        if not lineup:return {}
        pa=4.0
        def total(key): return sum(float(r["outcome_probabilities"].get(key,0))/100*pa for r in lineup)
        hits=total("hit"); walks=total("walk"); ks=total("strikeout"); hrs=total("home_run"); xbh=total("extra_base_hit")
        runs=.28*hits+.20*walks+.55*xbh+.65*hrs
        lam=max(.1,runs)
        p02=sum(np.exp(-lam)*lam**k/np.math.factorial(k) for k in range(3)) if hasattr(np,"math") else 0
        # Python 3.13-safe Poisson ranges
        import math
        p02=sum(math.exp(-lam)*lam**k/math.factorial(k) for k in range(3))
        p34=sum(math.exp(-lam)*lam**k/math.factorial(k) for k in range(3,5))
        return {"expected_plate_appearances":round(len(lineup)*pa,1),"expected_hits":round(hits,1),
                "expected_walks":round(walks,1),"expected_strikeouts":round(ks,1),"expected_home_runs":round(hrs,1),
                "expected_runs":round(runs,1),"runs_0_to_2_probability":round(p02*100,1),
                "runs_3_to_4_probability":round(p34*100,1),"runs_5_plus_probability":round(max(0,1-p02-p34)*100,1),
                "projection_type":"history_blend_v2"}
