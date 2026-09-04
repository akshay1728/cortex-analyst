"""AST-Based Code Validator for Dynamic Visualization Security.

Validates LLM-generated Python code using Abstract Syntax Trees (AST) to ensure strict security:
1. Rejects code using forbidden modules (os, sys, subprocess, socket, requests, urllib, etc.).
2. Rejects code calling forbidden builtins (open, eval, exec, compile, __import__, getattr, setattr, delattr, globals, locals).
3. Ensures code only imports approved visualization libraries (plotly, plotly.express, plotly.graph_objects, pandas, numpy).
4. Confirms `fig` is assigned in the AST.
"""

import ast
from typing import Tuple, List

# Approved module allowlist
APPROVED_MODULES = {
    "plotly",
    "plotly.express",
    "plotly.graph_objects",
    "plotly.subplots",
    "pandas",
    "numpy",
    "math"
}

# Strictly forbidden built-in functions & identifiers
FORBIDDEN_BUILTINS = {
    "open", "eval", "exec", "compile", "__import__",
    "getattr", "setattr", "delattr", "globals", "locals",
    "input", "breakpoint", "memoryview"
}

# Forbidden module names
FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "socket", "requests", "urllib", "http",
    "shutil", "importlib", "ctypes", "pathlib", "asyncio", "threading",
    "multiprocessing", "pickle", "codecs"
}

class ASTChartValidator(ast.NodeVisitor):
    def __init__(self):
        self.errors: List[str] = []
        self.assigns_fig: bool = False

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            mod_name = alias.name.split('.')[0]
            if mod_name in FORBIDDEN_MODULES or mod_name not in APPROVED_MODULES:
                self.errors.append(f"Forbidden import: '{alias.name}' is not in the approved allowlist.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            mod_name = node.module.split('.')[0]
            if mod_name in FORBIDDEN_MODULES or mod_name not in APPROVED_MODULES:
                self.errors.append(f"Forbidden import from module: '{node.module}'.")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in FORBIDDEN_BUILTINS:
                self.errors.append(f"Forbidden builtin call: '{func_name}()' is disallowed for security.")
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in FORBIDDEN_BUILTINS:
                self.errors.append(f"Forbidden attribute call: '{attr_name}()' is disallowed.")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr.startswith("__") and node.attr.endswith("__"):
            if node.attr not in ("__name__", "__doc__"):
                self.errors.append(f"Dunder attribute access disallowed: '{node.attr}'.")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if node.id in FORBIDDEN_BUILTINS:
            if isinstance(node.ctx, (ast.Load, ast.Call)):
                self.errors.append(f"Disallowed name access: '{node.id}'.")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "fig":
                self.assigns_fig = True
        self.generic_visit(node)

def validate_python_code(code_str: str) -> Tuple[bool, List[str]]:
    """Statically analyze generated Python code using AST.

    Returns:
        (is_valid: bool, error_messages: List[str])
    """
    if not code_str or not code_str.strip():
        return False, ["Code is empty."]

    try:
        parsed_ast = ast.parse(code_str)
    except SyntaxError as e:
        return False, [f"SyntaxError in generated code: {e}"]

    validator = ASTChartValidator()
    validator.visit(parsed_ast)

    if not validator.assigns_fig:
        validator.errors.append("Generated code does not assign a Plotly Figure to 'fig'.")

    is_valid = len(validator.errors) == 0
    return is_valid, validator.errors
