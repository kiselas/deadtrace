from cookiecutter.utils import simple_filter
from jinja2.ext import Extension


def _helper(value):
    return str(value).lower()


@simple_filter
def format_value(value):
    return _helper(value)


class FilterExtension(Extension):
    def filter(self, value):
        return str(value).upper()


def _unused(value):
    return str(value).strip()
