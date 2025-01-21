from enum import Enum
from diag_tree import Diagnosable, DiagnosableEnumMeta, DiagTree, Ok, Error


class SyncState(Diagnosable, Enum, metaclass=DiagnosableEnumMeta):
    SERVO_UNLOCKED = 0
    SERVO_JUMP = 1
    SERVO_LOCKED = 2
    SERVO_LOCKED_STABLE = 3

    def diagnose(self) -> DiagTree:
        match self:
            case SyncState.SERVO_LOCKED | SyncState.SERVO_LOCKED_STABLE:
                return Ok(f"Servo locked ({self.name})")
            case _:
                return Error(f"Servo not locked ({self.name})")