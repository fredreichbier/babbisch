# -*- coding: utf-8 -*-

from pycparser import c_parser, c_ast, parse_file

from .odict import odict

def format_tag(something):
    """
        if *something* is None, return "!None". Otherwise,
        return *something*.
    """
    if something is None:
        return '!None'
    else:
        return something

def format_coord(coord):
    if coord is not None:
        return {'file': coord.file, 'line': coord.line}
    else:
        return None

class Object(object):
    def __init__(self, coord, tag):
        self.coord = coord
        self.tag = tag

    def __repr__(self):
        return '<%s at 0x%x "%s">' % (
                self.__class__.__name__,
                id(self),
                self.tag)

    def __getstate__(self):
        return {'coord': self.coord,
                'tag': self.tag,
                'type': self.__class__.__name__}

class Type(Object):
    pass

class Typedef(Object):
    def __init__(self, coord, tag, target):
        Object.__init__(self, coord, tag)
        self.target = target

    def __getstate__(self):
        state = Object.__getstate__(self)
        state.update({'target': self.target})
        return state

class Array(Object):
    def __init__(self, coord, target, size=None):
        tag = 'ARRAY(%s, %s)' % (target.tag, format_tag(size))
        Object.__init__(self, coord, tag)
        self.target = target
        self.size = size

    def __getstate__(self):
        state = Object.__getstate__(self)
        state.update({'target': self.target, 'size': self.size})
        return state

class PrimitiveType(Type):
    pass

class Compound(Type):
    modifier = '%s'

    def __init__(self, coord, name, members=()):
        Type.__init__(self, coord, type(self).modifier % format_tag(name))
        self.name = name
        self.members = odict()
        self.add_members(members)

    def add_members(self, members):
        if not members:
            return
        if not isinstance(members, odict):
            members = odict(members)
        self.members.update(members)

    def add_member(self, name, type):
        self.members[name] = type

    def __getstate__(self):
        state = Type.__getstate__(self)
        state.update({
            'name': self.name,
            'members': self.members.items()
            })
        return state

class Struct(Compound):
    modifier = 'STRUCT(%s)'

class Enum(Compound):
    modifier = 'ENUM(%s)'

class Union(Compound):
    modifier = 'UNION(%s)'

class Pointer(Type):
    def __init__(self, coord, type):
        Type.__init__(self, coord, 'POINTER(%s)' % format_tag(type.tag))
        self.type = type

class Function(Object):
    def __init__(self, coord, name, rettype, argtypes, varargs=False):
        Object.__init__(self, coord, format_tag(name))
        self.name = name
        self.rettype = rettype
        self.argtypes = argtypes
        self.varargs = varargs

    def __getstate__(self):
        state = Object.__getstate__(self)
        state.update({
            'name': self.name,
            'rettype': self.rettype,
            'argtypes': self.argtypes.items(),
            'varargs': self.varargs
            })
        return state

TYPES = ('void',
         'signed char',
         'unsigned char',
         'signed byte',
         'unsigned byte',
         'signed short',
         'unsigned short',
         'signed int',
         'unsigned int',
         'signed long',
         'unsigned long',
         'double',
         'float',
         )
SYNONYMS = {
        'char': 'signed char',
        'byte': 'signed byte',
        'short': 'signed short',
        'int': 'signed int',
        'long': 'signed long',
        }

def _get_builtins():
    d = dict((name, PrimitiveType(None, name)) for name in TYPES)
    for synonym, of in SYNONYMS.iteritems():
        d[synonym] = d[of]
    return d

BUILTINS = _get_builtins()
del TYPES
del SYNONYMS
del _get_builtins

def _int(value):
    if value.startswith('0x'):
        return int(value, base=16)
    elif value.startswith('0'):
        return int(value, base=8)
    else:
        return int(value)

CONSTANT_TYPES = {
        'int': _int,
        }

def resolve_constant(node):
    return CONSTANT_TYPES[node.type](node.value)

