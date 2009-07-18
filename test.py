import sys
import json

from babbisch.analyze import AnalyzingVisitor
from babbisch.utils import ASTCache

cache = ASTCache()
ast = cache[sys.argv[1]]
try:
    v = AnalyzingVisitor()
    v.visit(ast)

    print v.to_json(indent=4)
finally:
    cache.save()
