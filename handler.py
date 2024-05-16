import io
import json
import os
import re
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler

RANGE_BYTES_RE = re.compile(r'bytes=(\d*)-(\d*)?\Z')


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
    web_root_dir = None
    host = None
    port = None
    domain = None

    def __init__(self, *args, **kwargs):
        self.domain = f"http://{self.host}:{self.port}"
        super().__init__(*args, directory=self.web_root_dir, **kwargs)

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

    def list_directory(self, path):
        match = re.search(r'\\(.*)', path.replace(self.web_root_dir, ""))
        m = match.group(1) if match else ""
        try:
            name_list = os.listdir(path)
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "No permission to list directory")
            return None
        name_list.sort(key=lambda a: a.lower())
        json_array = []
        for name in name_list:
            fullname = os.path.join(path, name)
            if os.path.isdir(fullname):
                file_type = "dir"
            elif os.path.isfile(fullname) and fullname.endswith(".mp4"):
                file_type = "mp4"
            else:
                continue
            url = f"{self.domain}/{m}{name}"
            json_array.append({"name": name, "url": url, "type": file_type})
        enc = sys.getfilesystemencoding()
        result = {"data": json_array}
        jsonobj = json.dumps(result)
        encoded = jsonobj.encode(enc, 'surrogateescape')
        f = io.BytesIO()
        f.write(encoded)
        f.seek(0)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-type", "text/html; charset=%s" % enc)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        return f

    def copyfile(self, source: io.BytesIO, outputfile):
        try:
            if self.range is not None:
                start, end = self.range
                source.seek(start)
            return super().copyfile(source, outputfile)
        except BrokenPipeError:
            pass
        except ConnectionResetError:
            # 链接失败
            pass
        except ConnectionAbortedError:
            print("终端链接断开")