class AnalyzingVisitor(c_ast.NodeVisitor):
    def __init__(self, builtins=BUILTINS):
        self.objects = odict() # typedefs, structs, unions, enums, stuff, functions go here
        self.objects.update(builtins)

    def to_json(self, **kwargs):
        import json
        return json.dumps(self.objects.items(),
                default=lambda obj: obj.__getstate__(),
                **kwargs)

    def generic_visit(self, node):
        print node
        c_ast.NodeVisitor.generic_visit(self, node)

    def resolve_type(self, node):
        if isinstance(node, c_ast.IdentifierType):
            name = ' '.join(reversed(node.names))
            return self.objects[name]
        elif isinstance(node, c_ast.PtrDecl):
            # ignoring qualifiers here
            return Pointer(format_coord(node.coord), self.resolve_type(node.type))
        elif isinstance(node,
                (c_ast.Struct, c_ast.Enum, c_ast.Union, c_ast.FuncDecl)):
            # revisit structs, enums, unions and funcs
            return self.visit(node)
        elif isinstance(node, c_ast.TypeDecl):
            # just ignoring TypeDecl nodes is not nice, but I don't
            # know what else I should do.
            return self.resolve_type(node.type)
        elif isinstance(node, c_ast.ArrayDecl):
            # create an array object for arrays.
            dim = None
            if node.dim is not None:
                dim = resolve_constant(node.dim)
            return Array(format_coord(node.coord),
                    self.resolve_type(node.type),
                    dim
                    )
        else:
            print 'Unknown type: ',
            node.show()

    def add_type(self, type):
        self.objects[type.tag] = type

    def visit_FuncDecl(self, node):
        return_type = self.resolve_type(node.type.type)

    def _add_compound_members(self, obj, node):
        if node.decls is None:
##            print 'No decls: ',
##            node.show()
            return
        for decl in node.decls:
            # ignoring qualifiers and storage classes here
            name = decl.name
            type = self.resolve_type(decl.type)
            obj.add_member(name, type)

    def visit_Struct(self, node):
        type = Struct(format_coord(node.coord), node.name)
        # add the members
        self._add_compound_members(type, node)
        # if the struct is not anonymous, add it to
        # the list of known objects
        if node.name is not None:
            self.add_type(type)
        # return it, so visit_Typedef can handle anonymous structs
        return type

    def visit_Union(self, node):
        type = Union(format_coord(node.coord), node.name)
        # add the members
        self._add_compound_members(type, node)
        # if the union is not anonymous, add it to
        # the list of known objects
        if node.name is not None:
            self.add_type(type)
        # return it, so visit_Typedef can handle anonymous structs
        return type
    
    def visit_Enum(self, node):
        type = Enum(format_coord(node.coord), node.name)
        # now, add all values
        value = 0
        for enumerator in node.values.enumerators:
            name = enumerator.name
            if enumerator.value is not None:
                value = resolve_constant(enumerator.value)
            type.add_member(name, value)
            value += 1
        # if the enum is not anonymous, add it to
        # the list of known objects
        if node.name is not None:
            self.add_type(type)
        return type

    def visit_Typedef(self, node):
        # ignoring storage classes and qualifiers here
        # get the type object
        type = Typedef(format_coord(node.coord), node.name, self.resolve_type(node.type.type))
        self.add_type(type)
        return type

    def visit_FuncDecl(self, node):
        # get the name, recursively
        type = node.type
        while not isinstance(type, c_ast.TypeDecl):
            type = type.type
        name = type.declname
        # first, handle the return type
        rettype = self.resolve_type(node.type.type)
        # then, handle the argument types
        argtypes = odict()
        varargs = False
        for param in node.args.params:
            if isinstance(param, c_ast.EllipsisParam):
                varargs = True
            else:
                argtypes[param.name] = self.resolve_type(param.type)
        obj = Function(format_coord(node.coord), name, rettype, argtypes, varargs)
        if name is not None:
            self.add_type(obj)
        return obj

