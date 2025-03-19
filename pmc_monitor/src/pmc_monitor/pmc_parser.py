import builtins
import dataclasses
import logging
import re
import types
import typing
from dataclasses import dataclass
from typing import Any

from pmc_monitor.pmc_protocol import Message


def indent(msg: str, level: int):
    return f"{'  ' * level}{msg}"


@dataclass
class Some:
    x: Any


@dataclass
class ParseError:
    trace: list[str]
    rest: str


def abbreviate(text: str):
    lines = text.splitlines()
    if not lines:
        return text
    if len(lines) == 1:
        line = lines[0]
        if len(line) <= 23:
            return line
        return f"{line[:10]}...{line[-10:]}"
    return f"{lines[0][:10]}..({len(lines) - 2} more lines)..{lines[-1][-10:]}"


def parse_float(string: str):
    hex_float_re = r"[+-]?0x[\da-fA-F]+\.[\da-fA-F]+$"
    if re.match(hex_float_re, string):
        return Some(float.fromhex(string)), ""

    try:
        return Some(float(string)), ""
    except ValueError:
        pass

    return ParseError(["parse_float"], string)


def parse_int(string: str):
    hex_int_re = r"[+-]?0x[\da-fA-F]+$"
    if re.match(hex_int_re, string):
        return Some(int(string, 16)), ""

    try:
        return Some(int(string)), ""
    except ValueError:
        pass

    return ParseError(["parse_int"], string)


def parse_class_from_regex(typ, string: str, logger: logging.Logger, level: int):
    m = re.match(typ.regex, string)
    if m is None:
        logger.debug(
            indent(f"regex did not match: string='{abbreviate(string)}'", level)
        )
        return ParseError([f"parse_class_from_regex({typ})->match"], string)

    logger.debug(indent("regex matches", level))

    rest = string[m.end() :]

    groups = m.groupdict()

    instance_dict = {}
    for field in dataclasses.fields(typ):
        value_to_parse = groups.get(field.name)
        if value_to_parse is None:
            logger.error(
                f"Could not find data class field '{field.name}' in regex match groups ({groups.keys()})"
            )
            return ParseError(
                [f"parse_class_from_regex({typ})->groups.get({field.name})"], string
            )

        type_to_parse = field.type

        logger.debug(
            indent(
                f"parsing field {field.name}[{type_to_parse}] from '{abbreviate(value_to_parse)}'",
                level,
            )
        )
        match consume(type_to_parse, value_to_parse, logger, level + 1):
            case Some(x), _:
                instance_dict[field.name] = x
            case ParseError() as e:
                e.trace.append(
                    f"parse_class_from_regex({typ})->consume_field({field.name})"
                )

    logger.debug(
        indent(
            f"parsing {typ} through regex done, '{abbreviate(rest)}' left", level - 1
        )
    )
    return Some(typ(**instance_dict)), rest


def consume(
    typ, text: str, logger: logging.Logger, level=0
) -> tuple[Some, str] | ParseError:
    logger.debug(indent(f"consuming type {typ}, text='{abbreviate(text)}'", level))
    level += 1
    match typ:
        case builtins.str:
            logger.debug(indent(f"parsing string, text='{abbreviate(text)}'", level))
            return Some(text.strip()), ""
        case builtins.float:
            logger.debug(indent(f"parsing float, text='{abbreviate(text)}'", level))
            return parse_float(text.strip().replace("'", ""))
        case builtins.int:
            logger.debug(indent(f"parsing int, text='{abbreviate(text)}'", level))
            return parse_int(text.strip().replace("'", ""))
        case types.UnionType() as union:
            logger.debug(indent(f"parsing union, text='{abbreviate(text)}'", level))
            level += 1
            # Try to parse the alternatives in the union in order, and return the first successfully parsed object.
            # Only fail (return None) if the union is exhausted
            for argument_type in typing.get_args(union):
                logger.debug(
                    indent(f"trying {argument_type}, text='{abbreviate(text)}'", level)
                )
                match consume(argument_type, text, logger, level + 1):
                    case Some(x), rest:
                        return Some(x), rest
                    case ParseError():
                        continue
            union_string = " | ".join(map(str, typing.get_args(union)))
            return ParseError([f"consume(Union({union_string}))"], text)
        case _:
            if dataclasses.is_dataclass(typ):
                logger.debug(indent("parsing class through regex", level))
                return parse_class_from_regex(typ, text, logger, level + 1)

    logger.debug(indent("type not matching any pattern", -1))
    return ParseError([f"consume({typ})->match"], text)


def parse(text: str, logger: logging.Logger | None = None):
    if logger is None:
        logger = logging.getLogger("TLV parser")
        logger.setLevel(logging.INFO)

    outputs: list[Message] = []
    rest = text
    while rest:
        logger.debug(f"start parsing with text='{abbreviate(rest)}'")
        result = consume(Message, rest, logger, 1)
        match result:
            case Some(x), remainder:
                outputs.append(x)
                rest = remainder
                logger.debug(f"parsing {type(x)} succeeded")
            case ParseError() as e:
                raise RuntimeError(
                    "parsing failed:\n"
                    f"  last parsed: {outputs[-1] if outputs else None}\n"
                    f"  parse tree: {e.trace}\n"
                    f"  with text: '{rest}'\n"
                    f"  remainder: '{e.rest}'\n"
                    f"  original text: '{text}'\n"
                )

    return outputs
