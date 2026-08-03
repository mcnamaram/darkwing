# src/scheduler.py
import datetime
from typing import List, Dict

# --- CONFIGURATION (Needs to be pulled from config/settings.yaml eventually) ---
TOWER_ID = "T1" 
START_HOUR_EDT = 6  # 06:00 EDT
END_HOUR_EDT = 21    # 21:00 EDT
SCAN_DURATION_MINUTES = 19 # Scan window lasts up to 19 minutes (e.g., 7:00 to 7:19)
SAMPLE_INTERVAL_MINUTES = 20 # Sampling check occurs every 20 minutes

def generate_sampling_schedules() -> List[Dict]:
    """
    Generates the complete list of time windows to analyze for a single tower.
    Adheres strictly to the Google Form 'look ahead' protocol (T_start to T_start + 19 mins).
    Returns a list of dictionaries, each containing mandatory info for analysis.
    """
    schedules = []
    current_time = datetime.datetime(2026, 8, 3, START_HOUR_EDT, 0, 0) # Using the date contextually provided by initial setup file

    # Loop through each sampling time (6:00, 6:20, 6:40, etc.)
    while current_time.hour < END_HOUR_EDT:
        t_start = current_time
        
        # Calculate the end bound for the scan window (19 minutes later)
        # We must handle potential hour rollovers gracefully.
        dt_end = t_start + datetime.timedelta(minutes=SAMPLE_INTERVAL_MINUTES)
        t_end = dt_end

        if t_end > datetime.datetime(2026, 8, 3, END_HOUR_EDT + 1): # Stop if scan goes past the end of day
            break

        schedule = {
            "tower_id": TOWER_ID,
            "date": t_start.strftime("%Y-%m-%d"),
            "sample_time_edt": t_start.strftime("%H:%M"), # The time reported to the form (e.g., 7:00)
            "scan_window_start": t_start.isoformat(), # Full ISO timestamp for video read API
            "scan_window_end": t_end.isoformat(),   # Full ISO timestamp for video read API
            "task_id": f"{TOWER_ID}-{t_start.strftime('%Y%m%d')}-{t_start.strftime('%H%M')}" # Unique ID for tracking
        }
        schedules.append(schedule)

        # Advance to the next 20-minute sampling point
        current_time += datetime.timedelta(minutes=SAMPLE_INTERVAL_MINUTES)
    
    return schedules


if __name__ == '__main__':
    print("--- Generated Sampling Schedule Report ---")
    schedules = generate_sampling_schedules()
    for i, s in enumerate(schedules):
        print(f"[{i+1}] ID: {s['task_id']} | Time Reported: {s['sample_time_edt']}: The scan covers {datetime.datetime.fromisoformat(s['scan_window_start']).strftime('%H:%M')} to {datetime.datetime.fromisoformat(s['scan_window_end']).strftime('%H:%M')}.")

    print("\\nSUCCESS: Schedule generation complete. Next step: Implement the video access layer (Stage 3).")