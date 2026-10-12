from app._users import UserRepo


def main():
    print(UserRepo().get())


if __name__ == "__main__":
    main()
