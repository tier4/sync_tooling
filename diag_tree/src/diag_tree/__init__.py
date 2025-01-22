from abc import ABC, ABCMeta, abstractmethod
from dataclasses import dataclass
import dataclasses
from enum import EnumMeta
from typing import Any, Dict, List


@dataclass
class Unknown:
    """Not all necessary information to produce a diagnostic status is present."""

    precedence = 1
    msg: str | None = None


@dataclass
class Ok:
    """No issues found"""

    precedence = 0
    msg: str | None = None


@dataclass
class Warning:
    """A non-critical issue was found"""

    precedence = 2
    msg: str


@dataclass
class Error:
    """A critical issue was found"""

    precedence = 3
    msg: str


DiagStatus = Unknown | Ok | Warning | Error

DiagTree = Dict[str, "DiagTree"] | List["DiagTree"] | DiagStatus


class DiagnosableEnumMeta(EnumMeta, ABCMeta):
    pass


class Diagnosable(ABC):
    @abstractmethod
    def diagnose(self) -> DiagTree:
        raise NotImplementedError()


def diagnose(obj: Any) -> DiagTree:
    match obj:
        case None:
            return Unknown()
        # Python does not allow to directly match union types 🥲
        case (Unknown() | Ok() | Warning() | Error()) as status:
            return status
        case list() as ls:
            return [diagnose(elem) for elem in ls]
        case dict() as d:
            return {k: diagnose(v) for k, v in d.items()}
        case Diagnosable() as diagnosable:
            return diagnosable.diagnose()
        case _:
            if dataclasses.is_dataclass(obj):
                return {obj.__class__.__name__: diagnose(dataclasses.asdict(obj))}  # type: ignore
            raise NotImplementedError(
                f"diagnose({type(obj).__qualname__}) is not implemented"
            )


def prettify(diag_tree: DiagTree, indent=0) -> str:
    lpad = "  " * indent

    match diag_tree:
        case (Unknown() | Ok() | Warning() | Error()) as status:
            text = status.__class__.__name__
            if status.msg is not None:
                text += f"({status.msg})"
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


def aggregate(diag_tree: DiagTree) -> DiagStatus:
    match diag_tree:
        case (Unknown() | Ok() | Warning() | Error()) as status:
            return status
        case [*subtrees]:
            if not subtrees:
                return Ok()

            max_status = max(map(aggregate, subtrees), key=lambda s: s.precedence)
            return max_status
        case {**subtrees}:
            if not subtrees:
                return Ok()

            max_status = max(
                map(aggregate, subtrees.values()), key=lambda s: s.precedence
            )
            return max_status
        case _:
            assert False
