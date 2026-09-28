from aiosmtpd.controller import Controller


class Handler:
    def __init__(self, port: int) -> None:
        self.port = port

    async def handle_DATA(self, server: object, session: object, envelope: object) -> str:
        return "250 OK"


class Report:
    def unused(self) -> str:
        return "unused"


def serve() -> None:
    Controller(Handler(25), port=25).start()
    handler = Handler(26)
    Controller(handler, port=26).start()


def show() -> None:
    print(Report())


if __name__ == "__main__":
    serve()
    show()
