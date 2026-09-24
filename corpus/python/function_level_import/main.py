def main() -> None:
    import reports
    from tasks import schedule

    def render() -> None:
        reports.build()

    schedule()
    render()


def unused_control() -> None:
    pass
