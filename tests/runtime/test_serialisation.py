import logging
import pytest

from inkpy.runtime import serialisation
from inkpy.runtime.call_stack import PushPopType
from inkpy.runtime.container import Container
from inkpy.runtime.divert import Divert
from inkpy.runtime.story import Story
from inkpy.runtime.value import BoolValue, FloatValue, IntValue, StringValue
from inkpy.runtime.void import Void


@pytest.fixture
def story():
    story = Story()
    story.root_content_container = Container()

    return story


@pytest.fixture(scope="session")
def story_json(datadir):
    with (datadir / "minimal.ink.json").open("r", encoding="utf-8-sig") as f:
        return f.read()


def test_dump(story, story_json, tmpdir):
    with (tmpdir / "dump.json").open("w+") as f:
        serialisation.dump(story, f)
        f.seek(0)
        res = f.read()

    assert res == story_json


def test_dump_runtime_container_empty():
    obj = serialisation.dump_runtime_container(Container())
    assert isinstance(obj, list)
    assert len(obj) == 0


def test_dump_runtime_container_flags():
    container = Container()
    container.count_at_start_only = True
    obj1 = serialisation.dump_runtime_container(container)
    assert len(obj1) == 0

    container = Container()
    container.turn_index_should_be_counted = True
    obj2 = serialisation.dump_runtime_container(container)
    assert obj2[-1]["#f"] == Container.CountFlags.Turns

    container = Container()
    container.visits_should_be_counted = True
    obj3 = serialisation.dump_runtime_container(container)
    assert obj3[-1]["#f"] == Container.CountFlags.Visits

    container = Container()
    container.turn_index_should_be_counted = True
    container.visits_should_be_counted = True
    obj4 = serialisation.dump_runtime_container(container)
    assert obj4[-1]["#f"] & Container.CountFlags.CountStartOnly == 0
    assert obj4[-1]["#f"] & Container.CountFlags.Turns > 0
    assert obj4[-1]["#f"] & Container.CountFlags.Visits > 0


def test_dump_runtime_container_named():
    obj = serialisation.dump_runtime_container(Container("foo"))
    assert isinstance(obj, list)
    assert len(obj) == 1
    assert obj[-1]["#n"] == "foo"


def test_dump_runtime_container_with_content():
    container = Container()
    container.add_content(StringValue("\n"))
    obj = serialisation.dump_runtime_container(container)
    assert isinstance(obj, list)
    assert len(obj) == 1


def test_dump_runtime_container_with_named_content():
    container = Container()
    container.add_content(Container("bar"))
    obj = serialisation.dump_runtime_container(container)
    assert isinstance(obj, list)
    assert len(obj) == 1
    assert obj[0][-1]["#n"] == "bar"


def test_dump_runtime_container_with_named_content_only():
    container = Container()
    container.add_named_content(Container("bar"))
    obj = serialisation.dump_runtime_container(container)
    assert isinstance(obj, list)
    assert len(obj) == 1
    assert "bar" in obj[-1]


def test_dump_runtime_object_bool_value():
    obj1 = serialisation.dump_runtime_object(BoolValue(True))
    assert obj1 is True

    obj2 = serialisation.dump_runtime_object(BoolValue(False))
    assert obj2 is False


def test_dump_runtime_object_float_value():
    obj = serialisation.dump_runtime_object(FloatValue(1.07))
    assert isinstance(obj, float)
    assert obj == pytest.approx(1.07)


def test_dump_runtime_object_int_value():
    obj = serialisation.dump_runtime_object(IntValue(1))
    assert isinstance(obj, int)
    assert obj == 1


def test_dump_runtime_object_string_newline():
    obj = serialisation.dump_runtime_object(StringValue("\n"))
    assert obj == "\n"


def test_dump_runtime_object_string_value():
    obj = serialisation.dump_runtime_object(StringValue("test string"))
    assert obj == "^test string"


def test_dump_runtime_object_unknown():
    with pytest.raises(RuntimeError, match="Failed to convert runtime object to token"):
        serialisation.dump_runtime_object(object)


def test_dump_runtime_object_void():
    obj = serialisation.dump_runtime_object(Void())
    assert obj == "void"


def test_dumps(story, story_json):
    res = serialisation.dumps(story)
    assert res == story_json


def test_load(datadir):
    with (datadir / "minimal.ink.json").open("r", encoding="utf-8-sig") as f:
        root, _ = serialisation.load(f)

    assert isinstance(root, Container)
    assert len(root.content) == 0


def test_load_root_missing():
    with pytest.raises(ValueError, match="Root node for ink not found"):
        serialisation.load({"inkVersion": serialisation.INK_VERSION_CURRENT})


def test_load_version_malformed():
    with pytest.raises(ValueError, match="Version of ink value was malformed"):
        serialisation.load({"inkVersion": "foo", "root": []})


def test_load_version_min_supported(caplog):
    with caplog.at_level(logging.WARNING):
        serialisation.load(
            {"inkVersion": serialisation.INK_VERSION_MINIMUM_COMPATIBLE, "root": []}
        )

    assert (
        "Version of ink used to build story doesn't match current version"
        in caplog.text
    )


def test_load_version_missing():
    with pytest.raises(ValueError, match="Version of ink could not be found"):
        serialisation.load({"root": []})


def test_load_version_newer():
    with pytest.raises(
        RuntimeError, match="Version of ink used to build story was newer"
    ):
        serialisation.load(
            {"inkVersion": serialisation.INK_VERSION_CURRENT + 1, "root": []}
        )


