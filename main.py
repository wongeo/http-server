import sys

from server3 import HttpServer as Server


def main():
    args = sys.argv
    path = args[1]
    address = ""
    if len(args) >= 2:
        address = args[2]
    server = Server(address, 3000, path)
    server.start()


if __name__ == '__main__':
    main()
