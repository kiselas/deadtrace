from typing import ClassVar

from arq import cron
from arq.connections import RedisSettings


async def startup(ctx: dict[str, object]) -> None:
    pass


async def job(ctx: dict[str, object]) -> None:
    pass


async def nightly(ctx: dict[str, object]) -> None:
    pass


class WorkerSettings:
    functions: ClassVar[list[object]] = [job]
    cron_jobs = [cron(nightly, hour=3)]  # noqa: RUF012 - arq reads a plain class attribute too
    on_startup = startup
    redis_settings = RedisSettings()
