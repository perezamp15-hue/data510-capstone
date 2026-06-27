import sys
from datetime import datetime, timedelta

# Import your individual scrapers
import scrape_statcast
import scrape_game_feed
import scrape_lineups
import scrape_defense
import scrape_bullpen
import scrape_weather
import scrape_umpires
import scrape_pitch_arsenal

def run_pipeline_for_date(target_date):
    print(f"\n=========================================")
    print(f"STARTING MLB PIPELINE FOR: {target_date}")
    print(f"=========================================\n")
    
    # 1. High-level Game Feed (Creates parent game rows)
    try: scrape_game_feed.run(target_date)
    except Exception as e: print(f"Error in game feed: {e}")
    
    # 2. Statcast Pitches (The heavy lifting)
    try: scrape_statcast.run(target_date, target_date)
    except Exception as e: print(f"Error in statcast: {e}")
    
    # 3. Game Details (Lineups, Defense, Weather, Umpires, Bullpen)
    try: scrape_lineups.run(target_date)
    except Exception as e: print(f"Error in lineups: {e}")
    
    try: scrape_defense.run(target_date)
    except Exception as e: print(f"Error in defense: {e}")
    
    try: scrape_bullpen.run(target_date)
    except Exception as e: print(f"Error in bullpen: {e}")
    
    try: scrape_weather.run(target_date)
    except Exception as e: print(f"Error in weather: {e}")
    
    try: scrape_umpires.run(target_date)
    except Exception as e: print(f"Error in umpires: {e}")
    
    # 4. Recalculate derived data (Pitch Arsenal updates based on new history)
    try: scrape_pitch_arsenal.run()
    except Exception as e: print(f"Error updating pitch arsenal: {e}")

    print(f"\nPipeline successfully completed for {target_date}!")

if __name__ == '__main__':
    # If a date string is passed (e.g., python run_daily_pipeline.py 2026-06-25)
    if len(sys.argv) > 1:
        run_pipeline_for_date(sys.argv[1])
    else:
        # Default to yesterday's date
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        run_pipeline_for_date(yesterday)
