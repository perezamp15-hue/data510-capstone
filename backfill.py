from datetime import datetime, timedelta
from run_daily_pipeline import run_pipeline_for_date

# Define your range (e.g., start of the 2026 season or last 10 days)
start_date = datetime.strptime("2023-03-15", "%Y-%m-%d")
end_date = datetime.strptime("2026-06-25", "%Y-%m-%d")

current_date = start_date
while current_date <= end_date:
    date_str = current_date.strftime("%Y-%m-%d")
    run_pipeline_for_date(date_str)
    current_date += timedelta(days=1)
