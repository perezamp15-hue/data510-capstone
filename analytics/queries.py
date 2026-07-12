# SQL Queries to Get the Information Needed for the Project

# DATABASE INVENTORY
TABLE_COUNTS_QUERY = """
SELECT 'games' AS table_name, COUNT(*)::bigint AS row_count
FROM public.games

UNION ALL

SELECT 'parks', COUNT(*)::bigint
FROM public.parks

UNION ALL

SELECT 'players', COUNT(*)::bigint
FROM public.players

UNION ALL

SELECT 'starting_lineups', COUNT(*)::bigint
FROM public.starting_lineups

UNION ALL

SELECT 'statcast_pitches', COUNT(*)::bigint
FROM public.statcast_pitches

UNION ALL

SELECT 'teams', COUNT(*)::bigint
FROM public.teams

UNION ALL

SELECT 'transactions', COUNT(*)::bigint
FROM public.transactions

UNION ALL

SELECT 'umpires', COUNT(*)::bigint
FROM public.umpires

ORDER BY table_name
"""


AVAILABLE_SEASONS_QUERY = """
SELECT DISTINCT season
FROM public.games
WHERE season IS NOT NULL
ORDER BY season DESC
"""


LATEST_GAME_DATE_QUERY = """
SELECT MAX(game_date)
FROM public.games
"""

# PLAYERS
PLAYER_BY_ID_QUERY = """
SELECT
    p.player_id,
    p.full_name,
    p.current_team_id,
    t.abbreviation AS current_team_abbreviation,
    t.team_name AS current_team_name,
    p.position_code,
    p.bats,
    p.throws,
    p.birth_date,
    p.height,
    p.weight,
    p.mlb_debut,
    p.is_active
FROM public.players AS p
LEFT JOIN public.teams AS t
    ON t.team_id = p.current_team_id
WHERE p.player_id = :player_id
"""

SEARCH_PLAYERS_QUERY = """
SELECT
    p.player_id,
    p.full_name,
    p.current_team_id,
    t.abbreviation AS team_abbreviation,
    t.team_name,
    p.position_code,
    p.bats,
    p.throws,
    p.is_active
FROM public.players AS p
LEFT JOIN public.teams AS t
    ON t.team_id = p.current_team_id
WHERE p.full_name ILIKE :search_pattern
ORDER BY
    p.is_active DESC NULLS LAST,
    p.full_name
LIMIT :limit
"""


ACTIVE_PLAYERS_QUERY = """
SELECT
    p.player_id,
    p.full_name,
    p.current_team_id,
    t.abbreviation AS team_abbreviation,
    t.team_name,
    p.position_code,
    p.bats,
    p.throws
FROM public.players AS p
LEFT JOIN public.teams AS t
    ON t.team_id = p.current_team_id
WHERE p.is_active IS TRUE
ORDER BY p.full_name
LIMIT :limit
"""

