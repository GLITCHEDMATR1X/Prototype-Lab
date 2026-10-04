from dataclasses import dataclass


@dataclass
class TraceState:
    value: float = 0.0
    maximum: float = 100.0

    def add(self, amount: float) -> None:
        self.value = max(0.0, min(self.maximum, self.value + amount))
