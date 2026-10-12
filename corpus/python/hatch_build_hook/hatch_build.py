from hatchling.builders.hooks.plugin.interface import BuildHookInterface


def _get_version():
    return "0.1.0"


def _helper():
    return None


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        build_data["version"] = _get_version()
