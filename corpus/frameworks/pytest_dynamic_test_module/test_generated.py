from _cases import make

SUITE = make()


def skip_slow(test: object) -> None:
    return None


TestGenerated = SUITE.to_testcase(SUITE.cases(), skip=lambda t: skip_slow(t))
