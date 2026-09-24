class Notifier:
    def send(self, text: str) -> str:
        return text


class EmailNotifier(Notifier):
    def send(self, text: str) -> str:
        return f"email: {text}"


def make_notifier() -> Notifier:
    return EmailNotifier()


def unused_control() -> str:
    return "never called"


def main() -> None:
    notifier = make_notifier()
    print(notifier.send("hello"))
