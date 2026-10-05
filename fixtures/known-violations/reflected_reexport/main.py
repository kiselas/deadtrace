import api


def main():
    callback = getattr(api, "run")
    callback()
