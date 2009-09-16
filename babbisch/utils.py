import os
import sys
from subprocess import Popen, PIPE

from pkg_resources import resource_filename

try:
    import cPickle as pickle
except ImportError:
    import pickle

from pycparser import CParser
from pycparser.plyparser import ParseError

CACHE_FILENAME = 'header.cache'
HEADER_REPLACEMENTS = resource_filename('babbisch', 'headers')

def parse_file(filename, use_cpp=True):
    if use_cpp:
        path_list = [
                'cpp',
                '-U __GNUC__',
                '-isystem', os.path.join(HEADER_REPLACEMENTS, 'usr', 'include'),
                filename,
                ]
        print path_list
        pipe = Popen(path_list,
                    stdout=PIPE,
                    universal_newlines=True)
        text = pipe.communicate()[0]
    else:
        text = open(filename).read()

    parser = CParser()
    # strip __extension__
    text = text.replace('__extension__', '')
    try:
        return parser.parse(text, filename)
    except ParseError:
        print >>sys.stderr, text
        raise

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

    def load_header(self, filename):
        self.headers[filename] = (
                os.lstat(filename).st_mtime,
                parse_file(filename, use_cpp=self.use_cpp)
                )

    def get_header(self, filename):
        if filename in self.headers:
            if os.lstat(filename).st_mtime > self.headers[filename][0]:
                self.load_header(filename)
        else:
            self.load_header(filename)
        return self.headers[filename][1]

