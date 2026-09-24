from fastapi import FastAPI

app = FastAPI()


def metaclass_helper() -> None:
    pass


class Meta(type):
    def __new__(mcls, name, bases, namespace):
        metaclass_helper()
        return super().__new__(mcls, name, bases, namespace)


def property_helper() -> str:
    return "value"


def protocol_helper() -> None:
    pass


class Resource(metaclass=Meta):
    @property
    def value(self) -> str:
        return property_helper()

    def __iter__(self):
        protocol_helper()
        return iter(())


def unused() -> None:
    pass


@app.get("/resource")
async def resource_endpoint() -> dict[str, str]:
    resource = Resource()
    return {"value": resource.value}
