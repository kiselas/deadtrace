import sys

if sys.platform == "win32":

    def cmdexec() -> str:
        return "windows"

else:

    def cmdexec() -> str:
        return "run"
