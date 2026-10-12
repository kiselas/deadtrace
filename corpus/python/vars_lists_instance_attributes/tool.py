import argparse


class _Store:
    def save(self):
        return "saved"


class _Registry:
    def handler(self):
        return "handled"


def _build_parser():
    return argparse.ArgumentParser()


def _run(**options):
    return _Store(), options


def main():
    _run(**vars(_build_parser().parse_args()))
    print(sorted(vars(_Registry)))


if __name__ == "__main__":
    main()
