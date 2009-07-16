import os

try:
    import cPickle as pickle
except ImportError:
    import pickle

from pycparser import parse_file

CACHE_FILENAME = 'header.cache'

class ASTCache(dict):
    # TODO: store the mtime when loading the header. Otherwise it is
    # possible to store a mtime that is more recent than the header.

    def __init__(self, filename=CACHE_FILENAME):
        self.filename = filename
        self.load()

    def load(self):
        self.clear()
        try:
            with open(self.filename, 'rb') as f:
                for header, (mtime, ast) in pickle.load(f).iteritems():
                    # if the last modification time is more recent than
                    # in the cache, reload it
                    if os.stat(header).st_mtime > mtime:
                        self[header]
                    else:
                        self[header] = ast
        except IOError:
            pass

    def save(self):
        to_save = {}
        for header, ast in self.iteritems():
            to_save[header] = (os.stat(header).st_mtime, ast)
        with open(self.filename, 'wb') as f:
            pickle.dump(to_save, f)
    
    def __missing__(self, key):
        self[key] = ast = parse_file(key)
        return ast
