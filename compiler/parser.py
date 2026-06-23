# parser.py

from errors import ParseError
from ast_nodes import *

TYPE_KEYWORDS = ('integer', 'float', 'bool', 'string')
CMP_KEYWORDS = {'is': '==', 'not': '!=', 'bigger': '>', 'smaller': '<'}


class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.pos = 0

    # ---------------- UTIL ----------------

    def peek(self, offset=0):
        idx = self.pos + offset
        if idx >= len(self.toks):
            return self.toks[-1]
        return self.toks[idx]

    def at(self, type_, value=None):
        t = self.peek()
        if t.type != type_:
            return False
        if value is not None and t.value != value:
            return False
        return True

    def advance(self):
        t = self.toks[self.pos]
        if self.pos < len(self.toks) - 1:
            self.pos += 1
        return t

    def expect(self, type_, value=None):
        if not self.at(type_, value):
            t = self.peek()
            expected = f"{type_} {value!r}" if value else type_
            raise ParseError(
                f"Baris {t.line}: expected {expected}, got {t.type} {t.value!r}"
            )
        return self.advance()

    def skip_newlines(self):
        while self.at('NEWLINE'):
            self.advance()

    # ---------------- PROGRAM ----------------

    def parse_program(self):
        prog = Program()
        self.skip_newlines()

        while not self.at('ENDMARKER'):
            prog.body.append(self.parse_top_level())
            self.skip_newlines()

        return prog

    # ---------------- TOP LEVEL ----------------

    def parse_top_level(self):
        if self.at('NAME', 'let'):
            node = self.parse_var_decl()
            self.expect('NEWLINE')
            return node

        if self.at('NAME', 'command'):
            return self.parse_func_def(is_command=True)

        if self.at('NAME'):
            return self.parse_func_def(is_command=False)

        t = self.peek()
        raise ParseError(f"Baris {t.line}: invalid top-level statement")

    # ---------------- TYPE ----------------

    def parse_type(self):
        t = self.advance()

        if t.type != 'NAME' or t.value not in TYPE_KEYWORDS:
            raise ParseError(f"Baris {t.line}: unknown type {t.value!r}")

        vtype = t.value
        size = None

        if vtype == 'string':
            self.expect('OP', '[')
            size = self.expect('NUMBER').value
            self.expect('OP', ']')

        return vtype, size

    # ---------------- VARIABLE ----------------

    def parse_var_decl(self):
        self.expect('NAME', 'let')
        name = self.expect('NAME').value
        self.expect('OP', ':')

        vtype, size = self.parse_type()

        init = None
        if self.at('OP', '='):
            self.advance()
            init = self.parse_expr()

        return VarDecl(name, vtype, size, init)

    # ---------------- FUNCTION ----------------

    def parse_func_def(self, is_command):
        if is_command:
            self.expect('NAME', 'command')

        name = self.expect('NAME').value

        self.expect('OP', '(')
        params = self.parse_param_list()
        self.expect('OP', ')')

        self.expect('NEWLINE')
        self.expect('INDENT')

        body = self.parse_block()

        self.expect('DEDENT')

        return FuncDef(name, params, body, is_command)

    def parse_param_list(self):
        params = []

        if self.at('OP', ')'):
            return params

        while True:
            name = self.expect('NAME').value

            if self.at('OP', '['):
                self.advance()
                self.expect('OP', ']')
                name += '[]'

            params.append(name)

            if self.at('OP', ','):
                self.advance()
                continue
            break

        return params

    def parse_block(self):
        stmts = []
        self.skip_newlines()

        while not self.at('DEDENT') and not self.at('ENDMARKER'):
            stmts.append(self.parse_statement())
            self.skip_newlines()

        return stmts

    # ---------------- STATEMENT ----------------

    def parse_statement(self):
        if self.at('INDENT'):
            t = self.peek()
            raise ParseError(f"Baris {t.line}: unexpected indent")

        if self.at('NAME', 'let'):
            node = self.parse_var_decl()
            self.expect('NEWLINE')
            return node

        if self.at('NAME', 'if'):
            return self.parse_if()

        if self.at('NAME', 'return'):
            self.advance()

            expr = None
            if not self.at('NEWLINE'):
                expr = self.parse_expr()

            self.expect('NEWLINE')
            return Return(expr)

        if self.at('NAME'):
            name = self.advance().value

            # assign array
            if self.at('OP', '['):
                self.advance()
                idx = self.parse_expr()
                self.expect('OP', ']')
                self.expect('OP', '=')
                val = self.parse_expr()
                self.expect('NEWLINE')
                return Assign(name, val, index=idx)

            # assign normal
            if self.at('OP', '='):
                self.advance()
                val = self.parse_expr()
                self.expect('NEWLINE')
                return Assign(name, val)

            # function call
            if self.at('OP', '('):
                self.advance()
                args = self.parse_arg_list()
                self.expect('OP', ')')
                self.expect('NEWLINE')
                return ExprStmt(CallExpr(name, args))

        t = self.peek()
        raise ParseError(f"Baris {t.line}: invalid statement")

    # ---------------- IF ----------------

    def parse_if(self):
        self.expect('NAME', 'if')

        cond = self.parse_condition()

        self.expect('NEWLINE')
        self.expect('INDENT')

        body = self.parse_block()
        self.expect('DEDENT')

        node = If(cond, body)

        while self.at('NAME', 'else'):
            self.advance()

            if self.at('NAME', 'if'):
                self.advance()
                econd = self.parse_condition()

                self.expect('NEWLINE')
                self.expect('INDENT')

                ebody = self.parse_block()
                self.expect('DEDENT')

                node.elifs.append((econd, ebody))
            else:
                self.expect('NEWLINE')
                self.expect('INDENT')

                node.else_body = self.parse_block()
                self.expect('DEDENT')
                break

        return node

    # ---------------- CONDITION ----------------

    def parse_condition(self):
        node = self.parse_comparison()

        while self.at('NAME') and self.peek().value in ('and', 'or'):
            op = '&&' if self.advance().value == 'and' else '||'
            right = self.parse_comparison()
            node = Logic(op, node, right)

        return node

    def parse_comparison(self):
        left = self.parse_expr()

        if self.at('NAME') and self.peek().value in CMP_KEYWORDS:
            op = CMP_KEYWORDS[self.advance().value]
            right = self.parse_expr()
            return Compare(op, left, right)

        return left

    # ---------------- EXPRESSIONS ----------------

    def parse_arg_list(self):
        args = []

        if self.at('OP', ')'):
            return args

        while True:
            args.append(self.parse_expr())

            if self.at('OP', ','):
                self.advance()
                continue
            break

        return args

    def parse_expr(self):
        node = self.parse_term()

        while self.at('OP') and self.peek().value in ('+', '-'):
            op = self.advance().value
            right = self.parse_term()
            node = BinOp(op, node, right)

        return node

    def parse_term(self):
        node = self.parse_factor()

        while self.at('OP') and self.peek().value in ('*', '/', '%'):
            op = self.advance().value
            right = self.parse_factor()
            node = BinOp(op, node, right)

        return node

    def parse_factor(self):
        if self.at('OP', '-'):
            self.advance()
            return BinOp('-', Lit(0, 'number'), self.parse_factor())

        if self.at('OP', '('):
            self.advance()
            node = self.parse_expr()
            self.expect('OP', ')')
            return node

        if self.at('NUMBER'):
            v = self.advance().value
            if '.' in str(v):
                return Lit(float(v), 'number')
            return Lit(int(v), 'number')

        if self.at('STRING'):
            return Lit(self.advance().value, 'string')

        if self.at('NAME', 'true') or self.at('NAME', 'false'):
            return Lit(self.advance().value == 'true', 'bool')

        if self.at('NAME'):
            name = self.advance().value

            if self.at('OP', '('):
                self.advance()
                args = self.parse_arg_list()
                self.expect('OP', ')')
                return CallExpr(name, args)

            if self.at('OP', '['):
                self.advance()
                idx = self.parse_expr()
                self.expect('OP', ']')
                return Index(name, idx)

            return Ident(name)

        t = self.peek()
        raise ParseError(f"Baris {t.line}: invalid expression")