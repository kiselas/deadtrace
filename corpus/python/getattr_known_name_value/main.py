from app._trackers import build


def main():
    for tracker in build():
        prime = getattr(tracker, "prime", None)
        if prime:
            prime([1])


if __name__ == "__main__":
    main()
