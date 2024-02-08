import typing as t


ErrorHandler = WarningHandler = t.Callable[[str], None]
Observer = t.Callable[[str, t.Any], None]
