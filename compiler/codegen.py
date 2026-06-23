from config import INDENT_UNIT
from errors import CompileError
from ast_nodes import *
from mappings import CALLBACKS, CALLBACK_PARAM_COUNT
from natives import NATIVES

class CodeGen:
    def __init__(self):
        self.var_types = {}

    def pad(self, lvl):
        return INDENT_UNIT * lvl

    def gen_program(self, prog, includes):
        lines = list(includes)
        for node in prog.body:
            lines.append(self.gen_node(node))
        return "\n".join(lines)

    def gen_node(self, node):
        if isinstance(node, VarDecl):
            return f"new {node.name};"
        if isinstance(node, FuncDef):
            return self.gen_func(node)
        raise CompileError("unknown node")

    def gen_func(self, node):
        name = CALLBACKS.get(node.name, node.name)
        return f"public {name}() {{\n}}"