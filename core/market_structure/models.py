from dataclasses import dataclass, field
from datetime import datetime

# Existing classes and definitions below...

@dataclass(frozen=True, slots=True)
class BOSEvent:
    """
    Represents an event detected by the Break of Structure (BOS) detector.
    """

    timestamp: datetime
    break_type: BreakType
    swing_point: SwingPoint
    confirmation_index: int
