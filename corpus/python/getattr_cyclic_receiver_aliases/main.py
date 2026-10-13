import _hooks


def probe(value):
    receiver = value
    receiver = receiver.target
    alternate = receiver
    receiver = alternate
    hook = getattr(receiver, "prime", None)
    return hook


def main():
    hook = probe(_hooks.Worker())
    if hook:
        hook()


if __name__ == "__main__":
    main()
