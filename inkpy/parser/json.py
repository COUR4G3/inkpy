import logging
import json

import typing as t
import warnings

import json_stream

from ..runtime.choice_point import ChoicePoint
from ..runtime.container import Container
from ..runtime.control_command import ControlCommand
from ..runtime.divert import Divert
from ..runtime.glue import Glue
from ..runtime.ink_list import InkList, InkListItem
from ..runtime.native_function_call import NativeFunctionCall
from ..runtime.path import Path
from ..runtime.push_pop import PushPopType
from ..runtime.value import (
    DivertTargetValue,
    ListValue,
    StringValue,
    Value,
    VariablePointerValue,
)
from ..runtime.variable_assignment import VariableAssignment
from ..runtime.variable_reference import VariableReference
from ..runtime.void import Void


logger = logging.getLogger(__name__)


class JsonParser:
    """Parser for the "compiled" runtime-optimised JSON format.

    ----------------------
    JSON ENCODING SCHEME
    ----------------------

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

    INK_VERSION_CURRENT: int = 21
    INK_VERSION_MINIMUM_COMPATIBLE: int = 18

    def _check_version(self, version: int):
        if version > self.INK_VERSION_CURRENT:
            raise RuntimeError(
                "Version of ink used to build story was newer than the current version "
                "of the parser"
            )
        elif version < self.INK_VERSION_MINIMUM_COMPATIBLE:
            raise RuntimeError(
                "Version of ink used to build story is too old to be loaded by this "
                "version of the parser"
            )
        elif version != self.INK_VERSION_CURRENT:
            warnings.warn(
                "Version of ink used to build story doesn't match current version of "
                "parser. Non-critical, but recommend synchronising.",
                RuntimeWarning,
            )

    def parse(self, input: str | t.TextIO):
        if isinstance(input, str):
            data = json.loads(input)
        else:
            data = json.load(input)

        version = data.get("inkVersion")
        if not version:
            raise ValueError("Version of ink could not be found")

        try:
            version = int(version)
        except ValueError:
            raise ValueError(f"Version of ink could not be parsed: {version}")

        self._check_version(version)

        root = data.get("root")
        if not root:
            raise ValueError("Root node for ink not found")

        return self._parse_token_to_object(root), data.get("listDefs", [])

    def _parse_list_to_container(self, list):
        logger.debug("Parsing container: %s", str(list)[:50])

        container = Container()
        container.content = self._parse_list_to_obj_list(list, True)

        if terminator := list[-1]:
            named_only_content = {}

            for key, value in terminator.items():
                if key == "#f":
                    container.count_flags = int(value)
                elif key == "#n":
                    container.name = str(value)
                else:
                    named_content_item = self._parse_token_to_object(value)
                    if isinstance(named_content_item, Container):
                        named_content_item.name = key
                    named_only_content[key] = named_content_item

        return container

    def _parse_list_to_obj_list(self, list, skip_last: bool = False):
        logger.debug("Parsing object list: %s", str(list)[:50])

        obj_list = []

        if skip_last:
            list = list[:-1]

        for token in list:
            obj = self._parse_token_to_object(token)
            obj_list.append(obj)

        return obj_list

    def _parse_obj_to_choice(self, obj):
        logger.debug("Parsing choice: %s", str(obj)[:50])

        choice = Choice()
        choice.text = str(obj.get("text"))
        choice.index = int(obj.get("index"))
        choice.source_path = str(obj.get("original_choice_path"))
        choice.original_thread_index = int(obj.get("originalThreadIndex"))
        choice.path_string_on_choice = str(obj.get("targetPath"))
        if obj.get("tags"):
            choice.tags = obj.get("tags")
        return choice

    def _parse_token_to_object(self, token):
        logger.debug("Parsing token: %s", str(token)[:50])

        if isinstance(token, (int, float, bool)):
            return Value.create(token)

        if isinstance(token, str):
            first_char = token[0]
            if first_char == "^":
                return StringValue(token[1:])
            elif first_char == "\n" and len(token) == 1:
                return StringValue("\n")

            # Glue
            if token == "<>":
                return Glue()

            # Older Glue Encoding
            # if token in ("G<", "G>"):
            #     return Glue()

            # Control commands (Implemented hash set as per comments in ink / inkjs)
            if token in ControlCommand.CommandType._value2member_map_:
                return ControlCommand(token)

            # Native Functions
            if token == "L^":
                token = "^"
            if NativeFunctionCall.call_exists_with_name(token):
                return NativeFunctionCall.call_with_name(token)

            # Pop
            if token == "->->":
                return ControlCommand.PopTunnel()
            if token == "~ret":
                return ControlCommand.PopFunction()

            if token == "void":
                return Void()
        elif isinstance(token, dict):
            obj = t.cast(dict, token)

            # DivertTargetValue
            if value := obj.get("^->"):
                return DivertTargetValue(Path(str(value)))

            # VariablePointerValue
            if value := obj.get("^var"):
                pointer = VariablePointerValue(str(value))
                if "ci" in obj:
                    value = obj.get("ci")
                    pointer.index = int(value)
                return pointer

            # Divert
            is_divert = False
            pushes_to_stack = False
            div_push_type = PushPopType.Function
            external = False

            if value := obj.get("->"):
                is_divert = True
            elif value := obj.get("f()"):
                is_divert = True
                pushes_to_stack = True
                div_push_type = PushPopType.Function
            elif value := obj.get("->t->"):
                is_divert = True
                pushes_to_stack = True
                div_push_type = PushPopType.Tunnel
            elif value := obj.get("x()"):
                is_divert = True
                external = True
                pushes_to_stack = False
                div_push_type = PushPopType.Function

            if is_divert:
                divert = Divert(div_push_type)
                divert.pushes_to_stack = pushes_to_stack
                divert.is_external = external

                target = str(value)

                if value := obj.get("var"):
                    divert.variable_divert_name = target
                else:
                    divert.target_path_string = target

                divert.is_conditional = bool(obj.get("c"))

                if external:
                    if value := obj.get("exArgs"):
                        divert.external_args = int(value)

                return divert

            # Choice
            if value := obj.get("*"):
                choice = ChoicePoint()
                choice.path_string_on_choice = str(value)

                if value := obj.get("flg"):
                    choice.flags = int(value)

                return choice

            # Variable reference
            if value := obj.get("VAR?"):
                return VariableReference(str(value))
            elif value := obj.get("CNT?"):
                read_count_variable_reference = VariableReference()
                read_count_variable_reference.path_string_for_count = str(value)
                return read_count_variable_reference

            # Variable assignment
            is_variable_assignment = False
            is_global_variable = False

            if value := obj.get("VAR="):
                is_variable_assignment = True
                is_global_variable = True
            elif value := obj.get("temp="):
                is_variable_assignment = True
                is_global_variable = False

            if is_variable_assignment:
                name = str(value)
                is_new_decl = not obj.get("re")
                assignment = VariableAssignment(name, is_new_decl)
                assignment.is_global = is_global_variable
                return assignment

            # Tag
            if value := obj.get("#"):
                return Tag(str(value))

            # List value
            if "list" in obj:
                value = obj.get("list")
                raw = InkList()

                for key, val in obj["list"].items():
                    item = InkListItem(key)
                    val = int(val)
                    raw[item] = val

                if value := obj.get("origins"):
                    raw.set_initial_origin_names(value)

                return ListValue(raw)

            # Choice
            if obj.get("originalChoicePath"):
                return self._parse_obj_to_choice(obj)

        elif isinstance(token, list):
            # array is always a container
            return self._parse_list_to_container(token)

        if token is None:
            return

        raise RuntimeError(f"Failed to convert token to runtime object: {token}")
