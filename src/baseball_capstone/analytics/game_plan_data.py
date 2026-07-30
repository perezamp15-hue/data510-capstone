"""Build real two-team game-plan data from PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import permutations
from typing import Any

from sqlalchemy import case, func, select

from baseball_capstone.analytics.pitch_baseline import (
    BaselinePrediction,
    predict_next_pitch_frequency,
)
from baseball_capstone.database.engine import session_scope
from baseball_capstone.database.models import Pitch, Player


PITCH_NAMES = {
    "FF": "Four-seam fastball",
    "FA": "Fastball",
    "SI": "Sinker",
    "FT": "Two-seam fastball",
    "FC": "Cutter",
    "SL": "Slider",
    "ST": "Sweeper",
    "SV": "Slurve",
    "CU": "Curveball",
    "KC": "Knuckle curve",
    "CH": "Changeup",
    "FS": "Splitter",
    "FO": "Forkball",
}


@dataclass(frozen=True, slots=True)
class PlayerProfile:
    """Player information required by the HTML report."""

    player_id: int
    name: str
    bats: str | None
    throws: str | None
    position: str | None


@dataclass(frozen=True, slots=True)
class ArsenalPitch:
    """Pitcher arsenal summary."""

    pitch_type: str
    pitch_name: str
    pitch_count: int
    usage: float
    velocity: float | None
    whiff_rate: float
    zone_rate: float


@dataclass(frozen=True, slots=True)
class BatterPitchSplit:
    """Batter result summary against one pitch type."""

    pitch_type: str
    pitch_name: str
    pitches_seen: int
    whiff_rate: float
    strike_rate: float
    in_play_rate: float
    average_exit_velocity: float | None


def safe_float(value: Decimal | float | int | None) -> float | None:
    """Convert database numeric values into normal floats."""
    if value is None:
        return None

    return float(value)


def pitch_name(pitch_type: str | None) -> str:
    """Return a readable pitch name."""
    if not pitch_type:
        return "Unknown"

    return PITCH_NAMES.get(
        pitch_type.upper(),
        pitch_type.upper(),
    )


def get_player_profile(player_id: int) -> PlayerProfile:
    """Load one player from PostgreSQL."""
    with session_scope() as session:
        player = session.get(Player, player_id)

        if player is None:
            raise ValueError(
                f"Player ID {player_id} does not exist in PostgreSQL."
            )

        return PlayerProfile(
            player_id=player.player_id,
            name=player.full_name,
            bats=player.bats,
            throws=player.throws,
            position=player.primary_position,
        )


def get_players(player_ids: list[int]) -> list[PlayerProfile]:
    """Load players while preserving the requested order."""
    if len(player_ids) != len(set(player_ids)):
        raise ValueError("Lineup player IDs must be unique.")

    profiles_by_id = {
        player_id: get_player_profile(player_id)
        for player_id in player_ids
    }

    return [profiles_by_id[player_id] for player_id in player_ids]


def get_pitcher_arsenal(
    *,
    pitcher_id: int,
    start_date: date,
    end_date: date,
    minimum_usage: float = 0.05,
    minimum_pitches: int = 25,
) -> list[ArsenalPitch]:
    """Aggregate the pitcher's observed arsenal."""
    whiff_descriptions = {
        "swinging_strike",
        "swinging_strike_blocked",
        "foul_tip",
    }

    with session_scope() as session:
        total_pitches = session.scalar(
            select(func.count())
            .select_from(Pitch)
            .where(Pitch.pitcher_id == pitcher_id)
            .where(Pitch.game_date.between(start_date, end_date))
            .where(Pitch.pitch_type.is_not(None))
        ) or 0

        if total_pitches == 0:
            return []

        rows = session.execute(
            select(
                Pitch.pitch_type,
                func.count().label("pitch_count"),
                func.avg(Pitch.release_speed).label("velocity"),
                func.avg(
                    case(
                        (
                            Pitch.description.in_(whiff_descriptions),
                            1.0,
                        ),
                        else_=0.0,
                    )
                ).label("whiff_rate"),
                func.avg(
                    case(
                        (
                            Pitch.zone.between(1, 9),
                            1.0,
                        ),
                        else_=0.0,
                    )
                ).label("zone_rate"),
            )
            .where(Pitch.pitcher_id == pitcher_id)
            .where(Pitch.game_date.between(start_date, end_date))
            .where(Pitch.pitch_type.is_not(None))
            .group_by(Pitch.pitch_type)
            .order_by(func.count().desc())
        ).all()

    arsenal: list[ArsenalPitch] = []

    for row in rows:
        usage = row.pitch_count / total_pitches

        if row.pitch_count < minimum_pitches:
            continue

        if usage < minimum_usage:
            continue

        arsenal.append(
            ArsenalPitch(
                pitch_type=row.pitch_type,
                pitch_name=pitch_name(row.pitch_type),
                pitch_count=row.pitch_count,
                usage=usage,
                velocity=safe_float(row.velocity),
                whiff_rate=safe_float(row.whiff_rate) or 0.0,
                zone_rate=safe_float(row.zone_rate) or 0.0,
            )
        )

    return arsenal


