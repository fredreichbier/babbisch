from __future__ import with_statement

import os.path
from optparse import OptionParser

from babbisch.utils import ASTCache
from babbisch.analyze import AnalyzingVisitor

USAGE = 'usage: %prog [options] headerfile...'
FORMATS = {
        'json': lambda visitor: visitor.to_json(indent=2)
        }

def main():
    parser = OptionParser(usage=USAGE)
    parser.add_option('--no-cache',
            action='store_false',
            dest='cache',
            default=True,
            help="don't create a header cache file",
            )
    parser.add_option('-f', '--format',
            action='store',
            choices=FORMATS.keys(),
            dest='format',
            default='json',
            help="defines the output format to use [supported: json]",
            )
    parser.add_option('-i', '--include-header',
            action='append',
            dest='include_headers',
            default=[],
            help="""include headers whose filename matches REGEX""",
            metavar='REGEX'
            )
    parser.add_option('-x', '--exclude-header',
            action='append',
            dest='exclude_headers',
            default=[],
            help="""exclude headers whose filename matches REGEX (even if they would be included by the -i option)""",
            metavar='REGEX'
            )
    parser.add_option('-o',
            action='store',
            dest='output',
            default=None,
            help="defines the output filename [default: stdout]",
            )
    options, args = parser.parse_args()
    if not args:
        parser.error("You have to specify at least one input file")

    # read and analyze all source files
    visitor = AnalyzingVisitor()
    cache = ASTCache(load=options.cache)
    try:
        for filename in args:
            if not os.path.isfile(filename):
                parser.error("'%s' is not a valid filename" % filename)
            else:
                path = os.path.abspath(filename)
                ast = cache.get_header(path,
                        tuple(options.include_headers),
                        tuple(options.exclude_headers))
                visitor.visit(ast)
    finally:
        if options.cache:
            cache.save()

    # output
    stuff = FORMATS[options.format](visitor)
    if options.output is None:
        # just print it
        print stuff
    else:
        with open(options.output, 'w') as f:
            f.write(stuff)

