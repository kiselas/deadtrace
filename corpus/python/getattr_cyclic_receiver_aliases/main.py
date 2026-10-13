import _hooks


def probe(value):
    receiver = value
    receiver = receiver.target
    alternate = receiver
    receiver = alternate
    hook = getattr(receiver, "prime", None)
    return hook


def main():
    probe(_hooks.Worker())


if __name__ == "__main__":
    main()
