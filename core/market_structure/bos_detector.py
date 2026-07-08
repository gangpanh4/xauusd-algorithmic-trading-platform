from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BOSEvent:
    """
    Event that occurs during the BOS detection process.
    """
    event_type: str
    timestamp: datetime


@dataclass(frozen=True)
class BOSDetectorConfig:
    """
    Configuration parameters for the BOS Detector.
    """
    param1: int
    param2: float


@dataclass
class BOSDetectorState:
    """
    State of the BOS Detector.
    """
    current_state: str
    last_event_time: datetime


class BOSDetector:
    def __init__(self, config: BOSDetectorConfig):
        self.config = config
        self.state = BOSDetectorState(current_state="ACTIVE", last_event_time=datetime.now())

    def detect_bos(self) -> BOSEvent | None:
        # Placeholder for BOS detection logic
        if self.state.current_state == "ACTIVE":
            return BOSEvent(event_type="DETECTED", timestamp=datetime.now())
        return None

    def clear_bos(self):
        self.state = BOSDetectorState(current_state="INACTIVE", last_event_time=datetime.now())
