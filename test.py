import json

from babbisch.analyze import AnalyzingVisitor
from babbisch.utils import ASTCache

cache = ASTCache()
ast = cache['cairo.h']
try:
    v = AnalyzingVisitor()
    v.visit(ast)

    print v.to_json()
finally:
    cache.save()
