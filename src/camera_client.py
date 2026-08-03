from typing import List, Optional
from datetime import datetime
from reolinkapi import Camera

class CameraClient:
    """
    A thin wrapper around the reolinkapi library to isolate 
    the analysis engine from external API changes.
    """
    def __init__(self, ip: str, username: str = "admin", password: str = "", **kwargs):
        # Allows extra kwargs if necessary for future-proofing or advanced options
        self.cam = Camera(ip, username, password, **kwargs)

    def get_playback_files(self, start_time: datetime, end_time: datetime, 
                             channel: int = 0) -> List[str]:
        """
        Retrieves a list of filenames for the specified time range.
        """
        return self.cam.get_playback_files(start=start_time, end=end_time, channel=channel)

    def fetch_file(self, filename: str, output_path: str = None) -> bool:
        # If no path is provided by the logic, we assume it's handled elsewhere or 
        # use a default. For now, keep it direct as per the sample.
        return self.cam.get_file(filename, output_path=output_path)
