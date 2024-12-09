import glob
import html
import io
import json
import os
import re
import sys
import urllib
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
        user_agent = self.headers['User-Agent']
        if "okhttp" in user_agent:
            return self.list_directory_json(path)
        else:
            return self.list_directory_web(path)

    def list_directory_json(self, path):
        try:
            mp4_files = glob.glob(os.path.join(path, '**', '*.mp4'), recursive=True)
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "No permission to list directory")
            return None
        json_array = []
        for full_path in mp4_files:
            name = full_path.replace(self.web_root_dir, "").replace("\\", "/")
            if name in json_array:
                continue
            else:
                url = f"{self.domain}/{name}"
                json_array.append({"name": name, "url": url, "type": "mp4"})
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

    def list_directory_web(self, path):
        try:
            list = get_files_with_extensions(path, ".mp4")
        except OSError:
            self.send_error(
                HTTPStatus.NOT_FOUND,
                "No permission to list directory")
            return None
        list.sort(key=lambda a: a.lower())
        r = []
        try:
            displaypath = urllib.parse.unquote(self.path, errors='surrogatepass')
        except UnicodeDecodeError:
            displaypath = urllib.parse.unquote(path)
        displaypath = html.escape(displaypath, quote=False)
        enc = sys.getfilesystemencoding()
        title = 'Directory listing for %s' % displaypath
        r.append('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" '
                 '"http://www.w3.org/TR/html4/strict.dtd">')
        r.append('<html>')
        r.append('<head>')
        r.append(f'<meta http-equiv="Content-Type" content="text/html; charset={enc}">')
        r.append(f'<title>{title}</title>')
        r.append('</head>')
        r.append('<body>')
        r.append(f'<h1>{title}</h1>')
        r.append('<hr>')
        r.append('<ul>')
        for name in list:
            fullname = os.path.join(path, name)
            displayname = linkname = name
            # Append / for directories or @ for symbolic links
            if os.path.isdir(fullname):
                displayname = name + "/"
                linkname = name + "/"
            if os.path.islink(fullname):
                displayname = name + "@"
                # Note: a link to a directory displays with @ and links with /
            r.append('<li><a href="%s">%s</a></li>' % (
                urllib.parse.quote(linkname, errors='surrogatepass'), html.escape(displayname, quote=False)))
        r.append('</ul>')
        r.append('<hr>')
        r.append('</body>')
        r.append('</html>')
        encoded = '\n'.join(r).encode(enc, 'surrogateescape')
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


def get_files_with_extensions(path, extensions):
    """
    获取指定路径下所有具有指定后缀之一的文件。

    参数:
    path (str): 要搜索的目录路径。
    extensions (list): 文件后缀列表，例如 ['.txt', '.csv']。

    返回:
    list: 包含符合条件的文件名的列表。
    """
    files = []
    for item in os.listdir(path):
        full_path = os.path.join(path, item)
        if os.path.isdir(full_path) or any(item.endswith(ext) for ext in extensions):
            files.append(item)
    return files