def get_batter_pitch_splits(
    *,
    batter_id: int,
    start_date: date,
    end_date: date,
) -> list[BatterPitchSplit]:
    """Aggregate batter results by pitch type."""
    whiff_descriptions = {
        "swinging_strike",
        "swinging_strike_blocked",
        "foul_tip",
    }

    with session_scope() as session:
        rows = session.execute(
            select(
                Pitch.pitch_type,
                func.count().label("pitches_seen"),
                func.avg(
                    case(
                        (
                            Pitch.description.in_(whiff_descriptions),
                            1.0,
                        ),
                        else_=0.0,
                    )
                ).label("whiff_rate"),
                func.avg(
                    case(
                        (
                            Pitch.is_strike.is_(True),
                            1.0,
                        ),
                        else_=0.0,
                    )
                ).label("strike_rate"),
                func.avg(
                    case(
                        (
                            Pitch.is_in_play.is_(True),
                            1.0,
                        ),
                        else_=0.0,
                    )
                ).label("in_play_rate"),
                func.avg(Pitch.launch_speed).label(
                    "average_exit_velocity"
                ),
            )
            .where(Pitch.batter_id == batter_id)
            .where(Pitch.game_date.between(start_date, end_date))
            .where(Pitch.pitch_type.is_not(None))
            .group_by(Pitch.pitch_type)
            .order_by(func.count().desc())
        ).all()

    return [
        BatterPitchSplit(
            pitch_type=row.pitch_type,
            pitch_name=pitch_name(row.pitch_type),
            pitches_seen=row.pitches_seen,
            whiff_rate=safe_float(row.whiff_rate) or 0.0,
            strike_rate=safe_float(row.strike_rate) or 0.0,
            in_play_rate=safe_float(row.in_play_rate) or 0.0,
            average_exit_velocity=safe_float(
                row.average_exit_velocity
            ),
        )
        for row in rows
    ]


def baseline_to_report_predictions(
    prediction: BaselinePrediction,
) -> list[dict[str, Any]]:
    """Convert the baseline result into HTML-ready dictionaries."""
    return [
        {
            "pitch_type": item.pitch_type,
            "pitch_name": pitch_name(item.pitch_type),
            "probability": item.probability,
            "pitch_count": item.pitch_count,
        }
        for item in prediction.probabilities
    ]


def calculate_threat_level(
    batter_splits: list[BatterPitchSplit],
) -> str:
    """Assign an initial transparent threat level."""
    qualified = [
        split
        for split in batter_splits
        if split.pitches_seen >= 20
    ]

    if not qualified:
        return "Medium"

    average_whiff = sum(
        split.whiff_rate for split in qualified
    ) / len(qualified)

    exit_velocities = [
        split.average_exit_velocity
        for split in qualified
        if split.average_exit_velocity is not None
    ]

    average_exit_velocity = (
        sum(exit_velocities) / len(exit_velocities)
        if exit_velocities
        else 88.0
    )

    if average_exit_velocity >= 91.0 and average_whiff <= 0.22:
        return "High"

    if average_exit_velocity < 87.0 or average_whiff >= 0.32:
        return "Low"

    return "Medium"


def score_candidate_pitch(
    arsenal_pitch: ArsenalPitch,
    batter_split: BatterPitchSplit | None,
) -> float:
    """Score one pitch for the rules-based optimizer."""
    batter_whiff = (
        batter_split.whiff_rate
        if batter_split is not None
        else 0.20
    )

    batter_exit_velocity = (
        batter_split.average_exit_velocity
        if batter_split
        and batter_split.average_exit_velocity is not None
        else 88.0
    )

    exit_velocity_penalty = max(
        batter_exit_velocity - 88.0,
        0.0,
    ) * 0.7

    return (
        arsenal_pitch.whiff_rate * 45.0
        + batter_whiff * 35.0
        + arsenal_pitch.zone_rate * 12.0
        + arsenal_pitch.usage * 8.0
        - exit_velocity_penalty
    )