PITCHER_PITCHES_QUERY = """
SELECT
    sp.pitch_id,
    sp.game_pk,
    sp.game_date,
    g.season,
    g.game_type,
    g.park_id,
    park.park_name,
    g.home_team_id,
    home_team.abbreviation AS home_team,
    g.away_team_id,
    away_team.abbreviation AS away_team,
    sp.plate_appearance_number,
    sp.at_bat_number,
    sp.pitch_number,
    sp.inning,
    sp.inning_half,
    sp.outs,
    sp.ball_count,
    sp.strike_count,
    sp.batter_id,
    batter.full_name AS batter_name,
    batter.bats AS batter_side,
    sp.pitcher_id,
    pitcher.full_name AS pitcher_name,
    pitcher.throws AS pitcher_throws,
    sp.pitch_type,
    sp.release_velocity,
    sp.release_spin_rate,
    sp.release_extension,
    sp.release_pos_x,
    sp.release_pos_y,
    sp.release_pos_z,
    sp.vx0,
    sp.vy0,
    sp.vz0,
    sp.ax,
    sp.ay,
    sp.az,
    sp.effective_speed,
    sp.plate_crossing_x,
    sp.plate_crossing_z,
    sp.sz_top,
    sp.sz_bot,
    sp.runner_on_first,
    sp.runner_on_second,
    sp.runner_on_third,
    sp.home_score,
    sp.away_score,
    sp.play_event,
    sp.play_description,
    sp.exit_velocity,
    sp.launch_angle,
    sp.hit_distance,
    sp.spray_angle,
    sp.hit_location_x,
    sp.hit_location_y,
    sp.expected_woba,
    sp.expected_slugging,
    sp.is_hard_hit,
    sp.is_sweet_spot,
    g.temperature_f,
    g.sky_condition,
    g.wind_speed_mph,
    g.wind_direction,
    park.elevation,
    sp.play_description
FROM public.statcast_pitches AS sp
LEFT JOIN public.games AS g
    ON g.game_pk = sp.game_pk
LEFT JOIN public.players AS pitcher
    ON pitcher.player_id = sp.pitcher_id
LEFT JOIN public.players AS batter
    ON batter.player_id = sp.batter_id
LEFT JOIN public.parks AS park
    ON park.park_id = g.park_id
LEFT JOIN public.teams AS home_team
    ON home_team.team_id = g.home_team_id
LEFT JOIN public.teams AS away_team
    ON away_team.team_id = g.away_team_id
WHERE sp.pitcher_id = :pitcher_id
  AND (
        CAST(:season AS INTEGER) IS NULL
        OR g.season = CAST(:season AS INTEGER)
      )
  AND (
        CAST(:start_date AS DATE) IS NULL
        OR sp.game_date >= CAST(:start_date AS DATE)
      )
  AND (
        CAST(:end_date AS DATE) IS NULL
        OR sp.game_date <= CAST(:end_date AS DATE)
      )
ORDER BY
    sp.game_date,
    sp.game_pk,
    sp.at_bat_number,
    sp.pitch_number
"""

BATTER_PITCHES_QUERY = """
SELECT
    sp.pitch_id,
    sp.game_pk,
    sp.game_date,
    g.season,
    g.game_type,
    g.park_id,
    park.park_name,
    g.home_team_id,
    home_team.abbreviation AS home_team,
    g.away_team_id,
    away_team.abbreviation AS away_team,
    sp.plate_appearance_number,
    sp.at_bat_number,
    sp.pitch_number,
    sp.inning,
    sp.inning_half,
    sp.outs,
    sp.ball_count,
    sp.strike_count,
    sp.batter_id,
    batter.full_name AS batter_name,
    batter.bats AS batter_side,
    sp.pitcher_id,
    pitcher.full_name AS pitcher_name,
    pitcher.throws AS pitcher_throws,
    sp.pitch_type,
    sp.release_velocity,
    sp.release_spin_rate,
    sp.release_extension,
    sp.release_pos_x,
    sp.release_pos_y,
    sp.release_pos_z,
    sp.effective_speed,
    sp.plate_crossing_x,
    sp.plate_crossing_z,
    sp.sz_top,
    sp.sz_bot,
    sp.runner_on_first,
    sp.runner_on_second,
    sp.runner_on_third,
    sp.home_score,
    sp.away_score,
    sp.play_event,
    sp.play_description,
    sp.exit_velocity,
    sp.launch_angle,
    sp.hit_distance,
    sp.spray_angle,
    sp.hit_location_x,
    sp.hit_location_y,
    sp.expected_woba,
    sp.expected_slugging,
    sp.is_hard_hit,
    sp.is_sweet_spot,
    g.temperature_f,
    g.sky_condition,
    g.wind_speed_mph,
    g.wind_direction,
    park.elevation,
    sp.play_description
FROM public.statcast_pitches AS sp
LEFT JOIN public.games AS g
    ON g.game_pk = sp.game_pk
LEFT JOIN public.players AS pitcher
    ON pitcher.player_id = sp.pitcher_id
LEFT JOIN public.players AS batter
    ON batter.player_id = sp.batter_id
LEFT JOIN public.parks AS park
    ON park.park_id = g.park_id
LEFT JOIN public.teams AS home_team
    ON home_team.team_id = g.home_team_id
LEFT JOIN public.teams AS away_team
    ON away_team.team_id = g.away_team_id
WHERE sp.batter_id = :batter_id
  AND (
        CAST(:season AS INTEGER) IS NULL
        OR g.season = CAST(:season AS INTEGER)
      )
  AND (
        CAST(:start_date AS DATE) IS NULL
        OR sp.game_date >= CAST(:start_date AS DATE)
      )
  AND (
        CAST(:end_date AS DATE) IS NULL
        OR sp.game_date <= CAST(:end_date AS DATE)
      )
ORDER BY
    sp.game_date,
    sp.game_pk,
    sp.at_bat_number,
    sp.pitch_number
"""


