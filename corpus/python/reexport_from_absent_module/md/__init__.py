from typing import TYPE_CHECKING

from ._compat import USE_EXTENSIONS

__all__ = ("MultiDict", "getversion")

if TYPE_CHECKING or not USE_EXTENSIONS:
    from ._impl import MultiDict, getversion
else:
    from ._ext import MultiDict, getversion
