import yt_dlp


def download(url: str) -> None:
    class _CollectingLogger:
        def debug(self, message: str) -> None:
            print(message)

        def warning(self, message: str) -> None:
            print(message)

    options = {"logger": _CollectingLogger(), "quiet": True}
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])


class _Direct:
    def info(self, message: str) -> None:
        print(message)


def direct() -> None:
    yt_dlp.YoutubeDL({"logger": _Direct()})


class _Kept:
    def run(self) -> None:
        print("kept")


def local_only() -> None:
    handlers = {"kept": _Kept()}
    print(len(handlers))


def main() -> None:
    download("x")
    direct()
    local_only()


if __name__ == "__main__":
    main()
