from abc import ABC, abstractmethod
from dataclasses import dataclass
import dataclasses
from typing import Any, Dict, List


@dataclass
class Unknown:
    """Not all necessary information to produce a diagnostic status is present."""

    msg: str | None = None


@dataclass
class Ok:
    """No issues found"""

    msg: str | None = None


@dataclass
class Warning:
    """A non-critical issue was found"""

    msg: str


@dataclass
class Error:
    """A critical issue was found"""

    msg: str


DiagStatus = Unknown | Ok | Warning | Error

DiagTree = Dict[str, "DiagTree"] | List["DiagTree"] | DiagStatus


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
            raise NotImplementedError()
