import sys

import json

from babbisch.client import ObjectVisitor
from babbisch.tag import parse_string
from babbisch.odict import odict

from wraplib.codegen import Codegen, CodegenBase, INDENT, DEDENT
from wraplib.pyclass import PyClass

ctypes_type_map = {
    'void': 'None',
    'signed int': 'c_int',
    'unsigned int': 'c_uint',
    'long int': 'c_long',
    'unsigned long': 'c_ulong',
    'unsigned long int': 'c_ulong',
    'long long': 'c_longlong',
    'long long int': 'c_longlong',
    'unsigned long long int': 'c_ulonglong',
    'unsigned long long': 'c_ulonglong',
    'signed char': 'c_char',
    'unsigned char': 'c_ubyte',
    'signed short': 'c_short',
    'unsigned short': 'c_ushort',
    'float': 'c_float',
    'double': 'c_double',
    'size_t': 'c_size_t',
    'int8_t': 'c_int8',
    'int16_t': 'c_int16',
    'int32_t': 'c_int32',
    'int64_t': 'c_int64',
    'uint8_t': 'c_uint8',
    'uint16_t': 'c_uint16',
    'uint32_t': 'c_uint32',
    'uint64_t': 'c_uint64',
    'wchar_t': 'c_wchar',
    'ptrdiff_t': 'c_ptrdiff_t',  # Requires definition in preamble
}

class CtypesClass(PyClass):
    def __init__(self, client, name, obj):
        PyClass.__init__(self, name)
        self.client = client
        self.obj = obj

class CtypesCompound(CtypesClass):
    def __init__(self, client, name, obj):
        CtypesClass.__init__(self, client, name, obj)
        self._build_code()

    def _build_code(self):
        members = []
        for name, obj in self.obj['members']:
            obj = self.client.resolve_object(obj)
            members.append('("%s", %s)' % (
                    name,
                    self.client.resolve_type(obj)
                    ))
        if members:
            self.epilog.append('%s._fields_ = [%s]' % (self.name, ', '.join(members)))
            self.epilog.append('')

class CtypesEnum(CodegenBase):
    def __init__(self, client, name, obj):
        self.client = client
        self.name = name
        self.obj = obj

    def generate_code(self):
        code = []
        # an enum is a c_int
        code.append('%s = c_int' % self.name)
        for name, value in self.obj['members']:
            code.append('%s = %s' % (name, value))
        code.append('')
        return code

class CtypesFunction(CodegenBase):
    def __init__(self, client, name, obj):
        self.client = client
        self.name = name
        self.obj = obj
        # resolve all argument types NOW
        self.client.resolve_type(self.obj['rettype'])
        for argtype in odict(self.obj['argtypes']).itervalues():
            self.client.resolve_type(argtype)

    def generate_code(self):
        code = []
        code.append('%s = _lib.%s' % (self.name, self.name))
        code.append('%s.restype = %s' % (
            self.name,
            self.client.resolve_type(self.obj['rettype'])
            ))
        code.append('%s.argtypes = [%s]' % (
            self.name,
            ', '.join(self.client.resolve_type(argtype) for argtype in odict(self.obj['argtypes']).itervalues())
            ))
        code.append('')
        return code
        
class CtypesStruct(CtypesCompound):
    def __init__(self, client, name, obj):
        CtypesCompound.__init__(self, client, name, obj)
        self.base = 'Structure'

    def _build_code(self):
        members = []
        for name, obj, bitsize in self.obj['members']:
            obj = self.client.resolve_object(obj)
            if bitsize is not None:
                members.append('("%s", %s, %d)' % (
                        name,
                        self.client.resolve_type(obj),
                        bitsize
                        ))
            else:
                members.append('("%s", %s)' % (
                        name,
                        self.client.resolve_type(obj)
                        ))
        if members:
            self.epilog.append('%s._fields_ = [%s]' % (self.name, ', '.join(members)))
            self.epilog.append('')


class CtypesUnion(CtypesCompound):
    def __init__(self, client, name, obj):
        CtypesCompound.__init__(self, client, name, obj)
        self.base = 'Union'

class CtypesTypedef(CodegenBase):
    def __init__(self, client, name, obj):
        self.client = client
        self.name = name
        self.obj = obj
        
        target = self.client.resolve_type(obj['target'])
        self.code = '%s = %s' % (obj['tag'], target)

    def generate_code(self):
        return self.code

def anon_namegen():
    i = 0
    while True:
        yield 'anon%d' % i
        i += 1

