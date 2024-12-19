import builtins
from dataclasses import Field, dataclass
import logging
import re
import types
from typing import Any, List, Type
import typing
from pmc_monitor.pmc_protocol import Message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TLV parser")
logger.setLevel(logging.INFO)


def indent(msg: str, level: int):
    return f"{'  ' * level}{msg}"


@dataclass
class Some:
    x: Any


@dataclass
class ParseError:
    rest: str


def parse_float(string: str):
    hex_float_re = r"[+-]?0x[\da-fA-F]+\.[\da-fA-F]+$"
    if re.match(hex_float_re, string):
        return Some(float.fromhex(string))

    try:
        return Some(float(string))
    except ValueError:
        pass

    return None


def parse_int(string: str):
    hex_int_re = r"[+-]?0x[\da-fA-F]+$"
    if re.match(hex_int_re, string):
        return Some(int(string, 16))

    try:
        return Some(int(string))
    except ValueError:
        pass

    return None


def parse_class_from_regex(_type: Type, string: str, level):
    m = re.match(_type.regex, string)
    if m is None:
        logger.debug(
            indent(f"regex did not match: re='{_type.regex}', string='{string}'", level)
        )
        return None, string

    rest = string[m.end() :]

    groups = m.groupdict()

    level += 1

    instance_dict = {}
    for field_name, field_info in _type.__dataclass_fields__.items():
        field_name: str
        field_info: Field

        value_to_parse = groups.get(field_name)
        if value_to_parse is None:
            logger.error(
                f"Could not find data class field '{field_name}' in regex match groups ({groups.keys()})"
            )
            return None, string

        type_to_parse = field_info.type

        logger.debug(
            indent(
                f"parsing field {field_name}[{type_to_parse}] from '{value_to_parse}'",
                level,
            )
        )
        match consume(type_to_parse, value_to_parse, level + 1):
            case Some(x), _:
                instance_dict[field_name] = x
            case None, _:
                return None, string

    return Some(_type(**instance_dict)), rest


def consume(_type: Type, text: str, level=0):
    logger.debug(indent(f"consuming type {_type}, text='{text}'", level))
    level += 1
    match _type:
        case builtins.str:
            logger.debug(indent(f"parsing string, text='{text}'", level))
            return Some(text.strip()), ""
        case builtins.float:
            logger.debug(indent(f"parsing float, text='{text}'", level))
            return parse_float(text.strip().replace("'", "")), ""
        case builtins.int:
            logger.debug(indent(f"parsing int, text='{text}'", level))
            return parse_int(text.strip().replace("'", "")), ""
        case types.UnionType() as union:
            logger.debug(indent(f"parsing union, text='{text}'", level))
            level += 1
            # Try to parse the alternatives in the union in order, and return the first successfully parsed object.
            # Only fail (return None) if the union is exhausted
            for argument_type in typing.get_args(union):
                logger.debug(indent(f"trying {argument_type}, text='{text}'", level))
                match consume(argument_type, text, level + 1):
                    case Some(x), rest:
                        return Some(x), rest
                    case None, _:
                        continue
            return None, text
        case _:
            if hasattr(_type, "__dataclass_fields__"):
                logger.debug(indent("parsing class through regex", level))
                return parse_class_from_regex(_type, text, level + 1)

    logger.debug(indent("type not matching any pattern", -1))
    return None, text


def parse(text: str):
    outputs: List[Message | ParseError] = []
    rest = text
    while rest:
        logger.debug(f"start parsing with text='{text}'")
        message_opt, rest = consume(Message, rest, 1)
        match message_opt:
            case Some(x):
                outputs.append(x)
            case None:
                outputs.append(ParseError(rest))
                logger.error("parsing failed")
                break

    return outputs
