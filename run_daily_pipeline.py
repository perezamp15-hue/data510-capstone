import sys
import os
from datetime import datetime, timedelta
import pytz

# Inject local scripts context directory directly into lookup priority path
scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

import scrape_teams
import scrape_park_info
import scrape_rosters
import scrape_schedule
import scrape_game_feed
import scrape_statcast
import scrape_lineups
import scrape_defense
import scrape_bullpen
import scrape_weather
import scrape_umpires
import scrape_pitch_arsenal

def run_pipeline_for_date(target_date):
    print(f"\n=========================================")
    print(f"RUNNING RESTRUCTURED DATA PIPELINE FOR: {target_date}")
    print(f"=========================================\n")
    
    print("--- Phase 1: Refreshing Core Dimensions & Context Registry ---")
    try: scrape_teams.run()
    except Exception as e: print(f"Warning in teams syncing: {e}")
        
    try: scrape_park_info.run()
    except Exception as e: print(f"Warning in parks syncing: {e}")
        
    try: scrape_rosters.run(season=2026)
    except Exception as e: print(f"Warning in roster snapshot: {e}")

    print("\n--- Phase 2: Updating Framework Schedules & Core Matches ---")
    try: scrape_schedule.run(season=2026)
    except Exception as e: print(f"Warning in schedule snapshot: {e}")
        
    try: scrape_game_feed.run(target_date)
    except Exception as e:
        print(f"CRITICAL ERROR: Main Match Ledger generation failed for {target_date}: {e}")
        return  # Halt if the primary game records are not available

    print("\n--- Phase 3: Processing Granular Pitch Physics & High-Fidelity Tracking ---")
    try: scrape_statcast.run(target_date, target_date)
    except Exception as e: print(f"Error gathering Statcast dimensions: {e}")
        
    try: scrape_lineups.run(target_date)
    except Exception as e: print(f"Error compiling starting lineup cards: {e}")
        
    try: scrape_defense.run(target_date)
    except Exception as e: print(f"Error compiling defensive alignments: {e}")
        
    try: scrape_bullpen.run(target_date)
    except Exception as e: print(f"Error mapping bullpen appearances: {e}")
        
    try: scrape_weather.run(target_date)
    except Exception as e: print(f"Error compiling weather dimensions: {e}")
        
    try: scrape_umpires.run(target_date)
    except Exception as e: print(f"Error logging relational crew IDs: {e}")
        
    try: scrape_pitch_arsenal.run()
    except Exception as e: print(f"Error recalculating long-term pitch profiles: {e}")

    print(f"\nPipeline execution successfully finished for processing window: {target_date}")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        run_pipeline_for_date(sys.argv[1])
    else:
        # Enforce the local timezone context 
        local_tz = pytz.timezone('America/Los_Angeles')
        current_time_local = datetime.now(local_tz)
        
        # Calculate yesterday's date relative to your time zone
        yesterday_local = current_time_local - timedelta(days=1)
        yesterday_str = yesterday_local.strftime('%Y-%m-%d')
        
        print(f"Server Time (UTC): {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Local Time (PT):   {current_time_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"Targeting finalized data window for: {yesterday_str}")
        
        run_pipeline_for_date(yesterday_str)
