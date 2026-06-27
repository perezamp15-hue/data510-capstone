-- Create file name: database_schema.sql

-- Safe cleanup sequence
DROP VIEW IF EXISTS view_model_ready_features;
DROP TABLE IF EXISTS fact_daily_player_stats;
DROP TABLE IF EXISTS fact_umpire_biases;
DROP TABLE IF EXISTS fact_pitches;
DROP TABLE IF EXISTS dim_games;
DROP TABLE IF EXISTS dim_stadiums;
DROP TABLE IF EXISTS dim_players;

-- ==========================================
-- 1. DIMENSION LAYERS
-- ==========================================
CREATE TABLE dim_players (
    player_id INT PRIMARY KEY,               
    player_name VARCHAR(150) NOT NULL,
    primary_position VARCHAR(5),            
    bats CHAR(1) CHECK (bats IN ('L', 'R', 'S')),
    throws CHAR(1) CHECK (throws IN ('L', 'R')),
    injury_status VARCHAR(50) DEFAULT 'Healthy', 
    consecutive_games_played INT DEFAULT 0,
    active_status BOOLEAN DEFAULT TRUE
);

CREATE TABLE dim_stadiums (
    stadium_id INT PRIMARY KEY,              
    stadium_name VARCHAR(150) NOT NULL,
    team_abbreviation CHAR(3),               
    roof_type VARCHAR(50),                   
    altitude INT DEFAULT 0,                  
    wall_height_left INT DEFAULT 8,
    wall_height_right INT DEFAULT 8,
    wind_shielded BOOLEAN DEFAULT FALSE,     
    hr_factor_left NUMERIC(4,2) DEFAULT 1.00,
    hr_factor_right NUMERIC(4,2) DEFAULT 1.00,
    singles_factor NUMERIC(4,2) DEFAULT 1.00,
    doubles_factor NUMERIC(4,2) DEFAULT 1.00,
    triples_factor NUMERIC(4,2) DEFAULT 1.00
);

CREATE TABLE dim_games (
    game_id INT PRIMARY KEY,                 
    game_date DATE NOT NULL,
    game_time TIME,
    home_team CHAR(3) NOT NULL,
    away_team CHAR(3) NOT NULL,
    stadium_id INT REFERENCES dim_stadiums(stadium_id),
    home_starting_pitcher INT REFERENCES dim_players(player_id),
    away_starting_pitcher INT REFERENCES dim_players(player_id),
    home_lineup INT[],                       
    away_lineup INT[],                       
    umpire_home_plate VARCHAR(150),
    
    -- Environmental Physics
    game_temperature NUMERIC(4,1),           
    game_humidity NUMERIC(3,0),              
    game_wind_speed NUMERIC(3,1),            
    game_wind_direction VARCHAR(20),         
    game_air_pressure NUMERIC(4,2)           
);

-- ==========================================
-- 2. FACT TRACKING EVENT TABLES
-- ==========================================
CREATE TABLE fact_pitches (
    pitch_id BIGSERIAL PRIMARY KEY,
    game_id INT REFERENCES dim_games(game_id),
    pitcher_id INT REFERENCES dim_players(player_id),
    batter_id INT REFERENCES dim_players(player_id),
    catcher_id INT REFERENCES dim_players(player_id),
    inning INT NOT NULL,
    inning_topbot CHAR(3),                   
    balls INT,
    strikes INT,
    outs INT,
    pitch_type VARCHAR(3),                   
    velocity NUMERIC(4,1),                   
    spin_rate INT,                           
    vertical_break NUMERIC(4,2),             
    horizontal_break NUMERIC(4,2),           
    plate_x NUMERIC(4,2),                    
    plate_z NUMERIC(4,2),                    
    is_swing BOOLEAN,
    is_contact BOOLEAN,
    exit_velocity NUMERIC(4,1),              
    launch_angle INT,                        
    hit_distance INT,                        
    play_result VARCHAR(50),                 
    xwoba NUMERIC(4,3),
    xba NUMERIC(4,3)
);

