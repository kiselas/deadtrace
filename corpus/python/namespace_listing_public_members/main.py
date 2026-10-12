from app._rpc import Service, rpc_methods


def main():
    print(rpc_methods(Service()))


if __name__ == "__main__":
    main()
