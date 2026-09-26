from pydantic import BaseModel


def to_camel(value: str) -> str:
    return value


class Item(BaseModel):
    item_name: str

    class Config:
        alias_generator = to_camel


class Plain:
    class Nested:
        pass


if __name__ == "__main__":
    print(Item(itemName="x"), Plain())
