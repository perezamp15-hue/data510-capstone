-- games
CREATE TABLE public.games (
  game_pk integer NOT NULL,
  game_date date NOT NULL,
  season integer NOT NULL,
  game_type character varying(10) NULL,
  scheduled_start timestamp without time zone NULL,
  park_id integer NULL,
  home_team_id integer NULL,
  away_team_id integer NULL,
  home_score integer NULL,
  away_score integer NULL,
  day_night_type character varying(20) NULL,
  is_doubleheader boolean NULL,
  temperature_f integer NULL,
  sky_condition character varying(100) NULL,
  wind_speed_mph integer NULL,
  wind_direction character varying(50) NULL,
  home_plate_ump_id integer NULL,
  first_base_ump_id integer NULL,
  second_base_ump_id integer NULL,
  third_base_ump_id integer NULL,
  winning_team_id integer NULL,
  is_home_team_win boolean NULL
);

ALTER TABLE public.games
ADD CONSTRAINT games_pkey PRIMARY KEY (game_pk)

-- Parks
CREATE TABLE public.parks (
  park_id integer NOT NULL,
  park_name character varying(150) NULL,
  elevation integer NULL
);

ALTER TABLE public.parks
ADD CONSTRAINT parks_pkey PRIMARY KEY (park_id)

-- Players
CREATE TABLE public.players (
  player_id integer NOT NULL,
  full_name character varying(150) NULL,
  current_team_id integer NULL,
  position_code character varying(10) NULL,
  bats character varying(5) NULL,
  throws character varying(5) NULL,
  birth_date date NULL,
  height character varying(20) NULL,
  weight integer NULL,
  mlb_debut date NULL,
  is_active boolean NULL
);

ALTER TABLE public.players
ADD CONSTRAINT players_pkey PRIMARY KEY (player_id)

-- Starting Lineup
CREATE TABLE public.starting_lineups (
  id serial NOT NULL,
  game_pk integer NULL,
  team_id integer NULL,
  batting_order_slot integer NOT NULL,
  player_id integer NULL,
  field_position character varying(10) NULL,
  batting_side character varying(1) NULL
);

ALTER TABLE public.starting_lineups
ADD CONSTRAINT starting_lineups_pkey PRIMARY KEY (id)

-- Pitch by Pitch Data 
CREATE TABLE public.statcast_pitches (
  pitch_id bigserial NOT NULL,
  game_pk integer NULL,
  game_date date NULL,
  plate_appearance_number integer NULL,
  at_bat_number integer NULL,
  pitch_number integer NULL,
  inning integer NULL,
  inning_half character varying(3) NULL,
  outs integer NULL,
  ball_count integer NULL,
  strike_count integer NULL,
  batter_id integer NULL,
  pitcher_id integer NULL,
  pitch_type character varying(10) NULL,
  release_velocity numeric NULL,
  release_spin_rate integer NULL,
  release_extension numeric NULL,
  release_pos_x numeric NULL,
  release_pos_y numeric NULL,
  release_pos_z numeric NULL,
  vx0 numeric NULL,
  vy0 numeric NULL,
  vz0 numeric NULL,
  ax numeric NULL,
  ay numeric NULL,
  az numeric NULL,
  effective_speed numeric NULL,
  plate_crossing_x numeric NULL,
  plate_crossing_z numeric NULL,
  sz_top numeric NULL,
  sz_bot numeric NULL,
  runner_on_first boolean NULL,
  runner_on_second boolean NULL,
  runner_on_third boolean NULL,
  home_score integer NULL,
  away_score integer NULL,
  play_event text NULL,
  play_description text NULL,
  exit_velocity numeric NULL,
  launch_angle numeric NULL,
  hit_distance numeric NULL,
  spray_angle numeric NULL,
  hit_location_x numeric NULL,
  hit_location_y numeric NULL,
  expected_woba numeric NULL,
  expected_slugging numeric NULL,
  is_hard_hit boolean NULL,
  is_sweet_spot boolean NULL
);

ALTER TABLE public.statcast_pitches
ADD CONSTRAINT statcast_pitches_pkey PRIMARY KEY (pitch_id)

-- Teams
CREATE TABLE public.teams (
  team_id integer NOT NULL,
  abbreviation character varying(10) NULL,
  team_name character varying(100) NULL,
  city character varying(100) NULL,
  nickname character varying(100) NULL,
  league character varying(50) NULL,
  division character varying(100) NULL,
  team_code character varying(10) NULL,
  location_name text NULL
);

ALTER TABLE public.teams
ADD CONSTRAINT teams_pkey PRIMARY KEY (team_id)

-- Injury/ Player Transcation table
CREATE TABLE public.transactions (
  id serial NOT NULL,
  player_id integer NULL,
  transaction_date date NOT NULL,
  transaction_type character varying(100) NULL,
  from_team_id integer NULL,
  to_team_id integer NULL,
  injury_status text NULL
);

ALTER TABLE public.transactions
ADD CONSTRAINT transactions_pkey PRIMARY KEY (id)

-- Umpires Data
CREATE TABLE public.umpires (
  umpire_id integer NOT NULL,
  umpire_name character varying(150) NULL
);

ALTER TABLE public.umpires
ADD CONSTRAINT umpires_pkey PRIMARY KEY (umpire_id)

