from app._archive import ArchiveStrategy, Artifact


def main():
    print(Artifact(ArchiveStrategy()).build(), Artifact(ArchiveStrategy()).build_quoted())


if __name__ == "__main__":
    main()
