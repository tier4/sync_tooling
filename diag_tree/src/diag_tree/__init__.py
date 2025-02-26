from abc import ABC, ABCMeta, abstractmethod
import dataclasses
from enum import EnumMeta
from typing import Any

from sync_tooling_msgs.diag_status_pb2 import DiagStatus
from sync_tooling_msgs.diag_tree_pb2 import DiagTree
from sync_tooling_msgs.ok_pb2 import Ok
from sync_tooling_msgs.warning_pb2 import Warning
from sync_tooling_msgs.error_pb2 import Error
from sync_tooling_msgs.unknown_pb2 import Unknown


def precedence(status: DiagStatus) -> int:
    match status.WhichOneof("status"):
        case "ok":
            return 0
        case "unknown":
            return 1
        case "warning":
            return 2
        case "error":
            return 3
    raise ValueError()


class DiagnosableEnumMeta(EnumMeta, ABCMeta):
    pass


class Diagnosable(ABC):
    @abstractmethod
    def diagnose(self) -> DiagTree:
        raise NotImplementedError()


def diagnose(obj: Any) -> DiagTree:
    match obj:
        case None:
            return DiagTree(status=DiagStatus(unknown=Unknown()))
        case DiagStatus() as status:
            return DiagTree(status=status)
        case list() as ls:
            return DiagTree(
                list=DiagTree.DiagList(list=[diagnose(elem) for elem in ls])
            )
        case dict() as d:
            return DiagTree(
                map=DiagTree.DiagMap(map={k: diagnose(v) for k, v in d.items()})
            )
        case Diagnosable() as diagnosable:
            return diagnosable.diagnose()
        case _:
            if dataclasses.is_dataclass(obj):
                return diagnose({obj.__class__.__name__: dataclasses.asdict(obj)})  # type: ignore
            raise NotImplementedError(
                f"diagnose({type(obj).__qualname__}) is not implemented"
            )


def prettify(diag_tree: DiagTree, indent=0) -> str:
    lpad = "  " * indent

    match diag_tree.WhichOneof("tree"):
        case "status":
            status = diag_tree.status
            field = status.WhichOneof("status")
            if field is None:
                raise ValueError("No status set")

            status_value: Ok | Warning | Error | Unknown = getattr(status, field)
            text = status_value.__class__.__name__
            if status_value.msg is not None:
                text += f"({status_value.msg})"
            return lpad + text
        case "list":
            subtrees = diag_tree.list.list
            if not subtrees:
                return lpad + "[]"

            lf = "\n"
            return f"{lpad}[\n{lf.join([prettify(t, indent + 1) for t in subtrees])}\n{lpad}]"
        case "map":
            subtrees = diag_tree.map.map
            if not subtrees:
                return lpad + "{}"

            lf = "\n"
            return f"{lpad}{{\n{lf.join([f'{k}: {prettify(t, indent + 1)}' for k, t in subtrees.items()])}\n{lpad}}}"
    raise ValueError()


def aggregate(diag_tree: DiagTree) -> DiagStatus:
    match diag_tree.WhichOneof("tree"):
        case "status":
            return diag_tree.status
        case "list":
            subtrees = diag_tree.list.list
            if not subtrees:
                return DiagStatus(ok=Ok())

            max_status = max(map(aggregate, subtrees), key=precedence)
            return max_status
        case "map":
            subtrees = diag_tree.map.map
            if not subtrees:
                return DiagStatus(ok=Ok())

            max_status = max(map(aggregate, subtrees.values()), key=precedence)
            return max_status
        case _:
            assert False
