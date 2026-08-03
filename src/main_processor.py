# src/main_processor.py
import csv
from datetime import datetime
from typing import List

# Local modules defined in the project (assuming they are in the same package scope)
from scheduler import generate_sampling_schedules
# Import the stub function from our analysis engine
from analysis_engine import TimeSegment, process_video_segment # Note: We use the mock version for now!


def run_pipeline() -> None:
    """
    Main entry point. Runs the data collection pipeline end-to-end using the current 
    mocked components to generate a System Log CSV suitable for Google Forms review.
    """
    print("======== DARKWING PROJECT START ========")
    
    # 1. Generate Schedule (Phase 2)
    schedule = generate_sampling_schedules()
    if not schedule:
        print("[ERROR] Failed to generate a time schedule. Exiting.")
        return

    all_sighting_records = []
    total_segments = len(schedule)
    print(f"✅ Schedule generated: {total_segments} segments planned for analysis.")

    # 2. Process Segments (Phases 3 & 4 combined in the mock run)
    for i, segment in enumerate(schedule):
        print(f"\n[STEP {i+1}/{total_segments}] Running Analysis for: {segment['sample_time_edt']}...")

        # Call the core analysis function (using the MOCK implementation)
        sighting_results = process_video_segment(segment)
        
        if sighting_results:
            print(f"  -> SUCCESS: Found {len(sighting_results)} detection event(s).")
            for s in sighting_results:
                # We record the data point for logging
                all_sighting_records.append({
                    'tower_id': 'T1',
                    'date': segment['date'],
                    'sample_time': segment['sample_time_edt'], # Time reported to forms
                    'first_detection_ts': s.detection_timestamp_edt.strftime('%H:%M:%S'), # Time recorded internally (the precise sighting)
                    'confidence': f"{s.confidence_score:.2f}",
                    'behavioral_flag': s.behavioral_notes or "N/A",
                    'raw_segment_id': segment['task_id']
                })
        else:
            print("  -> INFO: No swifts detected in this window.")
            # Always log a record even if nothing was found (to fulfill form requirement)
            all_sighting_records.append({
                    'tower_id': 'T1',
                    'date': segment['date'],
                    'sample_time': segment['sample_time_edt'],
                    'first_detection_ts': None, # Explicitly no detection timestamp
                    'confidence': "0.00",
                    'behavioral_flag': "ZERO SWIFTS PRESENT AT SAMPLE TIME.",
                    'raw_segment_id': segment['task_id']
                })

    # 3. Output to System Log (Phase 4 Complete)
    output_file = f"SystemLog_{datetime.date.today()}.csv"
    fieldnames = list(all_sighting_records[0].keys())

    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_sighting_records)

    print("\n=============================================")
    print("✅ PIPELINE COMPLETE:")
    print(f"System Log containing {len(all_sighting_records)} records written to: {output_file}")
    print("This CSV is ready for manual review and eventual Google Form import.")


if __name__ == '__main__':
    run_pipeline()