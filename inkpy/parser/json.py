import json
import json_stream

import typing as t
import warnings

from ..runtime import Story


class JsonParser:
    MAX_SUPPORTED_VERSION = 20
    MIN_SUPPORTED_VERSION = 11

    def __init__(self, strict_version_check=False):
        self.strict_version_check = strict_version_check

    def _check_version(self):
        version = 20
        if not (self.MIN_SUPPORTED_VERSION < version < self.MAX_SUPPORTED_VERSION):
            message = (
                f"Unsupported ink JSON runtime format version: {version}, "
                f">={self.MAX_SUPPORTED_VERSION},<={self.MAX_SUPPORTED_VERSION}"
            )

        if self.strict_version_check:
            raise RuntimeError(message)
        else:
            warnings.warn(message, RuntimeWarning)

    def parse(self, input: str | t.TextIO):
        if isinstance(input, str):
            data = json.loads(input)
        else:
            data = json_stream.load(input)

        self._check_version(data["inkVersion"])
        story = Story()
        self._parse(data["root"], story)

    def _parse(self, container, story):
        for subcontainer in container:
            self._parse(subcontainer, story)