MATCHUP_PITCHES_QUERY = """
SELECT
    sp.*,
    g.season,
    g.park_id,
    park.park_name,
    park.elevation,
    g.temperature_f,
    g.sky_condition,
    g.wind_speed_mph,
    g.wind_direction
FROM public.statcast_pitches AS sp
LEFT JOIN public.games AS g
    ON g.game_pk = sp.game_pk
LEFT JOIN public.parks AS park
    ON park.park_id = g.park_id
WHERE sp.pitcher_id = :pitcher_id
  AND sp.batter_id = :batter_id
  AND (
      CAST(:season AS INTEGER) IS NULL
      OR g.season = CAST(:season AS INTEGER)
    )
ORDER BY
    sp.game_date,
    sp.game_pk,
    sp.at_bat_number,
    sp.pitch_number
"""

# GAMES
GAME_BY_ID_QUERY = """
SELECT
    g.game_pk,
    g.game_date,
    g.season,
    g.game_type,
    g.scheduled_start,
    g.park_id,
    park.park_name,
    park.elevation,
    g.home_team_id,
    home_team.abbreviation AS home_team_abbreviation,
    home_team.team_name AS home_team_name,
    g.away_team_id,
    away_team.abbreviation AS away_team_abbreviation,
    away_team.team_name AS away_team_name,
    g.home_score,
    g.away_score,
    g.day_night_type,
    g.is_doubleheader,
    g.temperature_f,
    g.sky_condition,
    g.wind_speed_mph,
    g.wind_direction,
    g.home_plate_ump_id,
    hp_ump.umpire_name AS home_plate_umpire,
    g.first_base_ump_id,
    first_ump.umpire_name AS first_base_umpire,
    g.second_base_ump_id,
    second_ump.umpire_name AS second_base_umpire,
    g.third_base_ump_id,
    third_ump.umpire_name AS third_base_umpire,
    g.winning_team_id,
    winning_team.abbreviation AS winning_team_abbreviation,
    g.is_home_team_win
FROM public.games AS g
LEFT JOIN public.parks AS park
    ON park.park_id = g.park_id
LEFT JOIN public.teams AS home_team
    ON home_team.team_id = g.home_team_id
LEFT JOIN public.teams AS away_team
    ON away_team.team_id = g.away_team_id
LEFT JOIN public.teams AS winning_team
    ON winning_team.team_id = g.winning_team_id
LEFT JOIN public.umpires AS hp_ump
    ON hp_ump.umpire_id = g.home_plate_ump_id
LEFT JOIN public.umpires AS first_ump
    ON first_ump.umpire_id = g.first_base_ump_id
LEFT JOIN public.umpires AS second_ump
    ON second_ump.umpire_id = g.second_base_ump_id
LEFT JOIN public.umpires AS third_ump
    ON third_ump.umpire_id = g.third_base_ump_id
WHERE g.game_pk = :game_pk
"""

GAMES_BY_DATE_QUERY = """
SELECT
    g.game_pk,
    g.game_date,
    g.season,
    g.game_type,
    g.scheduled_start,
    g.park_id,
    park.park_name,
    park.elevation,
    g.home_team_id,
    home_team.abbreviation AS home_team,
    g.away_team_id,
    away_team.abbreviation AS away_team,
    g.home_score,
    g.away_score,
    g.day_night_type,
    g.temperature_f,
    g.sky_condition,
    g.wind_speed_mph,
    g.wind_direction
FROM public.games AS g
LEFT JOIN public.parks AS park
    ON park.park_id = g.park_id
LEFT JOIN public.teams AS home_team
    ON home_team.team_id = g.home_team_id
LEFT JOIN public.teams AS away_team
    ON away_team.team_id = g.away_team_id
WHERE g.game_date = :game_date
ORDER BY g.scheduled_start, g.game_pk
"""

