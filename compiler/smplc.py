#!/usr/bin/env python3
"""
Samp Language Compiler
==========================
Compiler for SAMP LANGUAGE (.smpl) -> Pawn (.pwn) for SA-MP / open.mp servers.

Usage:
    python smplc.py file.smpl

The generated .pwn file will be written next to the .smpl source.
"""

import sys
import os
import re

from callbacks import CALLBACKS, CALLBACK_PARAM_COUNT
from natives import NATIVES

VERSION = "0.2.0"


# 1. ERRORS


class LexError(Exception):
    def __init__(self, msg, line=None):
        super().__init__(msg)
        self.line = line


class ParseError(Exception):
    def __init__(self, msg, line=None):
        super().__init__(msg)
        self.line = line


class CompileError(Exception):
    def __init__(self, msg, line=None):
        super().__init__(msg)
        self.line = line


# 2. LEXER


TOKEN_REGEX = re.compile(r"""
    (?P<STRING>"([^"\\]|\\.)*")
  | (?P<NUMBER>0[xX][0-9a-fA-F]+|\d+\.\d+|\d+)
  | (?P<NAME>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<OP>==|!=|>=|<=|[\[\]\(\),:=\+\-\*/%<>])
  | (?P<SKIP>[ \t]+)
  | (?P<COMMENT>//.*)
""", re.VERBOSE)


class Tok:
    __slots__ = ('type', 'value', 'line')

    def __init__(self, type_, value, line):
        self.type = type_
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Tok({self.type}, {self.value!r}, line={self.line})"


def tokenize(source: str):
    """Convert .smpl source into a list of tokens + raw preprocessor directives."""
    tokens = []
    directives = []
    indent_stack = [0]
    lineno = 0

    for raw_line in source.split('\n'):
        lineno += 1
        line = raw_line.rstrip('\r\n')
        stripped = line.strip()

        if stripped == '' or stripped.startswith('//'):
            continue

        if stripped.startswith('#'):
            directives.append(stripped)
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
            raise LexError(
                f"Line {lineno}: inconsistent indentation. Expected {indent_stack[-1]} spaces, got {indent}.",
                line=lineno
            )

        pos = 0
        line_has_token = False
        while pos < len(content):
            m = TOKEN_REGEX.match(content, pos)
            if not m:
                raise LexError(
                    f"Line {lineno}: unknown character/token near '{content[pos:pos+10]}'",
                    line=lineno
                )
            kind = m.lastgroup
            val = m.group()
            pos = m.end()
            if kind in ('SKIP', 'COMMENT'):
                continue
            if kind == 'STRING':
                val = val[1:-1]
            tokens.append(Tok(kind, val, lineno))
            line_has_token = True
        if line_has_token:
            tokens.append(Tok('NEWLINE', None, lineno))

    while len(indent_stack) > 1:
        indent_stack.pop()
        tokens.append(Tok('DEDENT', 0, lineno))
    tokens.append(Tok('ENDMARKER', None, lineno))
    return tokens, directives


# 3. AST NODES


class Node:
    pass


class Program(Node):
    def __init__(self):
        self.body = []


class VarDecl(Node):
    def __init__(self, name, vtype, size, init):
        self.name = name
        self.vtype = vtype
        self.size = size
        self.init = init


class Assign(Node):
    def __init__(self, name, expr, index=None, op='=', line=None):
        self.name = name
        self.expr = expr
        self.index = index
        self.op = op
        self.line = line


class Return(Node):
    def __init__(self, expr):
        self.expr = expr


class If(Node):
    def __init__(self, cond, body):
        self.cond = cond
        self.body = body
        self.elifs = []
        self.else_body = None


class FuncDef(Node):
    def __init__(self, name, params, body, is_command=False, is_regular=False):
        self.name = name
        self.params = params
        self.body = body
        self.is_command = is_command
        self.is_regular = is_regular


class CallExpr(Node):
    def __init__(self, name, args, line):
        self.name = name
        self.args = args
        self.line = line


class ExprStmt(Node):
    def __init__(self, expr):
        self.expr = expr


