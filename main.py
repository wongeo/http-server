import os
import sys

from server import HttpServer as Server1
from server2 import HttpServer as Server2


def main():
    path = sys.argv[1]
    # server = Server1("127.0.0.1", 3000)
    server = Server2("127.0.0.1", 3000, os.path.expanduser('~') + "/Movies")
    server.serve_forever()


if __name__ == '__main__':
    main()
