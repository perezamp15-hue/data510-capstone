import sys
from datetime import datetime, timedelta

from scripts import scrape_statcast
from scripts import scrape_game_feed
from scripts import scrape_lineups
from scripts import scrape_rosters
from scripts import scrape_pitch_arsenal
from scripts import scrape_defense
from scripts import scrape_bullpen
from scripts import scrape_weather
from scripts import scrape_umpires
from scripts import scrape_park_info
from scripts import scrape_schedule

def run_pipeline_for_date(target_date):
    print(f"\n=========================================")
    print(f"STARTING MLB PIPELINE FOR: {target_date}")
    print(f"=========================================\n")
    
    try: scrape_park_info.run()
    except Exception as e: print(f"Warning in static park setup: {e}")
        
    try: scrape_schedule.run(season=2026)
    except Exception as e: print(f"Warning in static schedule setup: {e}")
        
    try: scrape_rosters.run(season=2026)
    except Exception as e: print(f"Warning updating active rosters: {e}")

    print("\n--- Processing Core Game Feeds ---")
    try: scrape_game_feed.run(target_date)
    except Exception as e: 
        print(f"Error in game feed processing: {e}")
        return  
    
    print("\n--- Ingesting Pitch-by-Pitch Metrics ---")
    try: scrape_statcast.run(target_date, target_date)
    except Exception as e: print(f"Error in Statcast collection: {e}")
    
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
    
    print("\n--- Recalculating Dynamic Metrics ---")
    try: scrape_pitch_arsenal.run()
    except Exception as e: print(f"Error updating pitcher arsenals: {e}")

    print(f"\nPipeline successfully completed for {target_date}!")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        run_pipeline_for_date(sys.argv[1])
    else:
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        run_pipeline_for_date(yesterday)
