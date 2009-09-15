import os
from subprocess import Popen, PIPE

try:
    import cPickle as pickle
except ImportError:
    import pickle

from pycparser import CParser

from .filter import filter_headers, include_exclude

CACHE_FILENAME = 'header.cache'

def parse_file(filename, include_headers, exclude_headers, use_cpp=True):
    if use_cpp:
        path_list = ['cpp', '-U __GNUC__', filename]
        pipe = Popen(path_list,
                    stdout=PIPE,
                    universal_newlines=True)
        text = pipe.communicate()[0]
    else:
        text = open(filename).read()

    parser = CParser()
    # strip __extension__
    text = text.replace('__extension__', '')
    # filter headers
    text = filter_headers(text,
            include_exclude(include_headers, exclude_headers)
            )
    return parser.parse(text, filename)

class ASTCache(object):
    # TODO: store the mtime when loading the header. Otherwise it is
    # possible to store a mtime that is more recent than the header.

    def __init__(self, filename=CACHE_FILENAME, load=True, use_cpp=True):
        self.filename = filename
        self.use_cpp = use_cpp
        self.headers = {} # (filename, iheaders, xheaders): (mtime, ast)
        if load:
            self.load()

    def load(self):
        self.headers.clear()
        try:
            with open(self.filename, 'rb') as f:
                self.headers = pickle.load(f)
        except IOError:
            pass

    def save(self):
        with open(self.filename, 'wb') as f:
            pickle.dump(self.headers, f)

    def load_header(self, filename, include_headers, exclude_headers):
        key = (filename, include_headers, exclude_headers)
        self.headers[key] = (
                os.lstat(filename).st_mtime,
                parse_file(filename, include_headers, exclude_headers, use_cpp=self.use_cpp)
                )

    def get_header(self, filename, include_headers, exclude_headers):
        key = (filename, include_headers, exclude_headers)
        if key in self.headers:
            if os.lstat(key).st_mtime > self.headers[key][0]:
                self.load_header(filename, include_headers, exclude_headers)
        else:
            self.load_header(filename, include_headers, exclude_headers)
        return self.headers[key][1]

