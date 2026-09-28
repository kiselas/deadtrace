from fastapi import BackgroundTasks, FastAPI

app = FastAPI()


class Cleanup:
    def __init__(self, user: str) -> None:
        self.user = user

    def run(self, dry: bool) -> None:
        self.helper()

    def helper(self) -> None:
        pass

    def forgotten(self) -> None:
        pass


@app.post("/cleanup")
def cleanup(background_tasks: BackgroundTasks) -> None:
    background_tasks.add_task(Cleanup(user="admin").run, True)
