import os
import re
import urllib
from http.server import HTTPServer, SimpleHTTPRequestHandler

web_root_dir = None


class HttpServer(object):
    def __init__(self, address='', port=8282, directory=None):
        self.server_address = (address, port)
        global web_root_dir
        web_root_dir = directory

    def serve_forever(self):
        http_server = HTTPServer(self.server_address, RequestHandler)
        http_server.serve_forever()


RANGE_BYTES_RE = re.compile(r'bytes=(\d*)-(\d*)?\Z')


def _copy_range(infile, outfile, start, end):
    buf_size = 16 * 1024
    if start is not None:
        infile.seek(start)
    while True:
        size = buf_size
        if end is not None:
            left = end - infile.tell()
            if left < size:
                size = left
        buf = infile.read(size)
        if not buf:
            break
        outfile.write(buf)


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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=web_root_dir, **kwargs)

    def send_head(self):
        if 'Range' not in self.headers:
            self.range = None
            return super().send_head()
        try:
            self.range = parse_range_bytes(self.headers['Range'])
        except ValueError as e:
            self.send_error(416, 'Requested Range Not Satisfiable')
            return None
        start, end = self.range

        path = self.translate_path(self.path)
        if os.path.isdir(path):
            parts = urllib.parse.urlsplit(self.path)
            print(parts)
            if not parts.path.endswith('/'):
                self.send_response(301)
                new_parts = (parts[0], parts[1], parts[2] + '/',
                             parts[3], parts[4])
                new_url = urllib.parse.urlunsplit(new_parts)
                self.send_header("Location", new_url)
                self.end_headers()
                return None
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break

        f = None
        try:
            f = open(path, 'rb')
        except IOError:
            self.send_error(404, 'Not Found')
            return None

        self.send_response(206)

        ctype = self.guess_type(path)
        self.send_header('Content-type', ctype)
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
        self.send_header('Last-Modified', self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f

    def end_headers(self):
        self.send_header('Cache-Control', 'max-age=0')
        self.send_header('Expires', '0')
        super().end_headers()

    def copyfile(self, source, outputfile):
        try:
            if not self.range:
                return super().copyfile(source, outputfile)

            start, end = self.range
            _copy_range(source, outputfile, start, end)
        except BrokenPipeError:
            pass
