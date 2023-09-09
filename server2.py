import http
import os
import re
import socketserver
import urllib
from http.server import HTTPServer, SimpleHTTPRequestHandler

web_root_dir = None


class HttpServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    def __init__(self, address='', port=8282, directory=None):
        super().__init__((address, port), RequestHandler)
        global web_root_dir
        web_root_dir = directory


RANGE_BYTES_RE = re.compile(r'bytes=(\d*)-(\d*)?\Z')

COPY_BUF_SIZE = 64 * 1024


def copyfileobj(file_src, file_dst, start=None):
    if start is not None:
        file_src.seek(start)
    length = COPY_BUF_SIZE
    while True:
        buf = file_src.read(length)
        if not buf:
            break
        file_dst.write(buf)


def parse_range_bytes(range_bytes):
    if range_bytes == '':
        return None, None

    m = RANGE_BYTES_RE.match(range_bytes)
    if not m:
        raise ValueError('Invalid byte range %s' % range_bytes)

    if m.group(1) == '':
        start = None
    else:
        start = int(m.group(1))
    if m.group(2) == '':
        end = None
    else:
        end = int(m.group(2)) + 1

    return start, end


class RequestHandler(SimpleHTTPRequestHandler):
    range = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=web_root_dir, **kwargs)

    def send_head(self):
        if 'Range' not in self.headers:
            # 没有range直接返回
            return super().send_head()
        # 获取range
        self.range = parse_range_bytes(self.headers['Range'])
        if self.range is None:
            self.send_error(416, 'Requested Range Not Satisfiable')
            return None
        start, end = self.range
        path = self.translate_path(self.path)
        try:
            f = open(path, 'rb')
        except IOError:
            self.send_error(404, 'Not Found')
            return None

        self.send_response(206)
        self.send_header('Content-type', self.guess_type(path))
        self.send_header('Accept-Ranges', 'bytes')

        fs = os.fstat(f.fileno())
        file_len = fs[6]
        if start is not None and start >= file_len:
            self.send_error(416, 'Requested Range Not Satisfiable')
            return None
        if end is None or end > file_len:
            end = file_len

        self.send_header('Content-Range', 'bytes %s-%s/%s' % (start, end - 1, file_len))
        self.send_header('Content-Length', str(end - start))
        self.send_header('Last-Modified', self.date_time_string(int(fs.st_mtime)))
        self.end_headers()
        return f

    def end_headers(self):
        self.send_header('Cache-Control', 'max-age=0')
        self.send_header('Expires', '0')
        super().end_headers()

    def copyfile(self, source, outputfile):
        try:
            if self.range is not None:
                start, end = self.range
                source.seek(start)
            # copy_range(source, outputfile, start, end)
            # copyfileobj(source, outputfile, start)
            return super().copyfile(source, outputfile)
        except BrokenPipeError:
            pass
        except ConnectionResetError:
            # 链接失败
            pass
