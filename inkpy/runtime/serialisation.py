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

from __future__ import annotations

import json
import logging
import typing as t

from .call_stack import PushPopType
from .container import Container
from .divert import Divert
from .glue import Glue
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
        json.dump(data, output, separators=(",", ":"))
    else:
        return json.dumps(data, separators=(",", ":"))


def dump(story: "Story", output: t.TextIO):
    return _dump(story, output)


def dumps(story: "Story") -> str:
    return _dump(story)


def dump_runtime_container(container: Container):
    obj = []

    for content in container.content:
        obj.append(dump_runtime_object(content))

    terminator = {}

    for name, content in container.named_only_content.items():
        terminator[name] = dump_runtime_object(content)

    if container.flags:
        terminator["#f"] = container.flags

    if container.name:
        terminator["#n"] = container.name

    if terminator or obj:
        obj.append(terminator or None)

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

    elif isinstance(obj, Glue):
        return "<>"

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
        raise ValueError(f"Version of ink value was malformed: {data['inkVersion']!r}")

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
        logger.warning(
            "Version of ink used to build story doesn't match current version of "
            "loader. Non-critical, but recommend synchronising.",
        )

    logger.debug("Loading ink runtime with version %s", version)

    if "root" not in data:
        raise ValueError("Root node for ink not found")

    root = load_runtime_container(data["root"])

    list_defs = data.get("listDefs")

    return root, list_defs


def load_runtime_container(obj: list) -> Container:
    container = Container()

    for content in obj[:-1]:
        container.add_content(load_runtime_object(content))

    if obj and (terminator := obj[-1]):
        for name, content in terminator.items():
            if name == "#f":
                container.flags = content
            elif name == "#n":
                container.name = content
            else:
                content = load_runtime_object(content)
                container.add_named_content(content, name)

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
        if obj and obj[0] == "^":
            return StringValue(obj[1:])
        elif obj == "\n":
            return StringValue(obj)

        # glue
        if obj == "<>":
            return Glue()

        # void
        if obj == "void":
            return Void()

    elif isinstance(obj, dict):
        # TODO: divert target value

        # TODO: variable pointer

        # divert
        is_divert = False
        pushes_to_stack = False
        stack_push_type = PushPopType.Function
        is_external = False

        if value := obj.get("->"):
            is_divert = True
        if value := obj.get("f()"):
            is_divert = True
            pushes_to_stack = True
        if value := obj.get("->t->"):
            is_divert = True
            pushes_to_stack = True
            stack_push_type = PushPopType.Tunnel
        if value := obj.get("x()"):
            is_divert = True
            is_external = True

        if is_divert:
            divert = Divert()
            divert.pushes_to_stack = pushes_to_stack
            divert.stack_push_type = stack_push_type
            divert.is_external = is_external

            target = str(value)

            if value := obj.get("var"):
                divert.variable_divert_name = target
            else:
                divert.target_path_string = target

            divert.is_conditional = obj.get("c", False)

            if is_external:
                if value := obj.get("exArgs"):
                    divert.external_args = int(value)

            return divert

    if obj is None:
        return

    raise RuntimeError(f"Failed to convert token to runtime object: '{obj}'")


def loads(s: str):
    return load(s)