def test_load_version_old():
    with pytest.raises(
        RuntimeError, match="Version of ink used to build story is too old"
    ):
        serialisation.load(
            {"inkVersion": serialisation.INK_VERSION_MINIMUM_COMPATIBLE - 1, "root": []}
        )


def test_load_runtime_container_empty():
    obj = serialisation.load_runtime_container([])
    assert isinstance(obj, Container)
    assert not obj.has_valid_name
    assert len(obj.content) == 0
    assert len(obj.named_content) == 0


def test_load_runtime_container_flags():
    obj1 = serialisation.load_runtime_container([])
    assert isinstance(obj1, Container)
    assert obj1.flags == 0

    obj2 = serialisation.load_runtime_container([{"#f": Container.CountFlags.Turns}])
    assert isinstance(obj2, Container)
    assert obj2.flags == Container.CountFlags.Turns

    obj3 = serialisation.load_runtime_container(
        [{"#f": Container.CountFlags.Turns | Container.CountFlags.Visits}]
    )
    assert isinstance(obj3, Container)
    assert obj3.flags & Container.CountFlags.Turns > 0
    assert obj3.flags & Container.CountFlags.Visits > 0
    assert obj3.flags & Container.CountFlags.CountStartOnly == 0

    obj4 = serialisation.load_runtime_container(
        [{"#f": Container.CountFlags.CountStartOnly}]
    )
    assert isinstance(obj4, Container)
    assert obj4.flags == 0


def test_load_runtime_container_named():
    obj = serialisation.load_runtime_container([{"#n": "foo"}])
    assert isinstance(obj, Container)
    assert obj.name == "foo"
    assert len(obj.content) == 0
    assert len(obj.named_content) == 0


def test_load_runtime_container_with_content():
    obj = serialisation.load_runtime_container([[], {}])
    assert isinstance(obj, Container)
    assert len(obj.content) == 1
    assert len(obj.named_content) == 0


def test_load_runtime_container_with_named_content():
    obj = serialisation.load_runtime_container([[{"#n": "bar"}], {}])
    assert isinstance(obj, Container)
    assert len(obj.content) == 1
    assert len(obj.named_content) == 1


def test_load_runtime_container_with_named_content_only():
    obj = serialisation.load_runtime_container([{"bar": [{"#n": "bar"}]}])
    assert isinstance(obj, Container)
    assert len(obj.content) == 0
    assert len(obj.named_only_content) == 1


def test_load_runtime_object_bool_value():
    obj1 = serialisation.load_runtime_object(True)
    assert isinstance(obj1, BoolValue)
    assert obj1.value is True

    obj2 = serialisation.load_runtime_object(False)
    assert isinstance(obj2, BoolValue)
    assert obj2.value is False


def test_load_runtime_object_divert():
    return

    target = "."

    obj1 = serialisation.load_runtime_object({"->": target})
    assert isinstance(obj1, Divert)
    assert obj1.is_external is False
    assert obj1.pushes_to_stack is False
    assert obj1.target_path_string == target

    obj2 = serialisation.load_runtime_object({"f()": target})
    assert isinstance(obj2, Divert)
    assert obj2.is_external is False
    assert obj2.pushes_to_stack is True
    assert obj2.stack_push_type == PushPopType.Function
    assert obj2.target_path_string == target

    obj3 = serialisation.load_runtime_object({"->t->": target})
    assert isinstance(obj3, Divert)
    assert obj3.is_external is False
    assert obj3.pushes_to_stack is True
    assert obj3.stack_push_type == PushPopType.Tunnel
    assert obj3.target_path_string == target

    obj4 = serialisation.load_runtime_object({"x()": target})
    assert isinstance(obj4, Divert)
    assert obj4.is_external is True
    assert obj4.pushes_to_stack is False
    assert obj4.target_path_string == target

    obj5 = serialisation.load_runtime_object({"->": target, "var": True})
    assert isinstance(obj5, Divert)
    assert obj5.has_variable_target is True

    obj6 = serialisation.load_runtime_object({"->": target, "c": True})
    assert isinstance(obj6, Divert)
    assert obj6.is_conditional is True

    obj7 = serialisation.load_runtime_object({"x()": target, "exArgs": 2})
    assert isinstance(obj7, Divert)
    assert obj7.is_external is True
    assert obj7.external_args == 2


def test_load_runtime_object_empty_dict():
    with pytest.raises(RuntimeError, match="Failed to convert token to runtime object"):
        serialisation.load_runtime_object({})


def test_load_runtime_object_float_value():
    obj = serialisation.load_runtime_object(1.07)
    assert isinstance(obj, FloatValue)
    assert obj.value == pytest.approx(1.07)


def test_load_runtime_object_int_value():
    obj = serialisation.load_runtime_object(1)
    assert isinstance(obj, IntValue)
    assert obj.value == 1


def test_load_runtime_object_null():
    obj = serialisation.load_runtime_object(None)
    assert obj is None


def test_load_runtime_object_string_newline():
    obj = serialisation.load_runtime_object("\n")
    assert isinstance(obj, StringValue)
    assert obj.value == "\n"


def test_load_runtime_object_string_value():
    obj = serialisation.load_runtime_object("^test string")
    assert isinstance(obj, StringValue)
    assert obj.value == "test string"


def test_load_runtime_object_unknown():
    with pytest.raises(RuntimeError, match="Failed to convert token to runtime object"):
        serialisation.load_runtime_object("")


def test_load_runtime_object_void():
    obj = serialisation.load_runtime_object("void")
    assert isinstance(obj, Void)


def test_loads(story_json):
    root, _ = serialisation.loads(story_json)
    assert isinstance(root, Container)
    assert len(root.content) == 0
