from dataclasses import dataclass


@dataclass
class GleebsState:
    alarms_triggered: int = 0
    last_message_id: str = ""
