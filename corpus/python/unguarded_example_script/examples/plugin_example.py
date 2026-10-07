from _shop.cart import total


def parse_items(text):
    return [int(item) for item in text.split(",")]


def setup(text):
    return total(parse_items(text))


def never_called():
    return "dead"


print(setup("1,2,3"))
