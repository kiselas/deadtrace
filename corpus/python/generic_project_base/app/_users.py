from app._repo import BaseRepo


class UserRepo(BaseRepo[int]):
    def _load(self):
        return 1

    def _never(self):
        return 2
