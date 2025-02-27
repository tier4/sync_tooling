from enum import Enum
from diag_tree import Diagnosable, DiagnosableEnumMeta
from sync_tooling_msgs.diag_status_pb2 import DiagStatus
from sync_tooling_msgs.diag_tree_pb2 import DiagTree
from sync_tooling_msgs.ok_pb2 import Ok
from sync_tooling_msgs.error_pb2 import Error


class SyncState(Diagnosable, Enum, metaclass=DiagnosableEnumMeta):
    SERVO_UNLOCKED = 0
    SERVO_JUMP = 1
    SERVO_LOCKED = 2
    SERVO_LOCKED_STABLE = 3

    def diagnose(self) -> DiagTree:
        match self:
            case SyncState.SERVO_LOCKED | SyncState.SERVO_LOCKED_STABLE:
                return DiagTree(status=DiagStatus(ok=Ok(msg=f"Servo locked ({self.name})")))
            case _:
                return DiagTree(status=DiagStatus(error=Error(msg=f"Servo not locked ({self.name})")))