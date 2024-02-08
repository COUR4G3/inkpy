"""Dump and load runtime-optimised serialised format.

---------------
ENCODING SCHEME
---------------

Glue:           "<>", "G<", "G>"

ControlCommand: "ev", "out", "/ev", "du" "pop", "->->", "~ret", "str", "/str", "nop",
                "choiceCnt", "turns", "visit", "seq", "thread", "done", "end"

NativeFunction: "+", "-", "/", "*", "%" "~", "==", ">", "<", ">=", "<=", "!=", "!"... etc

Void:           "void"

Value:          "^string value", "^^string value beginning with ^"
                5, 5.2
                {"^->": "path.target"}
                {"^var": "varname", "ci": 0}

Container:      [...]
                [...,
                    {
                        "subContainerName": ...,
                        "#f": 5,                     flags
                        "#n": "containerOwnName"     only if not redundant
                    }
                ]

Divert:         {"->": "path.target", "c": true }
                {"->": "path.target", "var": true}
                {"f()": "path.func"}
                {"->t->": "path.tunnel"}
                {"x()": "externalFuncName", "exArgs": 5}

Var Assign:     {"VAR=": "varName", "re": true}    reassignment
                {"temp=": "varName"}

Var ref:        {"VAR?": "varName"}
                {"CNT?": "stitch name"}

ChoicePoint:    {"*": pathString,
                "flg": 18 }

Choice:         Nothing too clever, it's only used in the save state,
                there's not likely to be many of them.

Tag:            {"#": "the tag text"}

"""

import json
import logging
import typing as t
import warnings

from .container import Container
from .object import InkObject
from .value import BoolValue, FloatValue, IntValue, StringValue, Value
from .void import Void


if t.TYPE_CHECKING:
    from .story import Story


INK_VERSION_CURRENT = 21
INK_VERSION_MINIMUM_COMPATIBLE = 18


logger = logging.getLogger(__name__)


def _dump(story: "Story", output: t.TextIO | None = None) -> str | None:
    root = dump_runtime_container(story.root_content_container)

    data = {
        "inkVersion": INK_VERSION_CURRENT,
        "root": root,
    }

    if output:
        json.dump(data, output)
    else:
        return data


def dump(story: "Story", output: t.TextIO):
    return _dump(story, output)


def dumps(story: "Story") -> str:
    return _dump(story)


def dump_runtime_container(container: Container):
    obj = []

    for content in container.content:
        obj.append(dump_runtime_object(obj))

    terminator = {}

    for name, content in container.named_only_content.items():
        terminator[name] = dump_runtime_object(content)

    if container.flags:
        terminator["#f"] = container.flags

    if container.name:
        terminator["#n"] = container.name

    if terminator:
        obj.append(terminator)

    return obj


def dump_runtime_object(obj: InkObject):
    # string values and newlines
    if isinstance(obj, StringValue):
        if obj.value == "\n":
            return "\n"
        else:
            return f"^{obj.value}"

    # basic types
    elif isinstance(obj, (BoolValue, FloatValue, IntValue)):
        return obj.value

    # void
    elif isinstance(obj, Void):
        return "void"

    # containers
    elif isinstance(obj, Container):
        return dump_runtime_container(obj)

    raise RuntimeError(f"Failed to convert runtime object to token: '{obj}'")


def load(data: dict | str | t.TextIO):
    if isinstance(data, str):
        data = json.loads(data)
    elif not isinstance(data, dict):
        data = json.load(data)

    try:
        version = int(data["inkVersion"])
    except KeyError:
        raise ValueError("Version of ink could not be found")
    except ValueError:
        raise ValueError(f"Version of ink value was invalid: {version!r}")

    if version > INK_VERSION_CURRENT:
        raise RuntimeError(
            "Version of ink used to build story was newer than the current version "
            "of the loader"
        )
    elif version < INK_VERSION_MINIMUM_COMPATIBLE:
        raise RuntimeError(
            "Version of ink used to build story is too old to be loaded by this "
            "version of the loader"
        )
    elif version != INK_VERSION_CURRENT:
        warnings.warn(
            "Version of ink used to build story doesn't match current version of "
            "loader. Non-critical, but recommend synchronising.",
            RuntimeWarning,
        )
    else:
        logger.debug("Version %s", version)

    if "root" not in data:
        raise ValueError("Root node for ink not found")

    root = load_runtime_container(root)

    list_defs = data.get("listDefs")

    return root, list_defs


def load_runtime_container(obj: list) -> Container:
    container = Container()

    *content, terminator = obj

    for obj in content:
        container.add_content(load_runtime_object(obj))

    for name, obj in terminator.items():
        if name == "#f":
            container.flags = obj
        elif name == "#n":
            container.name = obj
        else:
            container.add_named_content(obj, name)

    logger.debug(container.dump_string_hierachy())

    return container


def load_runtime_object(obj) -> InkObject:
    logger.debug(obj)

    if isinstance(obj, (bool, float, int)):
        return Value.create(obj)

    elif isinstance(obj, list):
        return load_runtime_container(obj)

    elif isinstance(obj, str):
        # strings and newlines
        if obj[0] == "^":
            return StringValue(obj[1:])
        elif obj == "\n":
            return StringValue(obj)

        # void
        if obj == "void":
            return Void()

    elif isinstance(obj, dict):
        pass

    if obj is None:
        return

    raise RuntimeError(f"Failed to convert token to runtime object: '{obj}'")


def loads(s: str):
    return load(s)