def choose_zone(
    pitch_type: str,
    sequence_position: int,
) -> str:
    """Return a simple pitch-type-appropriate location."""
    pitch_type = pitch_type.upper()

    if pitch_type in {"FF", "FA"}:
        return (
            "Upper third"
            if sequence_position == 1
            else "Above the zone"
        )

    if pitch_type in {"SI", "FT"}:
        return "Lower arm-side edge"

    if pitch_type in {"SL", "ST", "SV"}:
        return "Down and away"

    if pitch_type in {"CU", "KC", "CS"}:
        return "Below the zone"

    if pitch_type in {"CH", "FS", "FO"}:
        return "Below the zone"

    if pitch_type == "FC":
        return "Glove-side edge"

    return "Zone edge"


def build_rules_based_sequence(
    *,
    arsenal: list[ArsenalPitch],
    batter_splits: list[BatterPitchSplit],
) -> dict[str, Any]:
    """Rank realistic three-pitch sequences."""
    if not arsenal:
        return {
            "score": 0.0,
            "expected_woba": 0.330,
            "whiff_probability": 0.20,
            "pitches": [
                {
                    "pitch_name": "No arsenal data",
                    "zone": "Unknown",
                    "reason": "No eligible pitcher sample was available.",
                }
            ]
            * 3,
        }

    split_by_type = {
        split.pitch_type: split
        for split in batter_splits
    }

    ranked_pitches = sorted(
        arsenal,
        key=lambda item: score_candidate_pitch(
            item,
            split_by_type.get(item.pitch_type),
        ),
        reverse=True,
    )

    candidate_pool = ranked_pitches[:4]

    if len(candidate_pool) == 1:
        sequences = [
            (
                candidate_pool[0],
                candidate_pool[0],
                candidate_pool[0],
            )
        ]
    elif len(candidate_pool) == 2:
        sequences = list(
            permutations(
                candidate_pool + candidate_pool[:1],
                3,
            )
        )
    else:
        sequences = list(permutations(candidate_pool, 3))

    best_sequence = None
    best_score = float("-inf")

    for sequence in sequences:
        score = 0.0

        for pitch in sequence:
            score += score_candidate_pitch(
                pitch,
                split_by_type.get(pitch.pitch_type),
            )

        unique_pitch_types = {
            pitch.pitch_type for pitch in sequence
        }

        score += len(unique_pitch_types) * 4.0

        if len(unique_pitch_types) == 1:
            score -= 15.0

        if score > best_score:
            best_score = score
            best_sequence = sequence

    assert best_sequence is not None

    mean_whiff = sum(
        (
            pitch.whiff_rate
            + (
                split_by_type.get(pitch.pitch_type).whiff_rate
                if split_by_type.get(pitch.pitch_type)
                else 0.20
            )
        )
        / 2
        for pitch in best_sequence
    ) / 3

    expected_woba = max(
        0.180,
        min(
            0.420,
            0.340 - mean_whiff * 0.28,
        ),
    )

    pitches = []

    for index, pitch in enumerate(best_sequence, start=1):
        pitches.append(
            {
                "pitch_type": pitch.pitch_type,
                "pitch_name": pitch.pitch_name,
                "zone": choose_zone(
                    pitch.pitch_type,
                    index,
                ),
                "reason": (
                    f"Observed usage {pitch.usage:.1%}, "
                    f"pitcher whiff rate {pitch.whiff_rate:.1%}, "
                    "and matchup-specific batter vulnerability."
                ),
            }
        )

    return {
        "score": round(best_score / 3, 1),
        "expected_woba": expected_woba,
        "whiff_probability": mean_whiff,
        "pitches": pitches,
    }


