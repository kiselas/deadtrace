async def job(ctx: dict[str, object]) -> None:
    pass


class WorkerSettings:
    functions = [job]  # noqa: RUF012
