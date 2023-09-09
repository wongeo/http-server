import os
import socket
import re


class HttpServer(object):
    def __init__(self, address, port, directory=None):
        if directory is None:
            directory = os.getcwd()
        self.directory = os.fspath(directory)
        """ 在初始化中做好tcp连接的准备工作 """
        # 1创建一个tcp套接字
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # 端口重复使用
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # 2.绑定本地端口
        self.tcp_socket.bind((address, port))
        # 3.设置监听
        self.tcp_socket.listen(128)

    def serve_forever(self):
        """ 循环运行服务器 """
        while True:
            # 1.等待用户接入
            new_socket, address = self.tcp_socket.accept()
            # 2.为用户提供服务,创建多线程
            self.handle_client(new_socket)

    def handle_client(self, client_socket):
        # 1.接受消息
        client_message = client_socket.recv(1024).decode("utf-8")
        # 对接收的的请求信息进行分析筛选
        request_message = client_message.splitlines()
        if request_message:
            handle_result = re.match(r"[^/]+(/[^ ]*)", request_message[0])
            # 2.返回消息给用户 #
            if handle_result:
                file_name = handle_result.group(1)
                if file_name == "/":
                    file_name = "/html/index.html"
                try:
                    file = open(self.directory + file_name, "rb")
                except IOError:
                    handle_404(client_socket)
                else:
                    html = file.read()
                    file.close()
                    handle_200(client_socket, html)
                    # 3.关闭new_socket客户连接
                client_socket.close()


def handle_200(client_socket, content):
    response = "HTTP/1.1 200 OK\r\n\r\n"
    client_socket.send(response.encode("utf-8"))
    client_socket.send(content)


def handle_404(client_socket):
    response = "HTTP/1.1 404 NOT FOUND\r\n\r\n"
    client_socket.send(response.encode("utf-8"))
    client_socket.send("<h1>404 NOT FOUND</h1>".encode("utf-8"))
