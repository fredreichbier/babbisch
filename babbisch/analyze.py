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

def format_type(type, objects):
    if type.tag in objects:
        type = type.tag
    return type

class Object(object):
    def __init__(self, coord, tag):
        self.coord = coord
        self.tag = tag

    def __repr__(self):
        return '<%s at 0x%x "%s">' % (
                self.__class__.__name__,
                id(self),
                self.tag)

    def get_state(self, objects):
        return {'coord': self.coord,
                'tag': self.tag,
                'class': self.__class__.__name__
                }

class Type(Object):
    pass

class Typedef(Object):
    def __init__(self, coord, tag, target):
        Object.__init__(self, coord, tag)
        self.target = target

    def get_state(self, objects):
        state = Object.get_state(self, objects)
        state.update({
            'target': format_type(self.target, objects)
            })
        return state

class Array(Object):
    def __init__(self, coord, type, size=None):
        tag = 'ARRAY(%s, %s)' % (type.tag, format_tag(size))
        Object.__init__(self, coord, tag)
        self.type = type
        self.size = size

    def get_state(self, objects):
        state = Object.get_state(self, objects)
        state.update({
            'type': format_type(self.type, objects),
            'size': self.size
            })
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

    def get_state(self, objects):
        state = Type.get_state(self, objects)
        state.update({
            'name': self.name,
            'members': [(name, format_type(typ, objects))
                for name, typ in self.members.iteritems()
                ]
            })
        return state

class Struct(Compound):
    modifier = 'STRUCT(%s)'

    def add_member(self, name, type, bitsize):
        self.members[name] = (type, bitsize)

    def get_state(self, objects):
        state = Type.get_state(self, objects)
        state.update({
            'name': self.name,
            'members': [(name, format_type(typ, objects), bitsize)
                for name, (typ, bitsize) in self.members.iteritems()
                ]
            })
        return state

class Enum(Compound):
    modifier = 'ENUM(%s)'

    def add_member(self, name, type):
        self.members[name] = type

    def get_state(self, objects):
        state = Type.get_state(self, objects)
        state.update({
            'name': self.name,
            'members': self.members.items()
            })
        return state

class Union(Compound):
    modifier = 'UNION(%s)'

class Pointer(Type):
    def __init__(self, coord, type):
        Type.__init__(self, coord, 'POINTER(%s)' % format_tag(type.tag))
        self.type = type

    def get_state(self, objects):
        state = Type.get_state(self, objects)
        state.update({
            'type': format_type(self.type, objects)
            })
        return state

class Function(Object):
    def __init__(self, coord, name, rettype, arguments, varargs=False, storage=None):
        Object.__init__(self, coord, format_tag(name))
        if storage is None:
            storage = []
        self.name = name
        self.rettype = rettype
        self.arguments = arguments
        self.varargs = varargs
        self.storage = storage

    def get_state(self, objects):
        state = Object.get_state(self, objects)
        # only include arguments that are not well-known,
        # otherwise just use the tag as value.
        arguments = []
        for name, type in self.arguments.iteritems():
            arguments.append((name, format_type(type, objects)))
        # same for rettype
        rettype = format_type(self.rettype, objects)
        state.update({
            'name': self.name,
            'rettype': rettype,
            'arguments': arguments,
            'varargs': self.varargs,
            'storage': self.storage,
            })
        return state

