import api


def main():
    callback = getattr(api, "run")  # noqa: B009 - intentional reflected import alias
    callback()
