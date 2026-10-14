from cookiecutter.utils import simple_filter


@simple_filter
def format_value(value):
    return str(value)


def _unused():
    return "unused"