class FunctionType(Object):
    def __init__(self, coord, rettype, argtypes, varargs=False):
        # construct the tag
        tag = 'FUNCTIONTYPE(%s)' % (', '.join(a.tag for a in ([rettype] + argtypes)))

        Object.__init__(self, coord, tag)
        self.rettype = rettype
        self.argtypes = argtypes
        self.varargs = varargs

    def get_state(self, objects):
        state = Object.get_state(self, objects)
        # only include argtypes that are not well-known,
        # otherwise just use the tag as value.
        argtypes = []
        for type in self.argtypes:
            argtypes.append(format_type(type, objects))
        # same for rettype
        rettype = format_type(self.rettype, objects)
        state.update({
            'rettype': rettype,
            'argtypes': argtypes,
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
                default=lambda obj: obj.get_state(self.objects),
                **kwargs)

    def generic_visit(self, node):
        # new generic visit method: just do nothing for unknown nodes.
        pass

    def visit_Decl(self, node):
        # visit type node and set storage info if type is a FuncDecl.
        # TODO: what to do otherwise?
        if isinstance(node.type, c_ast.FuncDecl):
            obj = self.visit(node.type)
            obj.storage.extend(node.storage)

    def visit_FuncDef(self, node):
        # FuncDefs contain FuncDecls. Just handle it if
        # it isn't already known.
        if node.decl.name not in self.objects:
            self.visit(node.decl.type)

    def visit_FileAST(self, node):
        for child in node.children():
            self.visit(child)

    def resolve_type(self, node):
        if isinstance(node, c_ast.IdentifierType):
            name = ' '.join(reversed(node.names))
            return self.objects[name]
        elif isinstance(node, c_ast.PtrDecl):
            # ignoring qualifiers here
            return Pointer(format_coord(node.coord), self.resolve_type(node.type))
        elif isinstance(node, c_ast.FuncDecl):
            # that's a function pointer declaration, get the function type
            return self.make_functiontype(node)
        elif isinstance(node, (c_ast.Struct, c_ast.Enum, c_ast.Union)):
            # revisit structs, enums, unions
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

    def _add_compound_members(self, obj, node):
        if node.decls is None:
##            print 'No decls: ',
##            node.show()
            return
        for decl in node.decls:
            # ignoring qualifiers and storage classes here
            name = decl.name
            type = self.resolve_type(decl.type)
            if isinstance(obj, Struct):
                bitsize = None
                if decl.bitsize is not None:
                    bitsize = resolve_constant(decl.bitsize)
                obj.add_member(name, type, bitsize)
            else:
                obj.add_member(name, type)

    def make_functiontype(self, node):
        # don't get the name
        # first, handle the return type
        rettype = self.resolve_type(node.type)
        # then, handle the argument types.
        # Here, argtypes is just a list (no names included)
        argtypes = []
        varargs = False
        for param in node.args.params:
            if isinstance(param, c_ast.EllipsisParam):
                varargs = True
            elif (len(node.args.params) == 1
                    and param.name is None
                    and isinstance(param.type.type, c_ast.IdentifierType)
                    and param.type.type.names == ['void']):
                # it's the single `void` parameter signalizing
                # that there are no arguments.
                break
            else:
                argtypes.append(self.resolve_type(param.type))
        obj = FunctionType(format_coord(node.coord), rettype, argtypes, varargs)
        return obj

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
        # now, add all values, if there are any
        if node.values is not None:
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
        type = Typedef(format_coord(node.coord), node.name, self.resolve_type(node.type))
        self.add_type(type)
        return type

    def visit_FuncDecl(self, node):
        # get the name, recursively
        type = node.type
        while not isinstance(type, c_ast.TypeDecl):
            type = type.type
        name = type.declname
        # first, handle the return type
        rettype = self.resolve_type(node.type)
        # then, handle the argument types
        arguments = odict()
        varargs = False
        for param in node.args.params:
            if isinstance(param, c_ast.EllipsisParam):
                varargs = True
            elif (len(node.args.params) == 1
                    and param.name is None
                    and isinstance(param.type.type, c_ast.IdentifierType)
                    and param.type.type.names == ['void']):
                # it's the single `void` parameter signalizing
                # that there are no arguments.
                break
            else:
                arguments[param.name] = self.resolve_type(param.type)
        obj = Function(format_coord(node.coord), name, rettype, arguments, varargs)
        if name is not None:
            self.add_type(obj)
        return obj

