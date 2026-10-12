from app._testing import BaseAuthTests


class AuthTests(BaseAuthTests):
    def token(self):
        return "sample"
