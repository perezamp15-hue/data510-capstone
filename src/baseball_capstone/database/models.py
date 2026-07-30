"""Core database models for MLB data collection."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from baseball_capstone.database.base import Base


class Team(Base):
    """MLB team dimension."""

    __tablename__ = "teams"

    team_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    abbreviation: Mapped[str | None] = mapped_column(String(10))
    league_name: Mapped[str | None] = mapped_column(String(50))
    division_name: Mapped[str | None] = mapped_column(String(50))
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    current_park_id: Mapped[int | None] = mapped_column(
        ForeignKey("parks.park_id"),
        nullable=True,
    )

    current_park: Mapped["Park | None"] = relationship(
        foreign_keys=[current_park_id],
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Player(Base):
    """MLB player dimension."""

    __tablename__ = "players"
    __table_args__ = (
        Index("ix_players_full_name", "full_name"),
        Index("ix_players_current_team_id", "current_team_id"),
        Index("ix_players_active", "active"),
    )

    player_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    use_name: Mapped[str | None] = mapped_column(String(100))

    primary_position: Mapped[str | None] = mapped_column(String(10))
    position_name: Mapped[str | None] = mapped_column(String(100))
    position_type: Mapped[str | None] = mapped_column(String(50))

    bats: Mapped[str | None] = mapped_column(String(5))
    throws: Mapped[str | None] = mapped_column(String(5))

    birth_date: Mapped[date | None] = mapped_column(Date)
    mlb_debut_date: Mapped[date | None] = mapped_column(Date)

    height: Mapped[str | None] = mapped_column(String(20))
    weight: Mapped[int | None] = mapped_column(Integer)
    jersey_number: Mapped[str | None] = mapped_column(String(10))

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    roster_status: Mapped[str | None] = mapped_column(String(50))

    current_team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.team_id"),
        nullable=True,
    )

    current_team: Mapped[Team | None] = relationship(
        foreign_keys=[current_team_id],
    )

    last_roster_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Park(Base):
    """MLB park and venue dimension."""

    __tablename__ = "parks"

    park_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    time_zone: Mapped[str | None] = mapped_column(String(100))
    elevation_feet: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Game(Base):
    """One MLB game and its current schedule state."""

    __tablename__ = "games"
    __table_args__ = (
        Index("ix_games_game_date", "game_date"),
        Index("ix_games_season", "season"),
        Index("ix_games_status", "status"),
        Index("ix_games_home_team_id", "home_team_id"),
        Index("ix_games_away_team_id", "away_team_id"),
    )

    game_pk: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    game_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    scheduled_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    season: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    game_type: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str | None] = mapped_column(String(50))
    detailed_status: Mapped[str | None] = mapped_column(String(100))
    abstract_status: Mapped[str | None] = mapped_column(String(50))

    doubleheader: Mapped[str | None] = mapped_column(String(20))
    game_number: Mapped[int | None] = mapped_column(Integer)

    home_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.team_id"),
        nullable=False,
    )

    away_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.team_id"),
        nullable=False,
    )

    park_id: Mapped[int | None] = mapped_column(
        ForeignKey("parks.park_id"),
        nullable=True,
    )

    home_probable_pitcher_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.player_id"),
        nullable=True,
    )

    away_probable_pitcher_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.player_id"),
        nullable=True,
    )

    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)

    inning: Mapped[int | None] = mapped_column(Integer)
    inning_half: Mapped[str | None] = mapped_column(String(20))

    day_night: Mapped[str | None] = mapped_column(String(10))
    temperature_f: Mapped[int | None] = mapped_column(Integer)
    wind_speed_mph: Mapped[int | None] = mapped_column(Integer)
    wind_direction: Mapped[str | None] = mapped_column(String(100))
    weather_condition: Mapped[str | None] = mapped_column(String(100))

    home_team: Mapped[Team] = relationship(
        foreign_keys=[home_team_id],
    )

    away_team: Mapped[Team] = relationship(
        foreign_keys=[away_team_id],
    )

    park: Mapped[Park | None] = relationship(
        foreign_keys=[park_id],
    )

    home_probable_pitcher: Mapped[Player | None] = relationship(
        foreign_keys=[home_probable_pitcher_id],
    )

    away_probable_pitcher: Mapped[Player | None] = relationship(
        foreign_keys=[away_probable_pitcher_id],
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    pitches_collected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    pitch_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    pitches_collected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    pitch_collection_error: Mapped[str | None] = mapped_column(Text)


class Pitch(Base):
    """One pitch from an MLB game live feed."""

    __tablename__ = "pitches"
    __table_args__ = (
        UniqueConstraint(
            "game_pk",
            "at_bat_number",
            "pitch_number",
            name="uq_pitches_game_at_bat_pitch",
        ),
        Index("ix_pitches_game_pk", "game_pk"),
        Index("ix_pitches_game_date", "game_date"),
        Index("ix_pitches_pitcher_id", "pitcher_id"),
        Index("ix_pitches_batter_id", "batter_id"),
        Index("ix_pitches_pitch_type", "pitch_type"),
    )

    pitch_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    game_pk: Mapped[int] = mapped_column(
        ForeignKey("games.game_pk", ondelete="CASCADE"),
        nullable=False,
    )

    game_date: Mapped[date] = mapped_column(Date, nullable=False)

    at_bat_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    plate_appearance_number: Mapped[int | None] = mapped_column(
        Integer
    )

    pitch_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    inning: Mapped[int | None] = mapped_column(Integer)
    inning_half: Mapped[str | None] = mapped_column(String(10))
    outs: Mapped[int | None] = mapped_column(Integer)

    balls: Mapped[int | None] = mapped_column(Integer)
    strikes: Mapped[int | None] = mapped_column(Integer)

    pitcher_id: Mapped[int] = mapped_column(
        ForeignKey("players.player_id"),
        nullable=False,
    )

    batter_id: Mapped[int] = mapped_column(
        ForeignKey("players.player_id"),
        nullable=False,
    )

    pitch_type: Mapped[str | None] = mapped_column(String(10))
    pitch_name: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(100))
    event: Mapped[str | None] = mapped_column(String(100))
    event_type: Mapped[str | None] = mapped_column(String(100))

    is_pitch: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    is_ball: Mapped[bool | None] = mapped_column(Boolean)
    is_strike: Mapped[bool | None] = mapped_column(Boolean)
    is_in_play: Mapped[bool | None] = mapped_column(Boolean)

    release_speed: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 3)
    )
    effective_speed: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 3)
    )
    release_spin_rate: Mapped[int | None] = mapped_column(Integer)
    release_extension: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 3)
    )

    release_pos_x: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 4)
    )
    release_pos_y: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 4)
    )
    release_pos_z: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 4)
    )

    plate_x: Mapped[Decimal | None] = mapped_column(Numeric(9, 4))
    plate_z: Mapped[Decimal | None] = mapped_column(Numeric(9, 4))

    strike_zone_top: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 4)
    )
    strike_zone_bottom: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 4)
    )

    pfx_x: Mapped[Decimal | None] = mapped_column(Numeric(9, 4))
    pfx_z: Mapped[Decimal | None] = mapped_column(Numeric(9, 4))

    launch_speed: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 3)
    )
    launch_angle: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 3)
    )
    hit_distance: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 3)
    )

    hit_location: Mapped[int | None] = mapped_column(Integer)
    trajectory: Mapped[str | None] = mapped_column(String(50))
    hardness: Mapped[str | None] = mapped_column(String(50))

    estimated_batting_average: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 6)
    )
    estimated_woba: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 6)
    )
    estimated_slugging: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 6)
    )

    zone: Mapped[int | None] = mapped_column(Integer)
    type_code: Mapped[str | None] = mapped_column(String(5))

    runner_on_first: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    runner_on_second: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    runner_on_third: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)

    raw_payload: Mapped[str | None] = mapped_column(Text)

    game: Mapped[Game] = relationship()
    pitcher: Mapped[Player] = relationship(
        foreign_keys=[pitcher_id]
    )
    batter: Mapped[Player] = relationship(
        foreign_keys=[batter_id]
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PitchSequenceFeature(Base):
    """One training row for next-pitch prediction."""

    __tablename__ = "pitch_sequence_features"
    __table_args__ = (
        UniqueConstraint(
            "game_pk",
            "at_bat_number",
            "pitch_number",
            name="uq_pitch_sequence_game_at_bat_pitch",
        ),
        Index(
            "ix_pitch_sequence_game_date",
            "game_date",
        ),
        Index(
            "ix_pitch_sequence_season",
            "season",
        ),
        Index(
            "ix_pitch_sequence_pitcher_id",
            "pitcher_id",
        ),
        Index(
            "ix_pitch_sequence_batter_id",
            "batter_id",
        ),
        Index(
            "ix_pitch_sequence_count",
            "balls_before_pitch",
            "strikes_before_pitch",
        ),
        Index(
            "ix_pitch_sequence_target_pitch_type",
            "target_pitch_type",
        ),
    )

    feature_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    game_pk: Mapped[int] = mapped_column(
        ForeignKey("games.game_pk", ondelete="CASCADE"),
        nullable=False,
    )

    game_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    season: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    at_bat_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    pitch_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    pitcher_id: Mapped[int] = mapped_column(
        ForeignKey("players.player_id"),
        nullable=False,
    )

    batter_id: Mapped[int] = mapped_column(
        ForeignKey("players.player_id"),
        nullable=False,
    )

    pitcher_hand: Mapped[str | None] = mapped_column(
        String(5),
    )

    batter_side: Mapped[str | None] = mapped_column(
        String(5),
    )

    inning: Mapped[int | None] = mapped_column(Integer)

    inning_half: Mapped[str | None] = mapped_column(
        String(10),
    )

    outs_before_pitch: Mapped[int | None] = mapped_column(
        Integer,
    )

    balls_before_pitch: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    strikes_before_pitch: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    previous_pitch_type: Mapped[str | None] = mapped_column(
        String(10),
    )

    previous_pitch_zone: Mapped[str | None] = mapped_column(
        String(30),
    )

    previous_pitch_result: Mapped[str | None] = mapped_column(
        String(100),
    )

    second_previous_pitch_type: Mapped[str | None] = mapped_column(
        String(10),
    )

    second_previous_pitch_zone: Mapped[str | None] = mapped_column(
        String(30),
    )

    third_previous_pitch_type: Mapped[str | None] = mapped_column(
        String(10),
    )

    runner_on_first: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    runner_on_second: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    runner_on_third: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    target_pitch_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    target_pitch_name: Mapped[str | None] = mapped_column(
        String(100),
    )

    target_pitch_zone: Mapped[str | None] = mapped_column(
        String(30),
    )

    target_plate_x: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 4),
    )

    target_plate_z: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 4),
    )

    target_release_speed: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 3),
    )

    target_description: Mapped[str | None] = mapped_column(
        String(100),
    )

    target_is_ball: Mapped[bool | None] = mapped_column(
        Boolean,
    )

    target_is_strike: Mapped[bool | None] = mapped_column(
        Boolean,
    )

    target_is_in_play: Mapped[bool | None] = mapped_column(
        Boolean,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

class CollectionRun(Base):
    """Tracks each collector execution."""

    __tablename__ = "collection_runs"

    collection_run_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    collector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="running",
    )

    requested_start_date: Mapped[date | None] = mapped_column(Date)
    requested_end_date: Mapped[date | None] = mapped_column(Date)

    records_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_inserted: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    records_updated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    records_rejected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    error_message: Mapped[str | None] = mapped_column(Text)