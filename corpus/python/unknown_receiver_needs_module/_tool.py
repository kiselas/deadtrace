from _handles import Handle


def release(resource) -> None:
    resource.close()


if __name__ == "__main__":
    release(Handle())
