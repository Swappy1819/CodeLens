"""Python AST analysis for scanned repository files."""

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

from .scanner import PythonFile, scan_repository


@dataclass(frozen=True)
class Symbol:
    """A code entity discovered in a Python source file."""

    name: str
    symbol_type: str
    file_path: Path
    start_line: int
    end_line: Optional[int]
    parent_name: Optional[str] = None
    module: Optional[str] = None


@dataclass(frozen=True)
class CallSite:
    """A statically observed call expression inside a function or method."""

    caller_type: str
    caller_name: str
    caller_file_path: Path
    caller_start_line: int
    caller_parent_class: Optional[str]
    callee_name: str
    callee_qualifier: Optional[str]
    start_line: int
    start_column: int


@dataclass
class FileAnalysis:
    """Symbols and an optional syntax error for one Python source file."""

    file_path: Path
    symbols: List[Symbol]
    syntax_error: Optional[str] = None
    calls: List[CallSite] = field(default_factory=list)


def analyze_repository(repository: Union[Path, str]) -> List[FileAnalysis]:
    """Scan and analyze every Python file in *repository*."""
    repository_path = Path(repository).resolve()
    return [
        analyze_python_file(python_file, repository_path)
        for python_file in scan_repository(repository_path)
    ]


def analyze_python_file(python_file: PythonFile, repository: Union[Path, str]) -> FileAnalysis:
    """Analyze one file returned by :func:`scan_repository`."""
    source_path = Path(repository).resolve() / python_file.path

    try:
        tree = ast.parse(source_path.read_text(), filename=str(source_path))
    except SyntaxError as error:
        return FileAnalysis(
            file_path=python_file.path,
            symbols=[],
            syntax_error=str(error),
        )

    collector = _SymbolCollector(python_file.path)
    collector.visit(tree)
    return FileAnalysis(
        file_path=python_file.path,
        symbols=collector.symbols,
        calls=collector.calls,
    )


class _SymbolCollector(ast.NodeVisitor):
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.symbols: List[Symbol] = []
        self.calls: List[CallSite] = []
        self.class_stack: List[str] = []
        self.function_stack: List[Symbol] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add_symbol(node.name, "class", node)
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        symbol_type = "method" if self.class_stack else "function"
        symbol = self._add_symbol(node.name, symbol_type, node)
        self.function_stack.append(symbol)
        for statement in node.body:
            self.visit(statement)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_Import(self, node: ast.Import) -> None:
        for imported in node.names:
            self._add_symbol(
                imported.asname or imported.name,
                "import",
                node,
                module=imported.name,
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        for imported in node.names:
            self._add_symbol(
                imported.asname or imported.name,
                "from_import",
                node,
                module=module,
            )

    def visit_Call(self, node: ast.Call) -> None:
        if self.function_stack:
            callee_name, callee_qualifier = self._call_target(node)
            if callee_name is not None:
                caller = self.function_stack[-1]
                self.calls.append(
                    CallSite(
                        caller_type=caller.symbol_type,
                        caller_name=caller.name,
                        caller_file_path=caller.file_path,
                        caller_start_line=caller.start_line,
                        caller_parent_class=caller.parent_name,
                        callee_name=callee_name,
                        callee_qualifier=callee_qualifier,
                        start_line=node.lineno,
                        start_column=node.col_offset,
                    )
                )
        self.generic_visit(node)

    @staticmethod
    def _call_target(node: ast.Call) -> tuple:
        if isinstance(node.func, ast.Name):
            return node.func.id, None
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            return node.func.attr, node.func.value.id
        return None, None

    def _add_symbol(
        self,
        name: str,
        symbol_type: str,
        node: ast.AST,
        module: Optional[str] = None,
    ) -> Symbol:
        symbol = Symbol(
            name=name,
            symbol_type=symbol_type,
            file_path=self.file_path,
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", None),
            parent_name=self.class_stack[-1] if self.class_stack else None,
            module=module,
        )
        self.symbols.append(symbol)
        return symbol
