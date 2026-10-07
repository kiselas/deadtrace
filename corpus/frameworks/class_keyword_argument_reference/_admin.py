from sqladmin import ModelView


class User:
    pass


class Unused:
    pass


class UserAdmin(ModelView, model=User):
    pass


def main() -> None:
    print(UserAdmin)


if __name__ == "__main__":
    main()
