import os
import sys

# =======================================================
# PATH IMMUNITY SAFEGUARDS (Must execute first)
# =======================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
SRC_DIR = os.path.join(BASE_DIR, "src")                               

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# =======================================================
# CORE IMPORTS
# =======================================================
import psycopg2
from datetime import date, timedelta
from psycopg2.extras import execute_values

# Master Import Matrix matching your exact repository files
from src.scrapers.scrape_stadium_registry import fetch_mlb_stadiums
from src.scrapers.scrape_schedule import fetch_season_schedule
from src.scrapers.scrape_players import fetch_team_roster
from src.scrapers.scrape_park_factors import fetch_park_factors
from src.scrapers.scrape_catcher_framing import fetch_catcher_framing_metrics
from src.scrapers.scrape_environmental_weather import fetch_environmental_weather
from src.scrapers.scrape_pitch_by_pitch import fetch_game_pitch_by_pitch
from src.scrapers.scrape_boxscore import fetch_boxscore_data
from src.scrapers.scrape_injuries import fetch_injury_reports
from src.scrapers.scrape_bullpen import fetch_bullpen_metrics
from src.scrapers.scrape_defensive_quality import fetch_defensive_quality
from src.scrapers.scrape_team_trends import fetch_team_trends
from src.scrapers.scrape_umpire_trends import fetch_umpire_trends
from src.scrapers.scrape_player_fatigue import estimate_player_fatigue
from src.scrapers.scrape_baserunning import fetch_baserunning_metrics

# Splits & Lineups
from src.scrapers.scrape_batter_splits import fetch_batter_splits       # Matching your typo file name
from src.scrapers.scraper_player_splits import fetch_player_splits
from src.scrapers.scrape_pitcher_platoon_splits import fetch_pitcher_platoon_splits
from src.scrapers.scrape_pitcher_season import fetch_pitcher_season_stats
from src.scrapers.scrape_batter_statcast import fetch_batter_statcast
from src.scrapers.scrape_batter_vs_pitch_type import fetch_batter_vs_pitch_type
from src.scrapers.scrape_batter_vs_pitcher import fetch_batter_vs_pitcher
from src.scrapers.scrape_battar_lineup_position import fetch_lineup_positions

def get_db_connection():
    """Establishes connection to the Postgres warehouse."""
    return psycopg2.connect(
        dbname=os.getenv("DATABASE_PUBLIC_URL") or os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        host=os.getenv("PGHOST"),
        port=os.getenv("PGPORT")
    )

def run_pipeline(season: int):
    print(f"--- Starting Global ETL Pipeline Sequence for Season {season} ---")
    conn = get_db_connection()
    
    try:
        # =======================================================
        # PHASE 1: STATIC & GLOBAL ENVIRONMENT MATRIX
        # =======================================================
        print("Ingesting Stadium Registries & Park Factors...")
        stadiums_data = fetch_mlb_stadiums(season=season)
        park_factors = fetch_park_factors(season=season)
        # (Execute db inserts for stadiums/park factors here)
        
        print("Ingesting Master Schedule Matrix...")
        schedule_games = fetch_season_schedule(season=season)
        # (Execute db inserts for schedule matrix here)
        conn.commit()

        # =======================================================
        # PHASE 2: DAILY LEAGUE-WIDE UPDATES (Non-Game Specific)
        # =======================================================
        print("Updating League Injury Reports...")
        injuries = fetch_injury_reports()
        
        print("Compiling Team Trends, Defensive Quality, & Umpires...")
        defensive_quality = fetch_defensive_quality(season=season)
        team_trends = fetch_team_trends(season=season)
        umpire_trends = fetch_umpire_trends(season=season)
        conn.commit()

        # =======================================================
        # PHASE 3: TARGETED YESTERDAY GAME HYDRO-STREAM
        # =======================================================
        yesterday_str = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        print(f"Filtering completed game datasets for yesterday ({yesterday_str})...")
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT game_pk FROM schedule 
                WHERE status = 'Final' AND season = %s AND game_date = %s;
            """, (season, yesterday_str))
            completed_games = [row[0] for row in cur.fetchall()]

        if not completed_games:
            print("No finalized games found for yesterday. Skipping game-level scraping.")
        else:
            for game_pk in completed_games:
                print(f"🎮 Hydrating game metric profiles for game_pk: {game_pk}")
                weather = fetch_environmental_weather(conn, game_pk)
                boxscore = fetch_boxscore_data(conn, game_pk)
                pitches = fetch_game_pitch_by_pitch(conn, game_pk)
                # (Execute your transactional batch updates for games here)
            conn.commit()

        # =======================================================
        # PHASE 4: PLAYER SPLITS & DERIVED MATRICES
        # =======================================================
        print("Updating Statcast Performance, Splits & Lineup Registries...")
        catcher_framing = fetch_catcher_framing_metrics(season=season)
        bullpen_relief = fetch_bullpen_metrics(season=season)
        baserunning = fetch_baserunning_metrics(season=season)
        
        # Pulling active player loop to process deep historical matchups
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT player_id FROM players;")
            all_players = [row[0] for row in cur.fetchall()]

        print(f"Syncing split profiles and fatigue coefficients for {len(all_players)} players...")
        for player_id in all_players:
            fatigue = estimate_player_fatigue(conn, player_id, season=season)
            bat_splits = fetch_batter_splits(player_id, season=season)
            pitch_platoon = fetch_pitcher_platoon_splits(player_id, season=season)
            # (Execute updates for deep matchups, vs_pitch_type, vs_pitcher, and lineups)
            
        conn.commit()
        print("Global Pipeline execution cycle completed successfully.")

    except Exception as e:
        conn.rollback()
        print(f"Pipeline crashed during transaction sequence: {e}")
        raise e
    finally:
        conn.close()

if __name__ == "__main__":
    target_year = int(sys.argv[1]) if len(sys.argv) > 1 else date.today().year
    run_pipeline(target_year)
