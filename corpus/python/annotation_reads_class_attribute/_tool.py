class EventData:
    code: int = 0


class Meta:
    name = "arbiter"

    class Models:
        EventDataType = EventData | None

    class Unused:
        pass


def fire(data: Meta.Models.EventDataType) -> None:
    print(data)


def main() -> None:
    fire(EventData())


if __name__ == "__main__":
    main()
