import pytest as pt


@pt.fixture
def ready_for_case():
    return None


@pt.fixture(scope="class")
def ready_for_group():
    return None


@pt.fixture
def unused():
    return None


@pt.mark.usefixtures("ready_for_case", "ready_for_group")
class Base:
    pass


class Intermediate(Base):
    pass


@pt.mark.usefixtures("unused")
class Uncollected:
    pass
