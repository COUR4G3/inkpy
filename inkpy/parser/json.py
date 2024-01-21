import json
import json_stream

import typing as t
import warnings


class JsonParser:
    INK_VERSION_CURRENT: int = 21
    INK_VERSION_MINIMUM_COMPATIBLE: int = 18

    def _check_version(self, version: int):
        if version > self.INK_VERSION_CURRENT:
            raise RuntimeError(
                "Version of ink used to build story was newer than the current version "
                "of the engine"
            )
        elif version > self.INK_VERSION_MINIMUM_COMPATIBLE:
            raise RuntimeError(
                "Version of ink used to build story is too old to be loaded by this "
                "version of the engine"
            )
        elif version != self.INK_VERSION_CURRENT:
            warnings.warn(
                "Version of ink used to build story doesn't match current version of "
                "engine. Non-critical, but recommend synchronising.",
                RuntimeWarning,
            )

    def parse(self, input: str | t.TextIO):
        if isinstance(input, str):
            data = json.loads(input)
        else:
            data = json_stream.load(input)

        version = data.get("inkVersion")
        if not version:
            raise ValueError("Version of ink could not be found")

        try:
            version = int(version)
        except ValueError:
            raise ValueError(f"Version of ink could not be parsed: {version}")

        self._check_version(version)

        if "root" not in data:
            raise ValueError("Root node for ink not found")

        return data["root"], data.get("listDefs", [])
