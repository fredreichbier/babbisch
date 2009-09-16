import re
import shlex

FLAG_NEW_FILE = '1'
FLAG_RETURN = '2'

def include_exclude(include_regexes, exclude_regexes):
    def include(filename):
        return (any(re.match(regex, filename)
                    for regex in include_regexes) and not 
                any(re.match(regex, filename)
                    for regex in exclude_regexes))
    return include

def filter_headers(in_text, include):
    """
        return a modified version of the cpp-preprocessed string *in_text*
        without cpp information (lines starting with '#') and only
        containing headers where ``include(filename)`` returns True.
    """
    idx = 0
    unwanted = []
    depth = 0
    out_text = ''
    while idx < len(in_text):
        char = in_text[idx]
        if char == '#':
            # Ooooh, line!
            line = in_text[idx:in_text.index('\n', idx)]
            splitted = shlex.split(line[1:].strip())
            assert len(splitted) >= 2
            if len(splitted) == 2:
                linenum, filename = splitted
                flags = ()
            else:
                linenum, filename = splitted[:2]
                flags = splitted[2].split(' ')
            if FLAG_NEW_FILE in flags:
                if not include(filename):
                    unwanted.append(depth)
                depth += 1
            elif FLAG_RETURN in flags:
                depth -= 1
                if (unwanted and unwanted[-1] == depth):
                    del unwanted[-1]
#            else:
#                out_text += line + '\n' # no cpp information left. TODO: okay?
            idx += len(line)
            continue
        if not unwanted:
            out_text += in_text[idx]
        idx += 1
    return out_text
