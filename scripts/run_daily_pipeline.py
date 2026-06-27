import sys
import os
from datetime import datetime, timedelta

# Dynamically append the scripts directory to Python's lookup path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Now these imports will work flawlessly both locally and in Railway!
import scrape_statcast
import scrape_game_feed
import scrape_lineups
import scrape_rosters
import scrape_pitch_arsenal
import scrape_defense
import scrape_bullpen
import scrape_weather
import scrape_umpires
import scrape_park_info
import scrape_schedule

# ... rest of your code remains exactly the same

def run_pipeline_for_date(target_date):
    print(f"\n=========================================")
    print(f"STARTING MLB PIPELINE FOR: {target_date}")
    print(f"=========================================\n")
    
    # -------------------------------------------------------------
    # LAYER 0: Structural Base Tables (Run once or check existence)
    # -------------------------------------------------------------
    print("--- Running Base / Static Infrastructure Checks ---")
    try: 
        # Park layouts and the seasonal calendar framework
        scrape_park_info.run()
        scrape_schedule.run(season=2026)
    except Exception as e: 
        print(f"Warning in static infrastructure setup: {e}")
        
    try:
        # Update rosters to capture any transactions/call-ups
        scrape_rosters.run(season=2026)
    except Exception as e:
        print(f"Warning updating active player pool: {e}")

    # -------------------------------------------------------------
    # LAYER 1: Core Daily Game Data (Creates parent rows)
    # -------------------------------------------------------------
    print("\n--- Processing Core Game Feeds ---")
    try: 
        scrape_game_feed.run(target_date)
    except Exception as e: 
        print(f"Error in game feed processing: {e}")
        return  # If the parent games table fails, child records will break foreign keys
    
    # -------------------------------------------------------------
    # LAYER 2: Pitch-by-Pitch heavy lifting
    # -------------------------------------------------------------
    print("\n--- Ingesting Pitch-by-Pitch Metrics ---")
    try: 
        scrape_statcast.run(target_date, target_date)
    except Exception as e: 
        print(f"Error in Statcast data gathering: {e}")
    
    # -------------------------------------------------------------
    # LAYER 3: In-Game Context Sub-Scrapers
    # -------------------------------------------------------------
    print("\n--- Extracting Detailed Game Situations ---")
    try: scrape_lineups.run(target_date)
    except Exception as e: print(f"Error in lineups: {e}")
    
    try: scrape_defense.run(target_date)
    except Exception as e: print(f"Error in defensive alignments: {e}")
    
    try: scrape_bullpen.run(target_date)
    except Exception as e: print(f"Error in bullpen tracking: {e}")
    
    try: scrape_weather.run(target_date)
    except Exception as e: print(f"Error in weather telemetry: {e}")
    
    try: scrape_umpires.run(target_date)
    except Exception as e: print(f"Error in umpire collection: {e}")
    
    # -------------------------------------------------------------
    # LAYER 4: Downstream Aggregations
    # -------------------------------------------------------------
    print("\n--- Recalculating Dynamic Metrics ---")
    try: 
        scrape_pitch_arsenal.run()
    except Exception as e: 
        print(f"Error updating pitcher arsenals: {e}")

    print(f"\n=========================================")
    print(f"Pipeline successfully completed for {target_date}!")
    print(f"=========================================\n")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        run_pipeline_for_date(sys.argv[1])
    else:
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        run_pipeline_for_date(yesterday)
