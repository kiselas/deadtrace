class _InstanceHooks:
    def _fixture_setup(self):
        return "setup"

    def _fixture_teardown(self):
        return "teardown"

    def _private_helper(self):
        return "unused"


class _ClassHooks:
    @classmethod
    def _fixture_setup(cls):
        return "setup"

    def _fixture_teardown(self):
        return "teardown"


class _DormantHooks:
    def _fixture_setup(self):
        return "unused"


class _ShadowedHooks:
    def _fixture_setup(self):
        return "shadowed"


class _PlainHooks:
    def _fixture_setup(self):
        return "not a unittest callback"