class BinOp(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right


class Compare(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right


class Logic(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right


class Ident(Node):
    def __init__(self, name, line):
        self.name = name
        self.line = line


class Lit(Node):
    def __init__(self, value, kind):
        self.value = value
        self.kind = kind


class Index(Node):
    def __init__(self, name, index, line):
        self.name = name
        self.index = index
        self.line = line


# 4. PARSER


CMP_KEYWORDS = {'is': '==', 'not': '!=', 'bigger': '>', 'smaller': '<'}
TYPE_KEYWORDS = ('integer', 'float', 'bool', 'string')


class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.pos = 0

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
            expected = f"{type_} {value!r}" if value is not None else type_
            raise ParseError(
                f"Line {t.line}: expected {expected}, got {t.type} {t.value!r}",
                line=t.line
            )
        return self.advance()

    def skip_newlines(self):
        while self.at('NEWLINE'):
            self.advance()

    def parse_program(self):
        prog = Program()
        self.skip_newlines()
        while not self.at('ENDMARKER'):
            prog.body.append(self.parse_top_level())
            self.skip_newlines()
        return prog

    def parse_top_level(self):
        # Handle INDENT error early
        if self.at('INDENT'):
            t = self.peek()
            raise ParseError(
                f"Line {t.line}: unexpected indentation at top level.",
                line=t.line
            )
        if self.at('NAME', 'let'):
            d = self.parse_var_decl()
            self.expect('NEWLINE')
            return d
        if self.at('NAME', 'command'):
            return self.parse_func_def(is_command=True)
        if self.at('NAME', 'function'):
            self.advance()  # consume 'function'
            return self.parse_func_def(is_command=False, is_regular=True)
        if self.at('NAME'):
            # Callback function (without 'function' keyword)
            return self.parse_func_def(is_command=False, is_regular=False)
        t = self.peek()
        raise ParseError(f"Line {t.line}: invalid top-level statement: {t.value!r}", line=t.line)

    def parse_type(self):
        t = self.advance()
        if t.type != 'NAME' or t.value not in TYPE_KEYWORDS:
            raise ParseError(f"Line {t.line}: unknown data type: {t.value!r}", line=t.line)
        vtype = t.value
        size = None
        if vtype == 'string':
            self.expect('OP', '[')
            size_tok = self.advance()
            if size_tok.type not in ('NUMBER', 'NAME'):
                raise ParseError(
                    f"Line {size_tok.line}: string size must be a number or constant, "
                    f"got {size_tok.type} {size_tok.value!r}",
                    line=size_tok.line
                )
            size = str(size_tok.value)
            self.expect('OP', ']')
        return vtype, size

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

    def parse_func_def(self, is_command, is_regular=False):
        if is_command:
            # 'command' keyword already consumed
            pass
        name = self.expect('NAME').value
        self.expect('OP', '(')
        params = self.parse_param_list()
        self.expect('OP', ')')
        self.expect('NEWLINE')
        self.expect('INDENT')
        body = self.parse_block()
        self.expect('DEDENT')
        return FuncDef(name, params, body, is_command, is_regular)

    def parse_block(self):
        stmts = []
        self.skip_newlines()
        while not self.at('DEDENT') and not self.at('ENDMARKER'):
            stmts.append(self.parse_statement())
            self.skip_newlines()
        return stmts

    def parse_statement(self):
        if self.at('INDENT'):
            t = self.peek()
            raise ParseError(
                f"Line {t.line}: unexpected indentation.",
                line=t.line
            )
        if self.at('NAME', 'let'):
            d = self.parse_var_decl()
            self.expect('NEWLINE')
            return d
        if self.at('NAME', 'if'):
            return self.parse_if()
        if self.at('NAME', 'return'):
            self.advance()
            expr = None
            if not self.at('NEWLINE') and not self.at('DEDENT') and not self.at('ENDMARKER'):
                expr = self.parse_expr()
            self.expect('NEWLINE')
            return Return(expr)
        if self.at('NAME'):
            name_token = self.peek()
            name = name_token.value
            line = name_token.line
            self.advance()
            # Check for function call: NAME '('
            if self.at('OP', '('):
                self.advance()
                args = self.parse_arg_list()
                self.expect('OP', ')')
                self.expect('NEWLINE')
                return ExprStmt(CallExpr(name, args, line))
            # Check for array index
            idx = None
            if self.at('OP', '['):
                self.advance()
                idx = self.parse_expr()
                self.expect('OP', ']')
            # Check for assignment operators
            op = '='
            if self.at('OP', '+') and self.peek(1).value == '=':
                self.advance()
                self.advance()
                op = '+='
            elif self.at('OP', '-') and self.peek(1).value == '=':
                self.advance()
                self.advance()
                op = '-='
            else:
                self.expect('OP', '=')
            val = self.parse_expr()
            self.expect('NEWLINE')
            return Assign(name, val, index=idx, op=op, line=line)
        t = self.peek()
        raise ParseError(f"Line {t.line}: invalid statement: {t.value!r}", line=t.line)

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

    def parse_comparison(self):
        left = self.parse_expr()
        if self.at('NAME', 'bigger') and self.peek(1).type == 'NAME' and self.peek(1).value == 'is':
            self.advance()
            self.advance()
            op = '>='
        elif self.at('NAME', 'smaller') and self.peek(1).type == 'NAME' and self.peek(1).value == 'is':
            self.advance()
            self.advance()
            op = '<='
        elif self.at('NAME') and self.peek().value in CMP_KEYWORDS:
            op = CMP_KEYWORDS[self.advance().value]
        else:
            return left
        right = self.parse_expr()
        return Compare(op, left, right)

    def parse_condition(self):
        node = self.parse_comparison()
        while self.at('NAME') and self.peek().value in ('and', 'or'):
            op = '&&' if self.advance().value == 'and' else '||'
            rhs = self.parse_comparison()
            node = Logic(op, node, rhs)
        return node

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
            rhs = self.parse_term()
            node = BinOp(op, node, rhs)
        return node

    def parse_term(self):
        node = self.parse_factor()
        while self.at('OP') and self.peek().value in ('*', '/', '%'):
            op = self.advance().value
            rhs = self.parse_factor()
            node = BinOp(op, node, rhs)
        return node

    def parse_factor(self):
        if self.at('OP', '-'):
            self.advance()
            if self.at('NUMBER'):
                raw = self.advance().value
                if raw.lower().startswith('0x'):
                    return Lit('-' + raw, 'hex')
                if '.' in raw:
                    return Lit(-float(raw), 'number')
                return Lit(-int(raw), 'number')
            node = self.parse_factor()
            return BinOp('-', Lit(0, 'number'), node)
        if self.at('OP', '('):
            self.advance()
            node = self.parse_expr()
            self.expect('OP', ')')
            return node
        if self.at('NUMBER'):
            raw = self.advance().value
            if raw.lower().startswith('0x'):
                return Lit(raw, 'hex')
            if '.' in raw:
                return Lit(float(raw), 'number')
            return Lit(int(raw), 'number')
        if self.at('STRING'):
            v = self.advance().value
            return Lit(v, 'string')
        if self.at('NAME', 'true') or self.at('NAME', 'false'):
            v = self.advance().value
            return Lit(v == 'true', 'bool')
        if self.at('NAME'):
            name_token = self.peek()
            name = name_token.value
            line = name_token.line
            self.advance()
            if self.at('OP', '('):
                self.advance()
                args = self.parse_arg_list()
                self.expect('OP', ')')
                return CallExpr(name, args, line)
            if self.at('OP', '['):
                self.advance()
                idx = self.parse_expr()
                self.expect('OP', ']')
                return Index(name, idx, line)
            return Ident(name, line)
        t = self.peek()
        raise ParseError(f"Line {t.line}: invalid expression at '{t.value!r}'", line=t.line)


# 5. SEMANTIC ANALYZER


class SymbolTable:
    def __init__(self, parent=None):
        self.symbols = {}
        self.parent = parent

    def declare(self, name, kind):
        if name in self.symbols:
            raise CompileError(f"Symbol '{name}' already declared in this scope")
        self.symbols[name] = kind

    def lookup(self, name):
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def enter_scope(self):
        return SymbolTable(self)

    def exit_scope(self):
        return self.parent


class SemanticAnalyzer:
    def __init__(self):
        self.global_scope = SymbolTable()
        self.current_scope = self.global_scope
        self.errors = []
        self.funcs_needing_forward = []

    def analyze(self, prog):
        # Register built-ins
        for name in NATIVES:
            self.global_scope.declare(name, 'native')
        # Register callbacks
        for name in CALLBACKS:
            self.global_scope.symbols[name] = 'callback'
        self.global_scope.declare('Send', 'native')
        self.global_scope.declare('GetParams', 'native')

        # First pass: collect global declarations
        for node in prog.body:
            if isinstance(node, VarDecl):
                self.global_scope.declare(node.name, 'var')
            elif isinstance(node, FuncDef):
                if node.is_regular:
                    self.global_scope.declare(node.name, 'func')
                    self.funcs_needing_forward.append(node.name)
                elif node.name in CALLBACKS:
                    pass  # already registered
                else:
                    raise CompileError(
                        f"Function '{node.name}' must be declared with 'function' keyword or be a known callback."
                    )

        # Second pass: analyze function bodies and global initializers
        for node in prog.body:
            if isinstance(node, FuncDef):
                self.visit_funcdef(node)
            elif isinstance(node, VarDecl):
                if node.init:
                    self.visit_expr(node.init)

        return self.errors

    def visit_funcdef(self, node):
        old_scope = self.current_scope
        self.current_scope = self.global_scope.enter_scope()
        for param in node.params:
            name = param.replace('[]', '')
            self.current_scope.declare(name, 'param')
        for stmt in node.body:
            self.visit_stmt(stmt)
        self.current_scope = old_scope

    def visit_stmt(self, stmt):
        if isinstance(stmt, VarDecl):
            self.current_scope.declare(stmt.name, 'var')
            if stmt.init:
                self.visit_expr(stmt.init)
        elif isinstance(stmt, Assign):
            if not self.current_scope.lookup(stmt.name):
                self.errors.append(f"Undefined variable '{stmt.name}' (line {stmt.line})")
            if stmt.index:
                self.visit_expr(stmt.index)
            self.visit_expr(stmt.expr)
        elif isinstance(stmt, Return):
            if stmt.expr:
                self.visit_expr(stmt.expr)
        elif isinstance(stmt, ExprStmt):
            self.visit_expr(stmt.expr)
        elif isinstance(stmt, If):
            self.visit_expr(stmt.cond)
            old_scope = self.current_scope
            self.current_scope = self.current_scope.enter_scope()
            for s in stmt.body:
                self.visit_stmt(s)
            self.current_scope = old_scope
            for econd, ebody in stmt.elifs:
                self.visit_expr(econd)
                old_scope = self.current_scope
                self.current_scope = self.current_scope.enter_scope()
                for s in ebody:
                    self.visit_stmt(s)
                self.current_scope = old_scope
            if stmt.else_body:
                old_scope = self.current_scope
                self.current_scope = self.current_scope.enter_scope()
                for s in stmt.else_body:
                    self.visit_stmt(s)
                self.current_scope = old_scope

    def visit_expr(self, expr):
        if isinstance(expr, Ident):
            if not self.current_scope.lookup(expr.name):
                self.errors.append(f"Undefined symbol '{expr.name}' (line {expr.line})")
        elif isinstance(expr, CallExpr):
            if not self.current_scope.lookup(expr.name):
                self.errors.append(f"Undefined function '{expr.name}' (line {expr.line})")
            for arg in expr.args:
                self.visit_expr(arg)
        elif isinstance(expr, Index):
            self.visit_expr(expr.index)
            if not self.current_scope.lookup(expr.name):
                self.errors.append(f"Undefined array '{expr.name}' (line {expr.line})")
        elif isinstance(expr, BinOp):
            self.visit_expr(expr.left)
            self.visit_expr(expr.right)
        elif isinstance(expr, Compare):
            self.visit_expr(expr.left)
            self.visit_expr(expr.right)
        elif isinstance(expr, Logic):
            self.visit_expr(expr.left)
            self.visit_expr(expr.right)


# 6. CODE GENERATOR


INDENT_UNIT = '    '


class CodeGen:
    def __init__(self):
        self.global_types = {}
        self.var_types = {}
        self.warnings = []
        self.funcs_needing_forward = []

    def pad(self, level):
        return INDENT_UNIT * level

    def _warn(self, msg):
        if msg not in self.warnings:
            self.warnings.append(msg)

    def gen_program(self, prog: Program, directives, funcs_needing_forward):
        self.global_types = {}
        self.var_types = {}
        self.warnings = []
        self.funcs_needing_forward = funcs_needing_forward

        for node in prog.body:
            if isinstance(node, VarDecl):
                self.global_types[node.name] = node.vtype

        lines = []
        seen = set()
        for d in directives:
            if d not in seen:
                lines.append(d)
                seen.add(d)
        if lines:
            lines.append('')

        # Forward declarations for regular functions
        for func_name in self.funcs_needing_forward:
            for node in prog.body:
                if isinstance(node, FuncDef) and node.name == func_name and node.is_regular:
                    params = ', '.join(node.params)
                    lines.append(f"forward {func_name}({params});")
                    break
        if self.funcs_needing_forward:
            lines.append('')

        for node in prog.body:
            lines.append(self.gen_top(node))
            lines.append('')
        return '\n'.join(lines).rstrip() + '\n'

    def _collect_types(self, stmts):
        for s in stmts:
            if isinstance(s, VarDecl):
                self.var_types[s.name] = s.vtype
            elif isinstance(s, If):
                self._collect_types(s.body)
                for _, b in s.elifs:
                    self._collect_types(b)
                if s.else_body:
                    self._collect_types(s.else_body)

    def gen_top(self, node):
        if isinstance(node, VarDecl):
            self.var_types = dict(self.global_types)
            return self.gen_vardecl(node, 0)
        if isinstance(node, FuncDef):
            self.var_types = dict(self.global_types)
            for prm in node.params:
                if prm.endswith('[]'):
                    self.var_types[prm[:-2]] = 'string'
            self._collect_types(node.body)
            return self.gen_funcdef(node)
        raise CompileError(f"Unknown top-level node: {node}")

    def gen_vardecl(self, node: VarDecl, level):
        p = self.pad(level)
        name = node.name

        if node.vtype == 'integer':
            init = f" = {self.gen_expr(node.init)}" if node.init is not None else ''
            return f"{p}new {name}{init};"

        if node.vtype == 'bool':
            init = f" = {self.gen_expr(node.init)}" if node.init is not None else ''
            return f"{p}new bool:{name}{init};"

        if node.vtype == 'float':
            init = f" = {self.gen_float_expr(node.init)}" if node.init is not None else ''
            return f"{p}new Float:{name}{init};"

        if node.vtype == 'string':
            size = node.size
            if isinstance(node.init, CallExpr) and node.init.name in NATIVES \
                    and NATIVES[node.init.name].get('fills_buffer'):
                spec = NATIVES[node.init.name]
                decl_line = f"{p}new {name}[{size}];"
                args = [self.gen_expr(a) for a in node.init.args]
                args.append(name)
                args.append(str(size))
                call_line = f"{p}{spec['pawn']}({', '.join(args)});"
                return decl_line + '\n' + call_line
            if isinstance(node.init, Lit) and node.init.kind == 'string':
                return f'{p}new {name}[{size}] = "{node.init.value}";'
            if node.init is not None:
                decl_line = f"{p}new {name}[{size}];"
                fmt_line = f'{p}format({name}, sizeof({name}), "%s", {self.gen_expr(node.init)});'
                return decl_line + '\n' + fmt_line
            return f"{p}new {name}[{size}];"

        raise CompileError(f"Unknown data type: {node.vtype}")

    def gen_float_expr(self, node):
        if isinstance(node, Lit) and node.kind == 'number':
            return repr(float(node.value))
        return self.gen_expr(node)

    def is_string_expr(self, node):
        if isinstance(node, Lit) and node.kind == 'string':
            return True
        if isinstance(node, Ident) and self.var_types.get(node.name) == 'string':
            return True
        if isinstance(node, CallExpr) and node.name in ('GetName', 'GetIP'):
            return True
        return False

    def gen_expr(self, node):
        if isinstance(node, Lit):
            if node.kind == 'number':
                return str(node.value)
            if node.kind == 'hex':
                return node.value
            if node.kind == 'string':
                return f'"{node.value}"'
            if node.kind == 'bool':
                return 'true' if node.value else 'false'
        if isinstance(node, Ident):
            return node.name
        if isinstance(node, Index):
            return f"{node.name}[{self.gen_expr(node.index)}]"
        if isinstance(node, BinOp):
            return f"({self.gen_expr(node.left)} {node.op} {self.gen_expr(node.right)})"
        if isinstance(node, CallExpr):
            return self.gen_call(node)
        raise CompileError(f"Unknown expression: {node}")

    def gen_call(self, node: CallExpr):
        name = node.name

        if name == 'Send':
            args = node.args
            if len(args) == 2:
                target = self.gen_expr(args[0])
                color = '-1'
                text = self.gen_expr(args[1])
            elif len(args) == 3:
                target = self.gen_expr(args[0])
                color = self.gen_expr(args[1])
                text = self.gen_expr(args[2])
            else:
                raise CompileError("Send requires 2 or 3 arguments: Send(id, [color], text)")
            return f"SendClientMessage({target}, {color}, {text})"

        if name == 'GetParams':
            args = [self.gen_expr(a) for a in node.args]
            return f"sscanf({', '.join(args)})"

        if name in NATIVES:
            spec = NATIVES[name]
            if spec.get('fills_buffer'):
                raise CompileError(
                    f"'{name}' may only be used directly in the form "
                    f"'let varname : string[N] = {name}(...)'; it cannot be used "
                    f"inside other expressions or statements."
                )
            refs = spec.get('refs', [])
            args = []
            for i, a in enumerate(node.args):
                s = self.gen_expr(a)
                if i in refs:
                    s = f"&{s}"
                args.append(s)
            return f"{spec['pawn']}({', '.join(args)})"

        args = [self.gen_expr(a) for a in node.args]
        return f"{name}({', '.join(args)})"

    def gen_compare(self, node: Compare):
        l_is_str = self.is_string_expr(node.left)
        r_is_str = self.is_string_expr(node.right)
        l = self.gen_expr(node.left)
        r = self.gen_expr(node.right)
        if l_is_str or r_is_str:
            if node.op == '==':
                return f"strcmp({l}, {r}, false) == 0"
            if node.op == '!=':
                return f"strcmp({l}, {r}, false) != 0"
            self._warn(
                "operator 'bigger'/'smaller' used on a string value; Pawn has no "
                "string ordering operators, the result likely won't behave as expected."
            )
        return f"{l} {node.op} {r}"

    def gen_cond(self, node):
        if isinstance(node, Compare):
            return self.gen_compare(node)
        if isinstance(node, Logic):
            left = self.gen_cond(node.left)
            right = self.gen_cond(node.right)
            return f"{left} {node.op} {right}"
        return self.gen_expr(node)

    def gen_stmt(self, node, level):
        p = self.pad(level)
        if isinstance(node, VarDecl):
            return self.gen_vardecl(node, level)
        if isinstance(node, Assign):
            if node.index is not None:
                base = f"{node.name}[{self.gen_expr(node.index)}]"
            else:
                base = node.name
            if node.op in ('+=', '-='):
                return f"{p}{base} {node.op} {self.gen_expr(node.expr)};"
            if self.var_types.get(node.name) == 'string' and node.index is None:
                return f'{p}format({node.name}, sizeof({node.name}), "%s", {self.gen_expr(node.expr)});'
            return f"{p}{base} = {self.gen_expr(node.expr)};"
        if isinstance(node, Return):
            if node.expr is None:
                return f"{p}return;"
            return f"{p}return {self.gen_expr(node.expr)};"
        if isinstance(node, ExprStmt):
            return f"{p}{self.gen_call(node.expr)};"
        if isinstance(node, If):
            return self.gen_if(node, level)
        raise CompileError(f"Unknown statement: {node}")

    def gen_if(self, node: If, level):
        p = self.pad(level)
        out = [f"{p}if ({self.gen_cond(node.cond)})", f"{p}{{"]
        out.extend(self.gen_stmt(s, level + 1) for s in node.body)
        out.append(f"{p}}}")
        for econd, ebody in node.elifs:
            out.append(f"{p}else if ({self.gen_cond(econd)})")
            out.append(f"{p}{{")
            out.extend(self.gen_stmt(s, level + 1) for s in ebody)
            out.append(f"{p}}}")
        if node.else_body is not None:
            out.append(f"{p}else")
            out.append(f"{p}{{")
            out.extend(self.gen_stmt(s, level + 1) for s in node.else_body)
            out.append(f"{p}}}")
        return '\n'.join(out)

    def gen_funcdef(self, node: FuncDef, level=0):
        p = self.pad(level)

        if node.is_command:
            if len(node.params) >= 2 and not node.params[1].endswith('[]'):
                self._warn(
                    f"command '{node.name}' has parameter '{node.params[1]}' without [] — "
                    f"command arguments must be declared as a string array, e.g. params[]."
                )
            sig = f"{p}CMD:{node.name}({', '.join(node.params)})"
        elif node.is_regular:
            sig = f"{p}public {node.name}({', '.join(node.params)})"
        elif node.name in CALLBACKS:
            pawn_name = CALLBACKS[node.name]
            expected = CALLBACK_PARAM_COUNT.get(pawn_name)
            got = len(node.params)
            if expected is not None and expected != got:
                self._warn(
                    f"'{node.name}' ({pawn_name}) is normally declared with {expected} parameter(s), "
                    f"but you wrote {got}. Double-check the order and count."
                )
            sig = f"{p}public {pawn_name}({', '.join(node.params)})"
        else:
            raise CompileError(f"Function '{node.name}' is not a known callback and not declared with 'function'.")

        body_lines = [self.gen_stmt(s, level + 1) for s in node.body]
        body = '\n'.join(body_lines) if body_lines else f"{self.pad(level+1)}return 1;"
        return f"{sig}\n{p}{{\n{body}\n{p}}}"


# 7. CLI


HEADER_TEMPLATE = (
   "// Samp Language Compiler v{ver} - generated from {src}\n"
)


def compile_source(source, src_name="?"):
    tokens, directives = tokenize(source)
    parser = Parser(tokens)
    prog = parser.parse_program()

    analyzer = SemanticAnalyzer()
    errors = analyzer.analyze(prog)
    if errors:
        raise CompileError(errors[0])

    gen = CodeGen()
    code = gen.gen_program(prog, directives, analyzer.funcs_needing_forward)
    return HEADER_TEMPLATE.format(src=src_name, ver=VERSION) + code, gen.warnings


def compile_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        source = f.read()
    code, warnings = compile_source(source, os.path.basename(path))
    out_path = os.path.splitext(path)[0] + '.pwn'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(code)
    size = os.path.getsize(out_path)
    return out_path, warnings, size


def main():
    print(f"SAMPL Compiler v{VERSION}")

    if len(sys.argv) != 2:
        print("Usage:")
        print("  python smplc.py file.smpl")
        sys.exit(1)

    target = sys.argv[1]
    if not os.path.isfile(target) or not target.endswith('.smpl'):
        print("[ERROR] Please provide a single .smpl file.")
        sys.exit(1)

    print(f"\n-> Starting compile {target}")

    try:
        out_path, warnings, size = compile_file(target)
        for w in warnings:
            print(f"{target}: warning: {w}")
        print(f"\nFile size: {size} bytes")
        print("[OK] Compilation successful.")
    except (LexError, ParseError, CompileError) as e:
        line = getattr(e, 'line', None)
        if line is not None:
            print(f"{target}({line}): error: {e}")
        else:
            print(f"{target}: error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()