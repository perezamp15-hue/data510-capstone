import sys
import os

# 1. MOVED TO THE ABSOLUTE TOP: Inject scripts directory into Python's path list
scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

# 2. Now Python can safely look inside /app/scripts/ to resolve these modules
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
import scrape_transactions

from datetime import datetime, timedelta
import pytz

def run_pipeline_for_date(target_date=None):
    if not target_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        target_date = (datetime.now(local_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
        
    print(f"\n=========================================")
    print(f"RUNNING CRON-READY PIPELINE FOR: {target_date}")
    print(f"=========================================\n")
    
    try: scrape_teams.run()
    except Exception as e: print(f"Teams sync failed: {e}")
        
    try: scrape_park_info.run()
    except Exception as e: print(f"Parks sync failed: {e}")
        
    try: scrape_rosters.run(season=2026)
    except Exception as e: print(f"Roster sync failed: {e}")

    # --- SWAPPED: game_feed runs BEFORE schedule to ensure valid game_pks exist ---
    try: scrape_game_feed.run(target_date)
    except Exception as e:
        print(f"CRITICAL: Main Feed failed for {target_date}: {e}")
        return

    try: scrape_schedule.run(season=2026)
    except Exception as e: print(f"Schedule sync failed: {e}")
    # ------------------------------------------------------------------------------

    try: scrape_statcast.run(target_date, target_date)
    except Exception as e: print(f"Statcast failed: {e}")
        
    try: scrape_lineups.run(target_date)
    except Exception as e: print(f"Lineups failed: {e}")
        
    try: scrape_defense.run(target_date)
    except Exception as e: print(f"Defense failed: {e}")
        
    try: scrape_bullpen.run(target_date)
    except Exception as e: print(f"Bullpen failed: {e}")
        
    try: scrape_weather.run(target_date)
    except Exception as e: print(f"Weather failed: {e}")
        
    try: scrape_umpires.run(target_date)
    except Exception as e: print(f"Umpires failed: {e}")
        
    try: scrape_transactions.run(target_date)
    except Exception as e: print(f"Transactions failed: {e}")
        
    try: scrape_pitch_arsenal.run()
    except Exception as e: print(f"Arsenal update failed: {e}")

    print(f"\nPipeline execution successfully finished for window: {target_date}")

if __name__ == '__main__':
    passed_date = sys.argv[1] if len(sys.argv) > 1 else None
    run_pipeline_for_date(passed_date)