def build_batter_plan(
    *,
    order: int,
    batter: PlayerProfile,
    opposing_pitcher: PlayerProfile,
    arsenal: list[ArsenalPitch],
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """Build one batter section for the HTML report."""
    baseline = predict_next_pitch_frequency(
        pitcher_id=opposing_pitcher.player_id,
        batter_id=batter.player_id,
        balls=0,
        strikes=0,
        batter_side=batter.bats,
        previous_pitch_type=None,
        start_date=start_date,
        end_date=end_date,
        minimum_sample=15,
        top_n=5,
    )

    predictions = baseline_to_report_predictions(baseline)
    batter_splits = get_batter_pitch_splits(
        batter_id=batter.player_id,
        start_date=start_date,
        end_date=end_date,
    )

    sequence = build_rules_based_sequence(
        arsenal=arsenal,
        batter_splits=batter_splits,
    )

    confidence = min(
        0.95,
        0.45 + min(baseline.sample_size, 300) / 600,
    )

    primary_prediction = (
        predictions[0]["pitch_name"]
        if predictions
        else "No prediction"
    )

    threat_level = calculate_threat_level(batter_splits)

    return {
        "order": order,
        "player_id": batter.player_id,
        "name": batter.name,
        "bats": batter.bats or "Unknown",
        "threat_level": threat_level,
        "historical_sample": baseline.sample_size,
        "confidence": confidence,
        "prediction_source": baseline.fallback_level,
        "predicted_pitches": predictions
        or [
            {
                "pitch_type": "NA",
                "pitch_name": "No prediction",
                "probability": 1.0,
                "pitch_count": 0,
            }
        ],
        "recommended_sequence": sequence,
        "adjustments": [
            (
                "At 0-0, prepare for "
                f"{primary_prediction.lower()} based on the "
                "historical first-pitch distribution."
            ),
            (
                "When ahead in the count, expect the pitcher to "
                "expand toward the edge or below the strike zone."
            ),
            (
                "With two strikes, protect against the final pitch "
                f"in the recommended sequence: "
                f"{sequence['pitches'][-1]['pitch_name']}."
            ),
        ],
        "strategy_summary": (
            f"The frequency baseline uses {baseline.sample_size} "
            f"historical pitches at fallback level "
            f"'{baseline.fallback_level}'. The attack sequence is "
            "limited to the opposing pitcher's qualifying arsenal."
        ),
        "batter_splits": [
            {
                "pitch_name": split.pitch_name,
                "pitches_seen": split.pitches_seen,
                "whiff_rate": split.whiff_rate,
                "strike_rate": split.strike_rate,
                "in_play_rate": split.in_play_rate,
                "average_exit_velocity": (
                    split.average_exit_velocity
                ),
            }
            for split in batter_splits
        ],
    }


def build_team_plan(
    *,
    offense_team: str,
    opposing_pitcher: PlayerProfile,
    lineup: list[PlayerProfile],
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """Build one team's offensive plan."""
    arsenal = get_pitcher_arsenal(
        pitcher_id=opposing_pitcher.player_id,
        start_date=start_date,
        end_date=end_date,
    )

    batter_plans = [
        build_batter_plan(
            order=index,
            batter=batter,
            opposing_pitcher=opposing_pitcher,
            arsenal=arsenal,
            start_date=start_date,
            end_date=end_date,
        )
        for index, batter in enumerate(lineup, start=1)
    ]

    highest_threats = [
        batter["name"]
        for batter in batter_plans
        if batter["threat_level"] == "High"
    ]

    most_used_pitch = (
        arsenal[0].pitch_name
        if arsenal
        else "No qualifying pitch"
    )

    return {
        "offense_team": offense_team,
        "opposing_pitcher": {
            "player_id": opposing_pitcher.player_id,
            "name": opposing_pitcher.name,
            "throws": opposing_pitcher.throws or "Unknown",
        },
        "lineup": batter_plans,
        "pitcher_arsenal": [
            {
                "pitch_type": item.pitch_type,
                "pitch_name": item.pitch_name,
                "pitch_count": item.pitch_count,
                "usage": item.usage,
                "velocity": item.velocity,
                "whiff_rate": item.whiff_rate,
                "zone_rate": item.zone_rate,
            }
            for item in arsenal
        ],
        "team_summary": [
            (
                f"The opposing pitcher primarily relies on "
                f"{most_used_pitch}."
            ),
            (
                "Highest-threat hitters: "
                + (
                    ", ".join(highest_threats)
                    if highest_threats
                    else "none classified as high threat"
                )
                + "."
            ),
            (
                "Predictions currently use the hierarchical "
                "frequency baseline."
            ),
            (
                "Recommendations use a transparent rules-based "
                "three-pitch optimizer."
            ),
        ],
    }