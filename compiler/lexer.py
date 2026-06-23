import re
from errors import LexError
from ast_nodes import *

TOKEN_REGEX = re.compile(r"""
    (?P<STRING>"([^"\\]|\\.)*")
  | (?P<NUMBER>0[xX][0-9a-fA-F]+|\d+\.\d+|\d+)
  | (?P<NAME>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<OP>==|!=|>=|<=|[\[\]\(\),:=\+\-\*/%<>])
  | (?P<SKIP>[ \t]+)
  | (?P<COMMENT>//.*)
""", re.VERBOSE)


class Tok:
    def __init__(self, type_, value, line):
        self.type = type_
        self.value = value
        self.line = line


def tokenize(source: str):
    tokens = []
    includes = []
    indent_stack = [0]
    lineno = 0

    for raw_line in source.split('\n'):
        lineno += 1
        line = raw_line.rstrip('\r\n')
        stripped = line.strip()

        if stripped == '' or stripped.startswith('//'):
            continue

        if stripped.startswith('#include'):
            includes.append(stripped)
            continue

        norm = line.replace('\t', '    ')
        indent = len(norm) - len(norm.lstrip(' '))
        content = norm.strip()

        if indent > indent_stack[-1]:
            indent_stack.append(indent)
            tokens.append(Tok('INDENT', indent, lineno))

        while indent < indent_stack[-1]:
            indent_stack.pop()
            tokens.append(Tok('DEDENT', indent, lineno))

        if indent != indent_stack[-1]:
            raise LexError(f"Baris {lineno}: indentasi tidak konsisten")

        pos = 0
        while pos < len(content):
            m = TOKEN_REGEX.match(content, pos)
            if not m:
                raise LexError(f"Baris {lineno}: token tidak dikenal")

            kind = m.lastgroup
            val = m.group()
            pos = m.end()

            if kind in ('SKIP', 'COMMENT'):
                continue

            if kind == 'STRING':
                val = val[1:-1]

            tokens.append(Tok(kind, val, lineno))

        tokens.append(Tok('NEWLINE', None, lineno))

    while len(indent_stack) > 1:
        indent_stack.pop()
        tokens.append(Tok('DEDENT', 0, lineno))

    tokens.append(Tok('ENDMARKER', None, lineno))
    return tokens, includes