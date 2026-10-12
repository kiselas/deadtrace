HELPER_SETTINGS = dict(
    INSTALLED_APPS=["tests.media_app"],
)


def run():
    from app_helper import runner

    runner.cms("blog", extra_args=[])


if __name__ == "__main__":
    run()