RECENT_GAMES_QUERY = """
SELECT
    g.game_pk,
    g.game_date,
    g.season,
    g.scheduled_start,
    g.park_id,
    park.park_name,
    g.home_team_id,
    home_team.abbreviation AS home_team,
    g.away_team_id,
    away_team.abbreviation AS away_team,
    g.home_score,
    g.away_score,
    g.temperature_f,
    g.sky_condition,
    g.wind_speed_mph,
    g.wind_direction
FROM public.games AS g
LEFT JOIN public.parks AS park
    ON park.park_id = g.park_id
LEFT JOIN public.teams AS home_team
    ON home_team.team_id = g.home_team_id
LEFT JOIN public.teams AS away_team
    ON away_team.team_id = g.away_team_id
WHERE (
    CAST(:season AS INTEGER) IS NULL
    OR g.season = CAST(:season AS INTEGER)
)
ORDER BY g.game_date DESC, g.scheduled_start DESC
LIMIT :limit
"""

# LINEUPS
GAME_LINEUPS_QUERY = """
SELECT
    sl.id,
    sl.game_pk,
    sl.team_id,
    team.abbreviation AS team_abbreviation,
    team.team_name,
    sl.batting_order_slot,
    sl.player_id,
    player.full_name AS player_name,
    sl.field_position,
    sl.batting_side
FROM public.starting_lineups AS sl
LEFT JOIN public.teams AS team
    ON team.team_id = sl.team_id
LEFT JOIN public.players AS player
    ON player.player_id = sl.player_id
WHERE sl.game_pk = :game_pk
ORDER BY sl.team_id, sl.batting_order_slot
"""

# PARKS
PARKS_QUERY = """
SELECT
    park_id,
    park_name,
    elevation
FROM public.parks
ORDER BY park_name
"""


PARK_BY_ID_QUERY = """
SELECT
    park_id,
    park_name,
    elevation
FROM public.parks
WHERE park_id = :park_id
"""


PARK_GAMES_QUERY = """
SELECT
    g.game_pk,
    g.game_date,
    g.season,
    g.home_team_id,
    home_team.abbreviation AS home_team,
    g.away_team_id,
    away_team.abbreviation AS away_team,
    g.home_score,
    g.away_score,
    g.temperature_f,
    g.sky_condition,
    g.wind_speed_mph,
    g.wind_direction,
    g.day_night_type
FROM public.games AS g
LEFT JOIN public.teams AS home_team
    ON home_team.team_id = g.home_team_id
LEFT JOIN public.teams AS away_team
    ON away_team.team_id = g.away_team_id
WHERE g.park_id = :park_id
  AND (
        CAST(:season AS INTEGER) IS NULL
        OR g.season = CAST(:season AS INTEGER)
      )
ORDER BY g.game_date
"""

# TEAMS
TEAMS_QUERY = """
SELECT
    team_id,
    abbreviation,
    team_name,
    city,
    nickname,
    league,
    division,
    team_code,
    location_name
FROM public.teams
ORDER BY team_name
"""


TEAM_BY_ID_QUERY = """
SELECT
    team_id,
    abbreviation,
    team_name,
    city,
    nickname,
    league,
    division,
    team_code,
    location_name
FROM public.teams
WHERE team_id = :team_id
"""

# TRANSACTIONS
PLAYER_TRANSACTIONS_QUERY = """
SELECT
    tr.id,
    tr.player_id,
    player.full_name AS player_name,
    tr.transaction_date,
    tr.transaction_type,
    tr.from_team_id,
    from_team.abbreviation AS from_team,
    tr.to_team_id,
    to_team.abbreviation AS to_team,
    tr.injury_status
FROM public.transactions AS tr
LEFT JOIN public.players AS player
    ON player.player_id = tr.player_id
LEFT JOIN public.teams AS from_team
    ON from_team.team_id = tr.from_team_id
LEFT JOIN public.teams AS to_team
    ON to_team.team_id = tr.to_team_id
WHERE tr.player_id = :player_id
ORDER BY tr.transaction_date DESC, tr.id DESC
"""

RECENT_TRANSACTIONS_QUERY = """
SELECT
    tr.id,
    tr.player_id,
    player.full_name AS player_name,
    tr.transaction_date,
    tr.transaction_type,
    tr.from_team_id,
    from_team.abbreviation AS from_team,
    tr.to_team_id,
    to_team.abbreviation AS to_team,
    tr.injury_status
FROM public.transactions AS tr
LEFT JOIN public.players AS player
    ON player.player_id = tr.player_id
LEFT JOIN public.teams AS from_team
    ON from_team.team_id = tr.from_team_id
LEFT JOIN public.teams AS to_team
    ON to_team.team_id = tr.to_team_id
ORDER BY tr.transaction_date DESC, tr.id DESC
LIMIT :limit
"""

