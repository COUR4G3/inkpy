import io
import json
import typing as t

from ..runtime.choice_point import ChoicePoint
from ..runtime.container import Container
from ..runtime.control_command import ControlCommand
from ..runtime.divert import Divert
from ..runtime.glue import Glue
from ..runtime.ink_list import InkList, InkListItem
from ..runtime.native_function_call import NativeFunctionCall
from ..runtime.object import InkObject
from ..runtime.path import Path
from ..runtime.push_pop import PushPopType
from ..runtime.tag import Tag
from ..runtime.value import (
    BoolValue,
    DivertTargetValue,
    FloatValue,
    IntValue,
    ListValue,
    StringValue,
    Value,
    VariablePointerValue,
)
from ..runtime.variable_assignment import VariableAssignment
from ..runtime.variable_reference import VariableReference
from ..runtime.void import Void


if t.TYPE_CHECKING:
    from ..runtime.story import Story


class JSONCompiler:
    """Compiler to compile runtime-optimised JSON format.

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

    def compile(self, story: "Story", output: t.Optional[t.TextIO]) -> t.Optional[str]:
        return_string = False
        if not output:
            output = io.StringIO()
            return_string = True

        with InkObject.disable_compact_strings():
            data = {
                "inkVersion": self.INK_VERSION_CURRENT,
                "root": self._dump_runtime_container(story._main_content_container),
                "listDefs": self._dump_list_definition(story.list_definitions),
            }

        json.dump(data, output, separators=(",", ":"))

        if return_string:
            return output.getvalue()

    def _dump_list_definition(self, list_definitions):
        return {}

    @classmethod
    def _dump_runtime_container(cls, container: Container, without_name: bool = False):
        data = []

        for content in container.content:
            data.append(cls.dump_runtime_object(content))

        named_only_content = container.named_only_content
        has_name_property = container.has_valid_name and not without_name

        has_terminator = (
            named_only_content or container.count_flags or has_name_property
        )

        if has_terminator:
            terminator_data = {}

            if named_only_content:
                for name, content in named_only_content.items():
                    terminator_data[name] = cls._dump_runtime_container(
                        content, without_name=True
                    )

            if container.count_flags > 0:
                terminator_data["#f"] = container.count_flags

            if has_name_property:
                terminator_data["#n"] = container.name

            data.append(terminator_data)
        else:
            data.append(None)

        return data

    @classmethod
    def dump_runtime_object(cls, obj: "InkObject"):
        if isinstance(obj, Container):
            return cls._dump_runtime_container(obj)

        if isinstance(obj, Divert):
            key = "->"
            if obj.is_external:
                key = "x()"
            elif obj.pushes_to_stack:
                if obj.stack_push_type == PushPopType.Function:
                    key = "f()"
                elif obj.stack_push_type == PushPopType.Tunnel:
                    key = "->t->"

            if obj.has_variable_target:
                target_string = obj.variable_divert_name
            else:
                target_string = obj.target_path_string

            data = {key: target_string}

            data[key] = target_string

            if obj.has_variable_target:
                data["var"] = True

            if obj.is_conditional:
                data["c"] = True

            if obj.external_args > 0:
                data["exArgs"] = obj.external_args

            return data

        if isinstance(obj, ChoicePoint):
            return {"*": obj.path_string_on_choice, "flg": obj.flags}

        if isinstance(obj, (BoolValue, FloatValue, IntValue)):
            return obj.value

        if isinstance(obj, StringValue):
            if obj.is_newline:
                return "\n"
            return f"^{obj.value}"

        if isinstance(obj, ListValue):
            cls._dump_ink_list(obj)

        if isinstance(obj, DivertTargetValue):
            return {"^->": str(obj.value)}

        if isinstance(obj, VariablePointerValue):
            return {"^var": obj.value, "ci": obj.index}

        if isinstance(obj, Glue):
            return "<>"

        if isinstance(obj, ControlCommand):
            return obj.type.value

        if isinstance(obj, NativeFunctionCall):
            name = obj.name

            # avoid collision with ^ used to indicate a string
            if name == "^":
                name = "L^"

            return name

        if isinstance(obj, VariableReference):
            if read_count_path := obj.path_string_for_count:
                return {"CNT?": read_count_path}
            else:
                return {"VAR?": obj.name}

        if isinstance(obj, VariableAssignment):
            data = {}

            if obj.is_global:
                data["VAR="] = obj.variable_name
            else:
                data["temp="] = obj.variable_name

            if not obj.is_new_decl:
                data["re"] = True

            return data

        if isinstance(obj, Void):
            return "void"

        if isinstance(obj, Tag):
            return {"#": obj.text}

        raise RuntimeError(f"Failed to write runtime object to JSON: {obj}")
