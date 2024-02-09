import typing as t

if t.TYPE_CHECKING:
    from .object import InkObject


ChoosePathStringHandler = t.Callable[[str, "InkObject"], None]
DidContinueHandler = t.Callable[[], None]
ErrorHandler = WarningHandler = t.Callable[[str], None]
Observer = t.Callable[[str, t.Any], None]
