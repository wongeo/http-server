import http
import socketserver
from http.server import HTTPServer

from handler import RequestHandler

web_root_dir = None


class HttpServer:
    def __init__(self, address='', port=3000, directory=None):
        self.address = address
        self.port = port
        self.web_root_dir = directory
        self.http_server = None
        global web_root_dir
        web_root_dir = directory

    def start(self):
        # 创建HTTPServer实例并启动
        handler = RequestHandler
        self.http_server = CustomHTTPServer((self.address, self.port), handler)
        self.http_server.RequestHandlerClass.web_root_dir = self.web_root_dir
        self.http_server.RequestHandlerClass.host = self.address
        self.http_server.RequestHandlerClass.port = self.port
        self.http_server.serve_forever()


class CustomHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    pass
