"""Adapter for LinuxPTP configuration parsing."""

import argparse
from abc import ABC, abstractmethod
from configparser import ConfigParser
from dataclasses import dataclass, field


@dataclass(init=False)
class LinuxPtpConfig(ABC):
    """Abstract base class for LinuxPTP application configuration.

    Parses command-line arguments and configuration files in the same way
    that ptp4l and phc2sys do.

    Common config options shared between all LinuxPTP applications are handled
    here, while additional application-specific options are handled by subclasses.

    See Also:
        https://linux.die.net/man/8/ptp4l

    Attributes:
        config: The parsed ConfigParser instance.

    """

    config: ConfigParser = field(repr=False)

    def __init__(self, argv: list[str]) -> None:
        """Parse configuration from command-line arguments and configuration files.

        The default configuration file is expected at /etc/linuxptp/ptp4l.conf and should
        have been shipped with the LinuxPTP package. An additional configuration file can be
        specified with the `-f` command-line argument.

        Parameter precedence is as follows (highest to lowest):

        1. Command-line arguments
        2. User-specified configuration file (via `-f` argument)
        3. Default configuration file (/etc/linuxptp/ptp4l.conf)

        Args:
            argv: Command-line arguments including program name.

        """
        self.config = self._parse(argv)

    @abstractmethod
    def add_args_app_specific(self, parser: argparse.ArgumentParser) -> None:
        """Add application-specific arguments to the parser."""
        pass

    def validate_args_app_specific(self, args: argparse.Namespace) -> None:
        """Validate application-specific arguments."""
        return

    def override_app_specific(
        self, args: argparse.Namespace, config: ConfigParser
    ) -> list[str]:
        """Apply app-specific overrides, return list of handled arg names."""
        return []

    def validate_config_app_specific(self, config: ConfigParser) -> None:
        """Validate the final configuration."""
        return

    def _parse(self, argv: list[str]) -> ConfigParser:
        """Parse argv and config files into a ConfigParser."""
        if not argv:
            raise ValueError(
                "argv[] is expected to contain at least the program name but contains nothing"
            )

        parser = argparse.ArgumentParser(argv[0])
        parser.add_argument("-f", metavar="config", dest="config")
        parser.add_argument("--logging_level", "-l")
        self.add_args_app_specific(parser)

        args, _ = parser.parse_known_args(argv[1:])
        self.validate_args_app_specific(args)

        config_files = ["/etc/linuxptp/ptp4l.conf"]
        if args.config:
            config_files.append(args.config)

        config = ConfigParser(delimiters=["\t", " "])
        config.read(config_files)
        assert "global" in config.sections()

        if args.logging_level is not None:
            config["global"]["logging_level"] = args.logging_level

        overridden = ["config", *self.override_app_specific(args, config)]

        for k, v in vars(args).items():
            if k in overridden or v is None:
                continue
            config["global"][k] = str(v)

        log_level = int(config["global"]["logging_level"])
        if log_level < 6:
            raise ValueError(
                f"Cannot monitor LinuxPTP with a log level below 6 (current: {log_level})"
            )

        self.validate_config_app_specific(config)
        return config
