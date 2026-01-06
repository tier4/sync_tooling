# Copyright 2025 TIER IV, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Parser for PMC (PTP Management Client) text output."""

import builtins
import dataclasses
import logging
import re
import types
import typing
from dataclasses import dataclass
from typing import Any

from pmc_monitor.pmc_protocol import Message

hex_float_re = re.compile(r"[+-]?0x[\da-fA-F]+\.[\da-fA-F]+$")
hex_int_re = re.compile(r"[+-]?0x[\da-fA-F]+$")


def indent(msg: str, level: int):
    """Indent a message for debug logging."""
    return f"{'  ' * level}{msg}"


@dataclass
class Some:
    """Type representing a value in an option-like pattern.

    Example:
        ```
        result: Some | None = Some(42)
        match result:
            case Some(x):
                print(f"Got value: {x}")
            case None:
                print("No value")
        ```

    Attributes:
        x: The parsed value.

    """

    x: Any


@dataclass
class ParseError:
    """Represents a parse failure with trace information.

    Attributes:
        trace: Stack of parser contexts where the error occurred.
        rest: Remaining unparsed text.

    """

    trace: list[str]
    rest: str


def abbreviate(text: str):
    """Abbreviate long text for debug output."""
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
    """Parse a float from string, supporting hex and decimal floats."""
    if re.match(hex_float_re, string):
        return Some(float.fromhex(string)), ""

    try:
        return Some(float(string)), ""
    except ValueError:
        pass

    return ParseError(["parse_float"], string)


def parse_int(string: str):
    """Parse an int from string, supporting hex and decimal ints."""
    if re.match(hex_int_re, string):
        return Some(int(string, 16)), ""

    try:
        return Some(int(string)), ""
    except ValueError:
        pass

    return ParseError(["parse_int"], string)


def parse_class_from_regex(typ, string: str, logger: logging.Logger, level: int):
    """Parse a dataclass from string using its `regex` attribute."""
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
    """Consume and parse a value of the given type from text."""
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


def parse(text: str, logger: logging.Logger | None = None) -> list[Message]:
    """Parse PMC output text into a list of messages.

    Args:
        text: Raw PMC output text to parse.
        logger: Optional logger for debug output.

    Returns:
        List of parsed Message objects.

    """
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
            case ParseError():
                try:
                    next_linebreak = rest.index("\n")
                    rest = rest[next_linebreak + 1 :]
                except ValueError:
                    rest = ""

    return outputs
