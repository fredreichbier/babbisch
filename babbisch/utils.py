import os

try:
    import cPickle as pickle
except ImportError:
    import pickle

from pycparser import parse_file

CACHE_FILENAME = 'header.cache'

class ASTCache(object):
    # TODO: store the mtime when loading the header. Otherwise it is
    # possible to store a mtime that is more recent than the header.

    def __init__(self, filename=CACHE_FILENAME, load=True, use_cpp=True):
        self.filename = filename
        self.use_cpp = use_cpp
        self.headers = {} # filename: (mtime, ast)
        if load:
            self.load()

    def load(self):
        self.headers.clear()
        try:
            with open(self.filename, 'rb') as f:
                self.headers =  pickle.load(f)
        except IOError:
            pass

    def save(self):
        with open(self.filename, 'wb') as f:
            pickle.dump(self.headers, f)

    def load_header(self, filename):
        self.headers[filename] = (
                os.lstat(filename).st_mtime,
                parse_file(filename, use_cpp=self.use_cpp)
                )

    def __getitem__(self, key):
        if key in self.headers:
            if os.lstat(key).st_mtime > self.headers[key][0]:
                self.load_header(key)
        else:
            self.load_header(key)
        return self.headers[key][1]

