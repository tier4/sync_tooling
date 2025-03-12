import argparse
from abc import ABC, abstractmethod
from configparser import ConfigParser
from dataclasses import dataclass, field


@dataclass(init=False)
class LinuxPtpConfig(ABC):
    config: ConfigParser = field(repr=False)

    def __init__(self, argv: list[str]) -> None:
        self.config = self._parse(argv)

    @abstractmethod
    def add_args_app_specific(self, parser: argparse.ArgumentParser) -> None:
        pass

    def validate_args_app_specific(self, args: argparse.Namespace) -> None:
        return

    def override_app_specific(
        self, args: argparse.Namespace, config: ConfigParser
    ) -> list[str]:
        return []

    def validate_config_app_specific(self, config: ConfigParser) -> None:
        return

    def _parse(self, argv: list[str]) -> ConfigParser:
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
