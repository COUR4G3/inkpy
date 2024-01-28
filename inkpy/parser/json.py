import json
import typing as t
import warnings

from ..runtime.choice_point import ChoicePoint
from ..runtime.container import Container
from ..runtime.control_command import ControlCommand
from ..runtime.divert import Divert
from ..runtime.glue import Glue
from ..runtime.ink_list import InkList, InkListItem
from ..runtime.native_function_call import NativeFunctionCall
from ..runtime.path import Path
from ..runtime.push_pop import PushPopType
from ..runtime.tag import Tag
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


class JSONParser:
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

        return self._parse_token_to_object(root), data.get("listDefs", {})

    def _parse_array_to_container(self, array):
        container = Container()
        container.content = self._parse_array_to_objects(array, skip_last=True)

        if terminator := array[-1]:
            named_only_content = {}

            for key, value in terminator.items():
                if key == "#f":
                    container.count_flags = int(value)
                elif key == "#n":
                    container.name = str(value)
                else:
                    item = self._parse_token_to_object(value)
                    if isinstance(item, Container):
                        item.name = key
                    named_only_content[key] = item

            container.named_only_content = named_only_content

        return container

    def _parse_array_to_objects(self, array, skip_last=False):
        if skip_last:
            array = array[:-1]

        objects = []

        for token in array:
            obj = self._parse_token_to_object(token)

            objects.append(obj)

        return objects

    def _parse_token_to_object(self, token):
        if isinstance(token, (int, bool, float)):
            return Value.create(token)

        elif isinstance(token, str):
            # string value
            if token[0] == "^":
                return StringValue(token[1:])
            elif token == "\n":
                return StringValue(token)

            # glue
            if token == "<>":
                return Glue()

            # glue (older syntax)
            if token in ("G<", "G>"):
                return Glue()

            # control commands
            if ControlCommand.exists_with_name(token):
                return ControlCommand(token)

            # rename intersect native function to avoid conflict with string
            if token == "L^":
                token = "^"

            # native functions
            if NativeFunctionCall.call_exists_with_name(token):
                return NativeFunctionCall.call_with_name(token)

            # pop functions
            if token == "->->":
                return ControlCommand.PopTunnel()
            if token == "~ret":
                return ControlCommand.PopFunction()

            # void
            if token == "void":
                return Void()

        elif isinstance(token, dict):
            # divert value
            if value := token.get("^->"):
                return DivertTargetValue(Path(str(value)))

            # variable pointer value
            if value := token.get("^var"):
                pointer = VariablePointerValue(value)
                if value := token.get("ci"):
                    pointer.index = int(value)
                return pointer

            # divert
            is_divert = False
            pushes_to_stack = False
            div_push_type = PushPopType.Function
            external = False

            if value := token.get("->"):
                is_divert = True
            elif value := token.get("f()"):
                is_divert = True
                pushes_to_stack = True
                div_push_type = PushPopType.Function
            elif value := token.get("->t->"):
                is_divert = True
                pushes_to_stack = True
                div_push_type = PushPopType.Tunnel
            elif value := token.get("x()"):
                is_divert = True
                external = True
                pushes_to_stack = False
                div_push_type = PushPopType.Function

            if is_divert:
                divert = Divert()
                divert.pushes_to_stack = pushes_to_stack
                divert.stack_push_type = div_push_type
                divert.is_external = external

                target = str(value)

                if value := token.get("var"):
                    divert.variable_divert_name = target
                else:
                    divert.target_path_string = target

                divert.is_conditional = bool(token.get("c", False))

                if external:
                    if value := token.get("exargs"):
                        divert.external_args = int(value)

                return divert

            # choice
            if value := token.get("*"):
                choice = ChoicePoint()
                choice.path_string_on_choice = str(value)

                if value := token.get("flg"):
                    choice.flags = value

                return choice

            # variable reference
            if value := token.get("VAR?"):
                return VariableReference(str(value))
            elif value := token.get("CNT?"):
                read_count_var_ref = VariableReference()
                read_count_var_ref.path_string_for_count = str(value)
                return read_count_var_ref

            # variable assignment
            is_variable_assign = False
            is_global_variable = False

            if value := token.get("VAR="):
                is_variable_assign = True
                is_global_variable = True
            elif value := token.get("temp="):
                is_variable_assign = True
                is_global_variable = False

            if is_variable_assign:
                variable_name = str(value)
                is_new_decl = not token.get("re", False)
                variable_assign = VariableAssignment(variable_name, is_new_decl)
                variable_assign.is_global = is_global_variable
                return variable_assign

            # legacy tag with text
            if value := token.get("#"):
                return Tag(str(value))

            # list value
            if "list" in token:  # to handle empty lists
                list_content = token["list"]
                raw_list = InkList()
                if value := token.get("origins"):
                    raw_list.set_initial_origin_names(value)
                for key, val in list_content.items():
                    item = InkListItem(key)
                    raw_list[item] = val
                return ListValue(raw_list)

            # TODO: choice for serliazed save

        elif isinstance(token, list):
            return self._parse_array_to_container(token)

        elif token is None:
            return None

        raise RuntimeError(f"Failed to convert token to runtime object: '{token}'")
