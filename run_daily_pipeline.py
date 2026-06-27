import sys
import os
from datetime import datetime, timedelta

# Force Python to treat the scripts directory as a core lookup folder
scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

# Clean, direct module imports
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

def run_pipeline_for_date(target_date):
    print(f"\n=========================================")
    print(f"RUNNING MLB DATA STREAM FOR: {target_date}")
    print(f"=========================================\n")
    
    print("--- Running Base Infrastructure Updates ---")
    try: scrape_park_info.run()
    except Exception as e: print(f"Warning in park setup: {e}")
        
    try: scrape_schedule.run(season=2026)
    except Exception as e: print(f"Warning in schedule setup: {e}")
        
    try: scrape_rosters.run(season=2026)
    except Exception as e: print(f"Warning in active rosters: {e}")

    print("\n--- Ingesting Core Game Feed ---")
    try: scrape_game_feed.run(target_date)
    except Exception as e: 
        print(f"Error in game feed processing: {e}")
        return  
    
    print("\n--- Ingesting Pitch-by-Pitch Statcast Metrics ---")
    try: scrape_statcast.run(target_date, target_date)
    except Exception as e: print(f"Error in Statcast data gathering: {e}")
    
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
    
    print("\n--- Recalculating Dynamic Performance Baselines ---")
    try: scrape_pitch_arsenal.run()
    except Exception as e: print(f"Error updating pitch arsenals: {e}")

    print(f"\nCompleted execution block for {target_date}!")

if __name__ == '__main__':
    # Determine the date scopes dynamically
    today_str = datetime.now().strftime('%Y-%m-%d')
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    if len(sys.argv) > 1:
        # If a manual argument is given, run just that date
        run_pipeline_for_date(sys.argv[1])
    else:
        print(f"Kicking off multi-day automated rolling window loop...")
        # 1. Run yesterday first to capture late/finalized box scores
        run_pipeline_for_date(yesterday_str)
        # 2. Run today to capture live/early schedules and lineups
        run_pipeline_for_date(today_str)
        print("\n=========================================")
        print("ALL TARGETED ROLLING DATES SYNCED PERFECTLY!")
        print("=========================================\n")
