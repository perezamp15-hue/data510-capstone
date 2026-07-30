-- Optional persistence tables for future trained models and saved recommendations.
-- The MVP generator does not require these tables.

CREATE TABLE IF NOT EXISTS public.pitch_sequences (
    pitch_id bigint PRIMARY KEY,
    game_pk integer,
    pitcher_id integer,
    batter_id integer,
    plate_appearance_number integer,
    pitch_number integer,
    previous_pitch_type varchar(10),
    previous_velocity numeric,
    previous_plate_x numeric,
    previous_plate_z numeric,
    current_pitch_type varchar(10),
    current_velocity numeric,
    current_plate_x numeric,
    current_plate_z numeric,
    velocity_change numeric,
    horizontal_location_change numeric,
    vertical_location_change numeric,
    ball_count integer,
    strike_count integer,
    outcome varchar(50)
);

CREATE TABLE IF NOT EXISTS public.matchup_predictions (
    prediction_id bigserial PRIMARY KEY,
    game_pk integer,
    pitcher_id integer,
    batter_id integer,
    model_version varchar(50),
    strikeout_probability numeric,
    walk_probability numeric,
    hit_probability numeric,
    home_run_probability numeric,
    expected_woba numeric,
    recommended_first_pitch varchar(10),
    recommended_putaway_pitch varchar(10),
    recommended_sequence jsonb,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pitch_sequences_matchup
    ON public.pitch_sequences (pitcher_id, batter_id, game_pk);

CREATE INDEX IF NOT EXISTS idx_matchup_predictions_game
    ON public.matchup_predictions (game_pk, pitcher_id);
