import importlib
import sys

_BACKENDS = {"langfuse": "app._backends.langfuse"}


def _load_backend(name):
    return importlib.import_module(_BACKENDS[name])


def main():
    backend = _load_backend(sys.argv[1])
    print(backend.build_eval_command(sys.argv[2:]))


if __name__ == "__main__":
    main()
