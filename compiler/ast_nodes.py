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
    def __init__(self, name, expr, index=None):
        self.name = name
        self.expr = expr
        self.index = index


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
    def __init__(self, name, params, body, is_command=False):
        self.name = name
        self.params = params
        self.body = body
        self.is_command = is_command


class CallExpr(Node):
    def __init__(self, name, args):
        self.name = name
        self.args = args


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
    def __init__(self, name):
        self.name = name


class Lit(Node):
    def __init__(self, value, kind):
        self.value = value
        self.kind = kind


class Index(Node):
    def __init__(self, name, index):
        self.name = name
        self.index = index