# Pitcher and Batter Analysis
PITCHER_BATTER_MATCHUP_QUERY = """
SELECT
    sp.pitch_id,
    sp.game_pk,
    sp.game_date,
    sp.inning,
    sp.inning_half,
    sp.plate_appearance_number,
    sp.at_bat_number,
    sp.pitch_number,

    sp.pitcher_id,
    pitcher.full_name AS pitcher_name,
    pitcher.throws AS pitcher_throws,

    sp.batter_id,
    batter.full_name AS batter_name,
    batter.bats AS batter_side,

    sp.pitch_type,
    sp.release_velocity,
    sp.release_spin_rate,
    sp.release_extension,
    sp.release_pos_x,
    sp.release_pos_y,
    sp.release_pos_z,

    sp.plate_crossing_x,
    sp.plate_crossing_z,
    sp.sz_top,
    sp.sz_bot,

    sp.ball_count,
    sp.strike_count,
    sp.outs,

    sp.play_event,
    sp.play_description,

    sp.exit_velocity,
    sp.launch_angle,
    sp.hit_distance,
    sp.expected_woba,
    sp.expected_slugging,
    sp.is_hard_hit,
    sp.is_sweet_spot

FROM public.statcast_pitches AS sp

INNER JOIN public.players AS pitcher
    ON pitcher.player_id = sp.pitcher_id

INNER JOIN public.players AS batter
    ON batter.player_id = sp.batter_id

INNER JOIN public.games AS g
    ON g.game_pk = sp.game_pk

WHERE sp.pitcher_id = :pitcher_id
  AND sp.batter_id = :batter_id

  AND (
        CAST(:season AS INTEGER) IS NULL
        OR g.season = CAST(:season AS INTEGER)
      )

  AND (
        CAST(:start_date AS DATE) IS NULL
        OR sp.game_date >= CAST(:start_date AS DATE)
      )

  AND (
        CAST(:end_date AS DATE) IS NULL
        OR sp.game_date <= CAST(:end_date AS DATE)
      )

ORDER BY
    sp.game_date DESC,
    sp.game_pk DESC,
    sp.at_bat_number,
    sp.pitch_number
"""
# Player Searcher
PLAYER_SEARCH_QUERY = """
SELECT
    p.player_id,
    p.full_name,
    p.current_team_id,
    t.abbreviation AS team_abbreviation,
    p.position_code,
    p.bats,
    p.throws,
    p.is_active

FROM public.players AS p

LEFT JOIN public.teams AS t
    ON t.team_id = p.current_team_id

WHERE LOWER(p.full_name) LIKE LOWER(:search_pattern)

ORDER BY
    CASE
        WHEN LOWER(p.full_name) = LOWER(:exact_name) THEN 0
        WHEN LOWER(p.full_name) LIKE LOWER(:starts_with) THEN 1
        ELSE 2
    END,
    p.full_name

LIMIT :limit
"""

PITCHER_SEARCH_QUERY = """
SELECT DISTINCT
    p.player_id,
    p.full_name,
    p.current_team_id,
    t.abbreviation AS team_abbreviation,
    p.position_code,
    p.throws,
    p.is_active

FROM public.players AS p

INNER JOIN public.statcast_pitches AS sp
    ON sp.pitcher_id = p.player_id

LEFT JOIN public.teams AS t
    ON t.team_id = p.current_team_id

WHERE LOWER(p.full_name) LIKE LOWER(:search_pattern)

ORDER BY p.full_name
LIMIT :limit
"""

BATTER_SEARCH_QUERY = """
SELECT DISTINCT
    p.player_id,
    p.full_name,
    p.current_team_id,
    t.abbreviation AS team_abbreviation,
    p.position_code,
    p.bats,
    p.is_active

FROM public.players AS p

INNER JOIN public.statcast_pitches AS sp
    ON sp.batter_id = p.player_id

LEFT JOIN public.teams AS t
    ON t.team_id = p.current_team_id

WHERE LOWER(p.full_name) LIKE LOWER(:search_pattern)

ORDER BY p.full_name
LIMIT :limit
"""

