from app_admin import changelist
from django.test import RequestFactory


class _MockSuperUser:
    def has_perm(self, perm):
        return True

    def _private(self):
        return None


class _Unused:
    def has_perm(self, perm):
        return False


def test_changelist():
    request = RequestFactory().get("/")
    request.user = _MockSuperUser()
    assert changelist(request)
