from abc import ABC, ABCMeta, abstractmethod
import dataclasses
from enum import EnumMeta
from typing import Any
from sync_tooling_msgs.diag_status_pb2 import DiagStatus
from sync_tooling_msgs.diag_tree_pb2 import DiagTree
from sync_tooling_msgs.unknown_pb2 import Unknown
from sync_tooling_msgs.ok_pb2 import Ok
from sync_tooling_msgs.warning_pb2 import Warning
from sync_tooling_msgs.error_pb2 import Error


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
        case Unknown():
            return DiagTree(status=DiagStatus(unknown=obj))
        case Ok():
            return DiagTree(status=DiagStatus(ok=obj))
        case Warning():
            return DiagTree(status=DiagStatus(warning=obj))
        case Error():
            return DiagTree(status=DiagStatus(error=obj))
        case DiagStatus():
            return DiagTree(status=obj)
        case DiagTree():
            return obj
        case list() as ls:
            return DiagTree(list=DiagTree.DiagList([diagnose(elem) for elem in ls]))
        case dict() as d:
            return DiagTree(
                map=DiagTree.DiagMap({k: diagnose(v) for k, v in d.items()})
            )
        case Diagnosable() as diagnosable:
            return diagnosable.diagnose()
        case _:
            if dataclasses.is_dataclass(obj):
                cls = obj.__class__.__name__  # type: ignore
                mapping = dataclasses.asdict(obj)  # type: ignore
                return diagnose({cls: diagnose(mapping)})
            raise NotImplementedError(
                f"diagnose({type(obj).__qualname__}) is not implemented"
            )


def prettify(diag_tree: DiagTree, indent=0) -> str:
    lpad = "  " * indent

    match diag_tree:
        case DiagTree(status=DiagStatus() as status):
            obj: Unknown | Ok | Warning | Error = getattr(
                status, status.WhichOneof("status")
            )
            text = obj.__class__.__name__
            if obj.msg is not None:
                text += f"({obj.msg})"
            return lpad + text
        case [*subtrees]:
            if not subtrees:
                return lpad + "[]"

            lf = "\n"
            return f"{lpad}[\n{lf.join([prettify(t, indent + 1) for t in subtrees])}\n{lpad}]"
        case {**subtrees}:
            if not subtrees:
                return lpad + "{}"

            lf = "\n"
            return f"{lpad}{{\n{lf.join([f'{k}: {prettify(t, indent + 1)}' for k, t in subtrees.items()])}\n{lpad}}}"
        case _:
            assert False


def precedence(status: DiagStatus) -> int:
    match status:
        case DiagStatus(unknown=Unknown()):
            return 0
        case DiagStatus(ok=Ok()):
            return 1
        case DiagStatus(warning=Warning()):
            return 2
        case DiagStatus(error=Error()):
            return 3


def aggregate(diag_tree: DiagTree) -> DiagStatus:
    match diag_tree:
        case DiagTree(status=status):
            return status
        case DiagTree(list=DiagTree.DiagList(list=subtrees)):
            if not subtrees:
                return DiagStatus(ok=Ok())

            max_status = max(map(aggregate, subtrees), key=precedence)
            return max_status
        case DiagTree(map=DiagTree.DiagMap(map={**subtrees})):
            if not subtrees:
                return DiagStatus(ok=Ok())

            max_status = max(map(aggregate, subtrees.values()), key=precedence)
            return max_status
        case _:
            assert False
