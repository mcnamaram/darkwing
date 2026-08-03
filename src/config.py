from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    TOWER_ID = os.getenv("DARKWING_TOWER_ID", "T1")
    START_HOUR = int(os.getenv("DARKWING_START_HOUR", "6"))
    END_HOUR = int(os.getenv("DARKWING_END_HOUR", "21"))
    SCAN_DURATION_MINUTES = int(os.getenv("DARKWING_SCAN_DURATION", "19"))
    SAMPLE_INTERVAL_MINUTES = int(os.getenv("DARKWING_SAMPLE_INTERVAL", "20"))

config = Config()
