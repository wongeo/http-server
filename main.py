import socket
import threading
import re


def handle_client(new_socket):
    # 1.接受消息
    client_message = new_socket.recv(1024).decode("utf-8")
    # 对接收的的请求信息进行分析筛选
    request_message = client_message.splitlines()
    if request_message:
        handle_result = re.match(r"[^/]+(/[^ ]*)", request_message[0])
        # 2.返回消息给用户 #
        if handle_result:
            file_name = handle_result.group(1)
            if file_name == "/":
                file_name = "/index.html"
            try:
                file = open("./html" + file_name, "rb")
            except Exception :
                response = "HTTP/1.1 404 NOT FOUND\r\n\r\n"
                new_socket.send(response.encode("utf-8"))
                new_socket.send("<h1>404 NOT FOUND</h1>".encode("utf-8"))
            else:
                response = "HTTP/1.1 200 OK\r\n\r\n"
                new_socket.send(response.encode("utf-8"))
                html = file.read()
                file.close()
                new_socket.send(html)
                # 3.关闭new_socket客户连接
            new_socket.close()


class Server(object):
    def __init__(self, port):
        """ 在初始化中做好tcp连接的准备工作 """
        # 1创建一个tcp套接字
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # 端口重复使用
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # 2.绑定本地端口
        self.tcp_socket.bind(("127.0.0.1", port))
        # 3.设置监听
        self.tcp_socket.listen(128)

    def run_server(self):
        """ 循环运行服务器 """
        while True:
            # 1.等待用户接入
            new_socket, address = self.tcp_socket.accept()
            # 2.为用户提供服务,创建多线程
            handle_client(new_socket)


def main():
    server = Server(3000)
    server.run_server()
    server.tcp_socket.close()


if __name__ == '__main__':
    main()
