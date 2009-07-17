import json

from babbisch.analyze import AnalyzingVisitor
from babbisch.utils import ASTCache

cache = ASTCache()
ast = cache['test.h']
try:
    v = AnalyzingVisitor()
    v.visit(ast)

    print v.to_json(indent=4)
finally:
    cache.save()
