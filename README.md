# inkpy

This is a Python port of inkle's [ink](https://github.com/inkle/ink), a scripting language for writing interactive
narrative for use with game and web frameworks.

inkpy aims to be fully feature compatible with ink and [inkjs](github.com/y-lohse/inkjs) while instead maintaining a
more Pythonic API.


## Getting Started

```python

from inkpy.runtime import Story


story = Story(data)
story.continue_()

```


## Encoding

You should read any ``.ink`` and ``.ink.json`` files using ``utf-8-sig`` encoding or you may receive a
``UnicodeDecodeError`` because of the byte-order mark (BOM) that is typically added by some tools. An example below:

```python

with open("story.ink.json", "r", encoding="utf-8-sig") as f:
    ...

```

When writing files you can use ``utf-8`` encoding which is typically the Python default.


## Differences with C# API

- Methods and attributes have been converted from CamelCase to snake_case.

- Like the JS port, methods that pass a reference to a variable will typically return tuples instead.

- The entire API has not been replicated, typically your most common public methods and attributes on the ``Story``
  class have been retained but others may have been renamed, refactored, merged or removed.

- Errors and warnings have separate ``on_error`` and ``on_warning`` handlers respectively.

- The random implementation may not produce the same results even if seeded the same, but neither does inkjs until
  [ink #188](https://github.com/inkle/ink/issues/188) and [inkjs #31](https://github.com/y-lohse/inkjs/issues/31) are
  resolved. Once that has been done it will be worthwhile implementing the same PRNG here to have consistent results
  across the board.

  A hook ``random_generator`` is provided in case you need to implement an ink or inkjs adjacent random generator.
