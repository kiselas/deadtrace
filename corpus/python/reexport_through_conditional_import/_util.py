import sys

if sys.platform == "win32":
    from _inet import inet_ntop
else:
    from socket import inet_ntop

__all__ = ["inet_ntop"]
