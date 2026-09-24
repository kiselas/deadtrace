class Repository:
    def load(self) -> str:
        return "dish"


class Service:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def get(self) -> str:
        return self.repository.load()


def endpoint(service: Service) -> str:
    return service.get()
