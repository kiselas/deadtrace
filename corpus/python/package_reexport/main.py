import pkg
from pkg import PublicService, helper


def main() -> None:
    helper()
    pkg.helper()
    PublicService().run()
