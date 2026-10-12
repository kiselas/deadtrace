import yt_dlp


def download(src, dest, cookies=None):
    errors = []

    class _CollectingLogger:
        def debug(self, msg):
            pass

        def warning(self, msg):
            pass

        def error(self, msg):
            errors.append(str(msg))

    class _Unused:
        def error(self, msg):
            return msg

    base = {"outtmpl": dest, "logger": _CollectingLogger()}
    attempts = [base]
    if cookies:
        attempts.append({**base, "cookiefile": cookies})
    for opts in attempts:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([src])
    return errors