-- Bullpen Usage View
CREATE OR REPLACE VIEW "public"."view_bullpen_usage" AS
SELECT
  pitcher_id,
  game_pk,
  count(pitch_number) AS total_pitch_count,
  count(DISTINCT at_bat_number) AS batters_faced,
  round(
    count(
      CASE
        WHEN play_event = ANY (
          ARRAY[
            'out'::text,
            'field_out'::text,
            'strikeout'::text,
            'grounded_into_double_play'::text
          ]
        ) THEN 1
        ELSE NULL::integer
      END
    )::numeric / 3.0,
    1
  ) AS innings_pitched
FROM
  statcast_pitches
GROUP BY
  pitcher_id,
  game_pk;

-- Pitcher's Favorite Pitches
CREATE OR REPLACE VIEW "public"."view_pitch_arsenal" AS
SELECT
  pitcher_id,
  pitch_type,
  count(*) AS total_pitches_thrown,
  round(avg(release_velocity), 1) AS avg_velocity_mph,
  round(avg(release_spin_rate), 0) AS avg_spin_rate_rpm,
  round(
    count(
      CASE
        WHEN play_description = ANY (
          ARRAY[
            'swinging_strike'::text,
            'swinging_strike_blocked'::text,
            'foul_tip'::text
          ]
        ) THEN 1
        ELSE NULL::integer
      END
    )::numeric * 100.0 / NULLIF(
      count(
        CASE
          WHEN play_description = ANY (
            ARRAY[
              'swinging_strike'::text,
              'swinging_strike_blocked'::text,
              'foul_tip'::text,
              'foul'::text,
              'hit_into_play'::text
            ]
          ) THEN 1
          ELSE NULL::integer
        END
      ),
      0
    )::numeric,
    1
  ) AS whiff_percentage
FROM
  statcast_pitches
WHERE
  pitch_type IS NOT NULL
GROUP BY
  pitcher_id,
  pitch_type;

-- Plate Apperance View
CREATE OR REPLACE VIEW "public"."view_plate_appearances" AS
SELECT
  game_pk,
  batter_id,
  pitcher_id,
  at_bat_number,
  count(pitch_number) AS pitch_sequence_count,
  max(play_event) AS at_bat_outcome,
  max(play_description) AS final_pitch_description
FROM
  statcast_pitches
GROUP BY
  game_pk,
  batter_id,
  pitcher_id,
  at_bat_number;

-- Average Pitches thrown by Pitcher
CREATE OR REPLACE VIEW "public"."view_player_features" AS
SELECT
  pitcher_id,
  game_pk,
  avg(total_pitch_count) OVER (
    PARTITION BY
      pitcher_id
    ORDER BY
      game_pk ROWS BETWEEN 3 PRECEDING
      AND 1 PRECEDING
  ) AS rolling_avg_pitches_thrown
FROM
  view_bullpen_usage;

-- Weather Impact 
CREATE OR REPLACE VIEW "public"."view_prediction_dataset" AS
SELECT
  g.game_pk,
  g.game_date,
  g.home_team_id,
  g.away_team_id,
  g.temperature_f,
  g.wind_speed_mph,
  p.elevation AS park_elevation,
  hf.wins_last_10 AS home_team_wins_last_10,
  af.wins_last_10 AS away_team_wins_last_10,
  CASE
    WHEN g.is_home_team_win = true THEN 1
    ELSE 0
  END AS target_home_team_win
FROM
  games g
  LEFT JOIN parks p ON g.park_id = p.park_id
  LEFT JOIN view_team_features hf ON g.game_pk = hf.game_pk
  AND g.home_team_id = hf.team_id
  LEFT JOIN view_team_features af ON g.game_pk = af.game_pk
  AND g.away_team_id = af.team_id;

-- How Well a team been performing 
CREATE OR REPLACE VIEW "public"."view_team_features" AS
SELECT
  team_id,
  game_pk,
  game_date,
  sum(is_win) OVER (
    PARTITION BY
      team_id
    ORDER BY
      game_date ROWS BETWEEN 5 PRECEDING
      AND 1 PRECEDING
  ) AS wins_last_5,
  sum(is_win) OVER (
    PARTITION BY
      team_id
    ORDER BY
      game_date ROWS BETWEEN 10 PRECEDING
      AND 1 PRECEDING
  ) AS wins_last_10,
  avg(runs_scored) OVER (
    PARTITION BY
      team_id
    ORDER BY
      game_date ROWS BETWEEN 10 PRECEDING
      AND 1 PRECEDING
  ) AS avg_runs_scored_last_10
FROM
  view_team_games;

-- Team verse home and awya
CREATE OR REPLACE VIEW "public"."view_team_games" AS
SELECT
  games.game_pk,
  games.game_date,
  games.season,
  games.home_team_id AS team_id,
  games.home_score AS runs_scored,
  games.away_score AS runs_allowed,
  CASE
    WHEN games.is_home_team_win = true THEN 1
    ELSE 0
  END AS is_win
FROM
  games
UNION ALL
SELECT
  games.game_pk,
  games.game_date,
  games.season,
  games.away_team_id AS team_id,
  games.away_score AS runs_scored,
  games.home_score AS runs_allowed,
  CASE
    WHEN games.is_home_team_win = false THEN 1
    ELSE 0
  END AS is_win
FROM
  games;
