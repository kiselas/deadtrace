"""Small Python 3.12 nominal families; unrecognized external bases remain opaque.

These are shipped semantic data, not imports or inspections of target dependencies.
The families intentionally over-approximate related concrete and pure path types.
"""

PATH_TYPES = frozenset(
    f"pathlib.{name}"
    for name in ("Path", "PurePath", "PosixPath", "WindowsPath", "PurePosixPath", "PureWindowsPath")
)
LOGGING_TYPES = frozenset(
    f"logging.{name}"
    for name in (
        "LogRecord",
        "Handler",
        "StreamHandler",
        "FileHandler",
        "NullHandler",
        "Logger",
        "LoggerAdapter",
        "Filter",
        "Filterer",
    )
)
NOMINAL_FAMILIES = {name: PATH_TYPES for name in PATH_TYPES} | {
    "logging.LogRecord": frozenset({"logging.LogRecord"})
}
ROOT_BASES = frozenset(
    {
        "object",
        "dict",
        "list",
        "tuple",
        "set",
        "frozenset",
        "str",
        "bytes",
        "bytearray",
        "int",
        "float",
        "complex",
        "bool",
        "BaseException",
        "Exception",
        "RuntimeError",
        "TypeError",
        "ValueError",
        "AttributeError",
        "AssertionError",
        "KeyError",
        "LookupError",
        "ImportError",
        "Warning",
        "UserWarning",
        "DeprecationWarning",
        "ResourceWarning",
        "NotImplementedError",
        "OSError",
        "IOError",
    }
)
MIXIN_BASES = frozenset(
    {
        "abc.ABC",
        "enum.Enum",
        "enum.Flag",
        "enum.IntEnum",
        "enum.IntFlag",
        "enum.ReprEnum",
        "enum.StrEnum",
    }
    | {
        f"{module}.{name}"
        for module in ("typing", "typing_extensions")
        for name in ("Generic", "Protocol", "NamedTuple", "TypedDict")
    }
)


def may_supply_nominal_value(base: str, nominal: str) -> bool:
    """Unknown external ancestry always remains a possible supplier."""
    family = NOMINAL_FAMILIES[nominal]
    if base in family:
        return True
    if base in PATH_TYPES | LOGGING_TYPES | MIXIN_BASES | ROOT_BASES:
        return False
    return not (base.startswith("builtins.") and base.removeprefix("builtins.") in ROOT_BASES)