CREATE TABLE fact_umpire_biases (
    umpire_name VARCHAR(150) PRIMARY KEY,
    historical_games_called INT,
    strike_zone_modifier NUMERIC(4,3) DEFAULT 1.000, 
    bb_rate_bias NUMERIC(4,3) DEFAULT 1.000,          
    k_rate_bias NUMERIC(4,3) DEFAULT 1.000           
);

-- ==========================================
-- 3. INTERMEDIATE ROLLING AGGREGATES
-- ==========================================
CREATE TABLE fact_daily_player_stats (
    stat_date DATE NOT NULL,
    player_id INT REFERENCES dim_players(player_id),
    PRIMARY KEY (stat_date, player_id),
    
    hitter_rolling_15_ops NUMERIC(4,3),
    hitter_rolling_30_xwoba NUMERIC(4,3),
    hitter_vs_lhp_ops NUMERIC(4,3),
    hitter_vs_rhp_ops NUMERIC(4,3),
    hitter_barrel_rate NUMERIC(4,1),        
    hitter_whiff_rate NUMERIC(4,1),         
    
    pitcher_rolling_3_era NUMERIC(4,2),
    pitcher_vs_lhb_xwoba_allowed NUMERIC(4,3),
    pitcher_vs_rhb_xwoba_allowed NUMERIC(4,3),
    pitcher_groundball_rate NUMERIC(4,1),
    pitch_count_last_appearance INT DEFAULT 0,
    days_since_last_appearance INT DEFAULT 5,
    total_pitches_rolling_30_days INT DEFAULT 0,
    travel_distance_before_game INT DEFAULT 0
);

-- ==========================================
-- 4. MACHINE LEARNING LOGIC FEATURE VIEW
-- ==========================================
CREATE OR REPLACE VIEW view_model_ready_features AS
WITH base_plate_appearances AS (
    SELECT 
        game_id, batter_id, pitcher_id,
        MAX(inning) as inning,
        MAX(exit_velocity) as max_exit_velocity,
        CASE WHEN MAX(play_result) IN ('single', 'double', 'triple', 'home_run') THEN 1 ELSE 0 END as hit,
        CASE WHEN MAX(play_result) = 'strikeout' THEN 1 ELSE 0 END as strikeout,
        CASE WHEN MAX(play_result) = 'walk' THEN 1 ELSE 0 END as walk,
        CASE WHEN MAX(play_result) IN ('single','double','triple','home_run','walk') THEN 1 ELSE 0 END as on_base,
        COUNT(pitch_id) as pitches_seen
    FROM fact_pitches
    GROUP BY game_id, batter_id, pitcher_id
),
rolling_metrics AS (
    SELECT 
        b.game_id, b.batter_id, b.pitcher_id,
        AVG(b.on_base) OVER(PARTITION BY b.batter_id ORDER BY g.game_date ROWS BETWEEN 15 PRECEDING AND 1 PRECEDING) as rolling_15_obp,
        AVG(b.max_exit_velocity) OVER(PARTITION BY b.batter_id ORDER BY g.game_date ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING) as rolling_10_avg_exit_velo,
        AVG(b.strikeout) OVER(PARTITION BY b.batter_id ORDER BY g.game_date ROWS BETWEEN 15 PRECEDING AND 1 PRECEDING) as rolling_15_k_rate,
        AVG(b.pitches_seen) OVER(PARTITION BY b.pitcher_id ORDER BY g.game_date ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING) as pitcher_avg_pitches_per_game,
        AVG(b.hit) OVER(PARTITION BY b.pitcher_id ORDER BY g.game_date ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) as pitcher_cold_streak_metric
    FROM base_plate_appearances b
    JOIN dim_games g ON b.game_id = g.game_id
)
SELECT * FROM rolling_metrics;

-- Indexes for performance
CREATE INDEX idx_pitches_matchup ON fact_pitches(pitcher_id, batter_id);
CREATE INDEX idx_daily_stats_lookup ON fact_daily_player_stats(stat_date, player_id);
CREATE INDEX idx_games_date ON dim_games(game_date);
