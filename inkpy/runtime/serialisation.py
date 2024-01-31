"""Dump and load serialised structured data objects.

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

import io
import json
import typing as t

from .choice_point import ChoicePoint
from .container import Container
from .control_command import ControlCommand
from .divert import Divert
from .glue import Glue
from .ink_list import InkList, InkListItem
from .native_function_call import NativeFunctionCall
from .object import InkObject
from .path import Path
from .push_pop import PushPopType
from .tag import Tag
from .value import (
    BoolValue,
    DivertTargetValue,
    FloatValue,
    IntValue,
    ListValue,
    StringValue,
    Value,
    VariablePointerValue,
)
from .variable_assignment import VariableAssignment
from .variable_reference import VariableReference
from .void import Void


def dump_list_definition(list_definitions):
    return {}


def dump_runtime_container(container: Container, without_name: bool = False):
    data = []

    for content in container.content:
        data.append(dump_runtime_object(content))

    named_only_content = container.named_only_content
    has_name_property = container.has_valid_name and not without_name

    has_terminator = named_only_content or container.count_flags or has_name_property

    if has_terminator:
        terminator_data = {}

        if named_only_content:
            for name, content in named_only_content.items():
                terminator_data[name] = dump_runtime_container(
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


def dump_runtime_object(obj: "InkObject"):
    if isinstance(obj, Container):
        return dump_runtime_container(obj)

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
        dump_ink_list(obj)

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


def array_to_container(array):
    container = Container()
    container.content = array_to_runtime_object_list(array, skip_last=True)

    if terminator := array[-1]:
        named_only_content = {}

        for key, value in terminator.items():
            if key == "#f":
                container.count_flags = int(value)
            elif key == "#n":
                container.name = str(value)
            else:
                item = token_to_runtime_object(value)
                if isinstance(item, Container):
                    item.name = key
                named_only_content[key] = item

        container.named_only_content = named_only_content

    return container


def array_to_runtime_object_list(array, skip_last=False):
    if skip_last:
        array = array[:-1]

    objects = []

    for token in array:
        obj = token_to_runtime_object(token)

        objects.append(obj)

    return objects


def token_to_runtime_object(token):
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
        return array_to_container(token)

    elif token is None:
        return None

    raise RuntimeError(f"Failed to convert token to runtime object: '{token}'")