class CtypesClient(ObjectVisitor):
    def __init__(self, objects, libname):
        self.objects = objects
        self.libname = libname

        self.anon_namegen = anon_namegen()

        self.wrappers = ctypes_type_map.copy() # tag: Python name
        self.wrapper_classes = odict() # Python name: Wrapper class

        self.prolog = []
        self.epilog = []

        self._build_prolog()

    def format_name(self, name):
        if name == '!None':
            return self.anon_namegen.next()
        else:
            return name

    def _build_prolog(self):
        self.prolog.extend([
                '# generated by babbisch_ctypes'
                '',
                'import ctypes',
                'from ctypes import *',
                'from ctypes.util import find_library',
                '',
                '_libpath = find_library("%s")' % self.libname,
                'if _libpath is None:',
                INDENT,
                'raise RuntimeError("Couldn\'t find library %s")' % self.libname,
                DEDENT,
                '',
                '_lib = ctypes.CDLL(_libpath)',
                '',
                ]
                )

    def add_wrapper_class(self, tag, pycls):
        self.wrapper_classes[pycls.name] = pycls
        self.wrappers[tag] = pycls.name

    def visit_all(self):
        self.visit_objects(self.objects)

    def generate_code(self):
        return (self.prolog
                + [c.generate_code() for c in self.wrapper_classes.itervalues()]
                + self.epilog)

    def resolve_object(self, type):
        if isinstance(type, basestring):
            return self.objects[type]
        else:
            return type

    def add_type(self, type):
        # ooOokay, it HAS to be an unknown type. Pointer or something.
        klass = type['class']
        tag = type['tag']
        if klass == 'Pointer':
            # it's a new pointer type!
            target = self.resolve_type(type['type'])
            if target.startswith('CFUNCTYPE'): # it's a CFUNCTYPE.
                # function pointers in ctypes are not POINTER(CFUNCTYPE(...)),
                # but just CFUNCTYPE.
                self.wrappers[tag] = target
            elif target == 'c_char':
                # it's a char array = a string.
                self.wrappers[tag] = 'c_char_p'
            else:
                self.wrappers[tag] = 'POINTER(%s)' % target
        elif klass == 'Struct':
            # it's a struct, I suggest it's unnamed?
            self.visit_Struct(type)
        elif klass == 'Array':
            # it's a new array type!
            arrtype = self.resolve_type(type['type'])
            if arrtype == 'c_char':
                # it's a char array = a string.
                type = 'c_char_p'
            elif type['size'] is None:
                type = 'POINTER(%s)' % arrtype
            else:
                type = '%s * %d' % (arrtype, type['size'])
            self.wrappers[tag] = type
        elif klass == 'FunctionType':
            pytype = 'CFUNCTYPE(%s)' % ', '.join(map(self.resolve_type, [type['rettype']] + type['argtypes']))
            self.wrappers[type['tag']] = pytype
        else:
            assert 0, "OH NO, what is that? %r" % type

    def resolve_type(self, type):
        if isinstance(type, basestring):
            # just a tag passed, let's hope it's already wrapped
            tag = type
        else:
            tag = type['tag']
            if tag not in self.wrappers:
                self.add_type(type)
        return self.wrappers[tag]

    def visit_Function(self, obj):
        name = obj['tag']
        # don't wrap functions with the "static" storage type
        if 'static' in obj['storage']:
            return
        wrapper = CtypesFunction(self, name, obj)
        self.add_wrapper_class(name, wrapper)

    def visit_Struct(self, obj):
        modifier, args = parse_string(obj['tag'])
        assert modifier == 'STRUCT'
        assert len(args) == 1
        name = 'struct_%s' % self.format_name(args[0])
        pycls = CtypesStruct(self, name, obj)
        self.add_wrapper_class(obj['tag'], pycls)

    def visit_Union(self, obj):
        modifier, args = parse_string(obj['tag'])
        assert modifier == 'UNION'
        assert len(args) == 1
        name = 'union_%s' % self.format_name(args[0])
        pycls = CtypesUnion(self, name, obj)
        self.add_wrapper_class(obj['tag'], pycls)

    def visit_Enum(self, obj):
        modifier, args = parse_string(obj['tag'])
        assert modifier == 'ENUM'
        assert len(args) == 1
        name = 'enum_%s' % self.format_name(args[0])
        wrapper = CtypesEnum(self, name, obj)
        self.add_wrapper_class(obj['tag'], wrapper)

    def visit_Typedef(self, obj):
        wrapper = CtypesTypedef(self, obj['tag'], obj)
        self.add_wrapper_class(obj['tag'], wrapper)

def code(c):
    return Codegen()(c.generate_code()).buf

with open(sys.argv[1], 'r') as f:
    visitor = CtypesClient(odict(json.load(f)), sys.argv[2])
    visitor.visit_all()
    print code(visitor)
