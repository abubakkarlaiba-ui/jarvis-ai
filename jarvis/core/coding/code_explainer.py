"""
Code Explainer — explain code in natural language.
===================================================
Uses AST parsing for Python, regex patterns for other languages.
"""

from __future__ import annotations

import ast
import re
import textwrap
from typing import Any, Optional

from jarvis.core.coding.base import (
    CodeLanguage,
    CodingResult,
    TaskType,
)


# ---------------------------------------------------------------------------
# Keyword / pattern dictionaries for non-Python languages
# ---------------------------------------------------------------------------

_KEYWORD_DOCS: dict[str, dict[str, str]] = {
    "javascript": {
        "function": "Declares a function that can be called with arguments.",
        "const": "Declares a read-only variable (constant) that cannot be reassigned.",
        "let": "Declares a block-scoped variable that can be reassigned.",
        "var": "Declares a function-scoped or globally-scoped variable.",
        "return": "Returns a value from the current function.",
        "if": "Conditional branch — executes the block if the condition is truthy.",
        "else": "Fallback branch executed when the preceding `if` condition is false.",
        "for": "Loop that repeats a block for a fixed number of iterations.",
        "while": "Loop that repeats as long as the condition remains true.",
        "class": "Defines a class (blueprint) for creating objects with shared behavior.",
        "import": "Imports a module so its exports can be used in the current file.",
        "export": "Makes a function, variable, or class available to other modules.",
        "try": "Begins an error-handling block that catches runtime exceptions.",
        "catch": "Handles the exception thrown inside the preceding `try` block.",
        "async": "Marks a function as asynchronous (returns a Promise).",
        "await": "Pauses execution until the given Promise resolves.",
        "new": "Creates a new instance of a class or object.",
        "this": "Refers to the current object context inside a method.",
        "switch": "Multi-branch conditional that matches a value against several cases.",
        "case": "A single branch inside a `switch` statement.",
        "default": "Fallback branch inside a `switch` statement.",
        "break": "Exits the nearest enclosing loop or `switch`.",
        "continue": "Skips to the next iteration of the enclosing loop.",
    },
    "typescript": {},  # inherits JS keywords
    "java": {
        "public": "Accessible from any class.",
        "private": "Accessible only within the declaring class.",
        "protected": "Accessible within the class and its subclasses.",
        "static": "Belongs to the class itself rather than an instance.",
        "final": "Cannot be overridden or reassigned.",
        "void": "The function returns no value.",
        "int": "Integer numeric type.",
        "double": "Double-precision floating-point type.",
        "String": "Sequence of characters.",
        "class": "Defines a class (blueprint) for creating objects.",
        "interface": "Defines a contract that classes or objects must implement.",
        "extends": "Class inherits from a parent class.",
        "implements": "Class adheres to an interface contract.",
        "return": "Returns a value from the current method.",
        "if": "Conditional branch.",
        "else": "Fallback branch.",
        "for": "Loop.",
        "while": "Loop.",
        "try": "Begins error handling.",
        "catch": "Handles exceptions.",
        "throws": "Declares that a method may throw exceptions.",
        "new": "Creates a new object instance.",
        "this": "Refers to the current instance.",
        "switch": "Multi-branch conditional.",
        "case": "A branch in a `switch`.",
        "break": "Exits a loop or `switch`.",
        "continue": "Skips to next loop iteration.",
        "abstract": "Declares an abstract class or method (no implementation).",
        "enum": "Defines a set of named constants.",
    },
    "go": {
        "func": "Declares a function or method.",
        "var": "Declares a variable with optional type and initialization.",
        "const": "Declares a compile-time constant.",
        "if": "Conditional branch.",
        "else": "Fallback branch.",
        "for": "The only loop construct in Go (used for while-style loops too).",
        "switch": "Multi-branch conditional.",
        "case": "A branch in a `switch`.",
        "default": "Fallback branch in a `switch`.",
        "return": "Returns values from a function.",
        "break": "Exits the nearest loop or `switch`.",
        "continue": "Skips to the next loop iteration.",
        "go": "Launches a goroutine (lightweight concurrent function).",
        "chan": "Declares a channel for goroutine communication.",
        "select": "Blocks on multiple channel operations.",
        "defer": "Schedules a function call to run when the surrounding function returns.",
        "package": "Declares the package this file belongs to.",
        "import": "Imports another package.",
        "type": "Defines a new named type.",
        "struct": "Defines a composite type with named fields.",
        "interface": "Defines a set of methods that a type must satisfy.",
        "map": "Declares a key-value map type.",
        "range": "Iterates over elements of a slice, array, string, map, or channel.",
    },
    "rust": {
        "fn": "Declares a function.",
        "let": "Declares a local variable.",
        "mut": "Makes a variable mutable (assignable).",
        "pub": "Makes an item publicly accessible.",
        "struct": "Defines a composite data type with named fields.",
        "enum": "Defines a type by enumerating its possible variants.",
        "impl": "Implements methods for a struct or enum.",
        "trait": "Defines shared behavior (like an interface).",
        "use": "Brings items into scope.",
        "mod": "Declares a module.",
        "return": "Returns a value from a function.",
        "if": "Conditional branch.",
        "else": "Fallback branch.",
        "for": "Loop.",
        "while": "Loop.",
        "loop": "Infinite loop (must be exited with `break`).",
        "match": "Pattern-matching expression (like a powerful `switch`).",
        "async": "Declares an asynchronous function.",
        "await": "Waits for an async future to complete.",
        "self": "Refers to the current struct instance in a method.",
        "Self": "Refers to the implementing type in an `impl` block.",
        "where": "Adds type constraints on generics.",
        "move": "Captures variables by value in closures.",
        "unsafe": "Enables use of unsafe features (raw pointers, FFI, etc.).",
        "type": "Defines a type alias.",
        "const": "Declares a compile-time constant.",
        "static": "Declares a global variable with a fixed memory address.",
        "extern": "Declares an external (FFI) function or ABI.",
        "break": "Exits a loop.",
        "continue": "Skips to the next loop iteration.",
        "ref": "Creates a reference to a value.",
        "crate": "Refers to the current crate root.",
        "super": "Refers to the parent module.",
    },
    "cpp": {
        "int": "Integer numeric type.",
        "double": "Double-precision floating-point type.",
        "float": "Single-precision floating-point type.",
        "char": "Single character type.",
        "bool": "Boolean type (true/false).",
        "void": "Indicates no return value.",
        "auto": "Lets the compiler deduce the type.",
        "class": "Defines a class.",
        "struct": "Defines a struct (default-public members).",
        "enum": "Defines an enumeration type.",
        "namespace": "Groups declarations to avoid name collisions.",
        "return": "Returns a value from a function.",
        "if": "Conditional branch.",
        "else": "Fallback branch.",
        "for": "Loop.",
        "while": "Loop.",
        "do": "Loop that executes at least once before checking the condition.",
        "switch": "Multi-branch conditional.",
        "case": "A branch in a `switch`.",
        "break": "Exits a loop or `switch`.",
        "continue": "Skips to the next loop iteration.",
        "try": "Begins error handling.",
        "catch": "Handles an exception.",
        "throw": "Throws an exception.",
        "new": "Dynamically allocates memory.",
        "delete": "Frees dynamically allocated memory.",
        "template": "Defines a generic (parameterized) class or function.",
        "typename": "Indicates a type parameter in a template.",
        "virtual": "Declares a method that can be overridden in derived classes.",
        "override": "Indicates a method overrides a virtual base method.",
        "const": "Declares an entity as read-only.",
        "static": "Declares an entity shared across all instances.",
        "public": "Accessible from anywhere.",
        "private": "Accessible only within the class.",
        "protected": "Accessible within the class and derived classes.",
        "include": "Includes a header file.",
        "using": "Imports a namespace or creates a type alias.",
        "nullptr": "Null pointer literal.",
        "true": "Boolean true literal.",
        "false": "Boolean false literal.",
    },
    "c": {
        "int": "Integer type.",
        "double": "Double-precision float.",
        "float": "Single-precision float.",
        "char": "Character type.",
        "void": "No value.",
        "struct": "Composite type with named fields.",
        "enum": "Enumeration type.",
        "typedef": "Creates a new type name.",
        "return": "Returns from a function.",
        "if": "Conditional.",
        "else": "Fallback branch.",
        "for": "Loop.",
        "while": "Loop.",
        "do": "Do-while loop.",
        "switch": "Multi-branch conditional.",
        "case": "Branch in a switch.",
        "break": "Exits loop or switch.",
        "continue": "Next loop iteration.",
        "sizeof": "Returns the size in bytes of a type or expression.",
        "static": "Internal linkage or persistent local variable.",
        "extern": "Declares a variable defined elsewhere.",
        "const": "Read-only qualifier.",
        "volatile": "Prevents compiler optimizations on a variable.",
        "register": "Hint to store a variable in a register.",
        "auto": "Automatic storage duration (default for locals).",
        "malloc": "Allocates heap memory.",
        "free": "Releases heap memory.",
        "include": "Includes a header.",
        "define": "Preprocessor macro definition.",
        "ifdef": "Conditional compilation: if defined.",
        "ifndef": "Conditional compilation: if not defined.",
        "endif": "Ends a preprocessor conditional block.",
        "NULL": "Null pointer constant.",
    },
    "csharp": {
        "class": "Defines a class.",
        "struct": "Defines a value type.",
        "enum": "Defines an enumeration.",
        "interface": "Defines a contract.",
        "namespace": "Groups related declarations.",
        "public": "Accessible everywhere.",
        "private": "Accessible within the class.",
        "protected": "Accessible within the class and subclasses.",
        "internal": "Accessible within the same assembly.",
        "static": "Belongs to the type, not an instance.",
        "abstract": "Cannot be instantiated directly.",
        "virtual": "Can be overridden in derived classes.",
        "override": "Overrides a virtual method.",
        "void": "No return value.",
        "int": "Integer type.",
        "string": "Text type.",
        "bool": "Boolean type.",
        "return": "Returns a value.",
        "if": "Conditional.",
        "else": "Fallback.",
        "for": "Loop.",
        "foreach": "Iterates over a collection.",
        "while": "Loop.",
        "switch": "Multi-branch.",
        "case": "Branch in switch.",
        "break": "Exits loop or switch.",
        "continue": "Next iteration.",
        "try": "Error handling.",
        "catch": "Handles exception.",
        "finally": "Always executes after try/catch.",
        "throw": "Throws an exception.",
        "new": "Creates an instance or hides a base member.",
        "this": "Current instance reference.",
        "base": "Base class reference.",
        "async": "Asynchronous method.",
        "await": "Waits for async operation.",
        "var": "Implicitly typed variable.",
        "readonly": "Can only be assigned in constructor.",
        "const": "Compile-time constant.",
        "using": "Imports a namespace or disposes resources.",
        "yield": "Returns an enumerator element lazily.",
    },
    "ruby": {
        "def": "Defines a method.",
        "end": "Marks the end of a block.",
        "class": "Defines a class.",
        "module": "Defines a module (namespace).",
        "if": "Conditional.",
        "elsif": "Additional condition in an if-chain.",
        "else": "Fallback.",
        "unless": "Inverse of if.",
        "while": "Loop.",
        "until": "Loop that runs while condition is false.",
        "for": "Loop over a range or collection.",
        "do": "Starts a block.",
        "yield": "Passes control to the block given to a method.",
        "return": "Returns a value.",
        "puts": "Prints a line to stdout.",
        "require": "Loads another file.",
        "attr_reader": "Defines getter methods.",
        "attr_writer": "Defines setter methods.",
        "attr_accessor": "Defines getter and setter methods.",
        "self": "Current object reference.",
        "nil": "Absence of a value.",
        "true": "Boolean true.",
        "false": "Boolean false.",
        "begin": "Starts an exception-handling block.",
        "rescue": "Catches an exception.",
        "ensure": "Always executes after begin/rescue.",
        "raise": "Throws an exception.",
        "lambda": "Creates a lambda (anonymous function).",
        "proc": "Creates a Proc object.",
    },
    "php": {
        "function": "Declares a function.",
        "class": "Defines a class.",
        "interface": "Defines a contract.",
        "trait": "Defines reusable behavior (like mixins).",
        "namespace": "Groups related code.",
        "public": "Accessible everywhere.",
        "private": "Accessible within the class.",
        "protected": "Accessible within the class and subclasses.",
        "static": "Belongs to the class, not an instance.",
        "abstract": "Cannot be instantiated directly.",
        "final": "Cannot be overridden or extended.",
        "return": "Returns a value.",
        "if": "Conditional.",
        "elseif": "Additional condition.",
        "else": "Fallback.",
        "for": "Loop.",
        "foreach": "Iterates over a collection.",
        "while": "Loop.",
        "switch": "Multi-branch.",
        "case": "Branch in switch.",
        "break": "Exits loop or switch.",
        "continue": "Next iteration.",
        "try": "Error handling.",
        "catch": "Catches exceptions.",
        "throw": "Throws an exception.",
        "echo": "Outputs a string.",
        "new": "Creates an object instance.",
        "array": "Creates an array.",
        "null": "Null value.",
        "true": "Boolean true.",
        "false": "Boolean false.",
        "var": "Declares a variable (older style).",
        "const": "Declares a constant.",
        "define": "Defines a named constant.",
        "include": "Includes and evaluates a file.",
        "require": "Includes a file (fatal on failure).",
    },
    "swift": {
        "func": "Declares a function.",
        "class": "Defines a class.",
        "struct": "Defines a value type.",
        "enum": "Defines an enumeration.",
        "protocol": "Defines a contract (like an interface).",
        "extension": "Adds functionality to an existing type.",
        "let": "Declares a constant.",
        "var": "Declares a variable.",
        "return": "Returns a value.",
        "if": "Conditional.",
        "else": "Fallback.",
        "for": "Loop.",
        "while": "Loop.",
        "switch": "Pattern-matching conditional.",
        "case": "Branch in a switch.",
        "break": "Exits a loop or switch.",
        "continue": "Next iteration.",
        "guard": "Exits early if a condition is false.",
        "do": "Begins a scope for error handling.",
        "catch": "Catches errors.",
        "throw": "Throws an error.",
        "try": "Marks a throwing call.",
        "self": "Current instance reference.",
        "super": "Base class reference.",
        "init": "Initializer (constructor).",
        "deinit": "Deinitializer (destructor).",
        "mutating": "Allows modification of struct properties.",
        "static": "Type-level member.",
        "public": "Accessible everywhere.",
        "private": "Accessible within the declaration.",
        "internal": "Accessible within the module (default).",
        "nil": "Absence of a value.",
        "true": "Boolean true.",
        "false": "Boolean false.",
        "import": "Imports a module.",
        "print": "Outputs to stdout.",
        "var": "Declares a mutable variable.",
        "some": "Opaque return type.",
        "any": "Existential type.",
        "async": "Asynchronous function.",
        "await": "Waits for async work.",
    },
    "kotlin": {
        "fun": "Declares a function.",
        "class": "Defines a class.",
        "object": "Declares a singleton object.",
        "interface": "Defines a contract.",
        "data": "Modifier for classes that auto-generate equals/hashCode/toString.",
        "sealed": "Restricted class hierarchy.",
        "enum": "Enumeration.",
        "val": "Declares an immutable variable.",
        "var": "Declares a mutable variable.",
        "return": "Returns a value.",
        "if": "Conditional (also an expression).",
        "else": "Fallback.",
        "when": "Multi-branch (like switch, but more powerful).",
        "for": "Loop.",
        "while": "Loop.",
        "do": "Do-while loop.",
        "break": "Exits a loop.",
        "continue": "Next iteration.",
        "try": "Error handling.",
        "catch": "Catches exceptions.",
        "finally": "Always executes.",
        "throw": "Throws an exception.",
        "is": "Type check.",
        "as": "Type cast.",
        "in": "Iteration or range check.",
        "by": "Delegates a property or implements an interface.",
        "companion": "Companion object (static members).",
        "suspend": "Marks a coroutine function.",
        "launch": "Starts a coroutine.",
        "async": "Starts an async coroutine.",
        "await": "Suspends until coroutine completes.",
        "this": "Current instance.",
        "super": "Base class.",
        "init": "Initializer block.",
        "null": "Null literal.",
        "true": "Boolean true.",
        "false": "Boolean false.",
        "import": "Imports a package.",
        "package": "Declares a package.",
        "typealias": "Creates a type alias.",
        "open": "Allows inheritance.",
        "abstract": "Abstract class or method.",
        "override": "Overrides a base member.",
        "private": "Accessible within the file/class.",
        "protected": "Accessible in subclasses.",
        "internal": "Accessible within the module.",
        "public": "Accessible everywhere.",
    },
}
# Fill in TypeScript from JavaScript
_KEYWORD_DOCS["typescript"] = {**_KEYWORD_DOCS["javascript"], **{
    "type": "Declares a type alias.",
    "interface": "Declares an interface (contract for object shapes).",
    "enum": "Defines a set of named constants.",
    "any": "Opt-out of type checking.",
    "unknown": "Type-safe alternative to `any`.",
    "never": "Type that never occurs.",
    "readonly": "Makes object properties immutable.",
    "keyof": "Constructs a union of an object's keys.",
    "as": "Type assertion.",
    "is": "Type guard that narrows a type.",
    "namespace": "Groups related declarations.",
    "declare": "Declares ambient types (e.g., from .d.ts).",
    "module": "Module declaration.",
    "abstract": "Declares abstract class or method.",
    "implements": "Class implements an interface.",
    "extends": "Inherits from a class or interface.",
    "string": "String type.",
    "number": "Number type.",
    "boolean": "Boolean type.",
    "void": "Absence of a value.",
    "null": "Null literal.",
    "undefined": "Undefined literal.",
    "Array": "Generic array type.",
    "Promise": "Asynchronous result type.",
    "Partial": "Makes all properties optional.",
    "Required": "Makes all properties required.",
    "Pick": "Creates a type with a subset of properties.",
    "Omit": "Creates a type excluding certain properties.",
    "Record": "Object type with fixed keys.",
    "infer": "Infers a type within a conditional type.",
    "Exclude": "Removes types from a union.",
    "Extract": "Extracts types from a union.",
    "NonNullable": "Removes null and undefined.",
    "ReturnType": "Extracts function return type.",
    "Parameters": "Extracts function parameter types.",
}}

# Simple regex patterns for structure detection in non-Python languages
_FUNC_PATTERNS: dict[CodeLanguage, re.Pattern[str]] = {
    CodeLanguage.JAVASCRIPT: re.compile(
        r"(?:(?:export\s+)?(?:async\s+)?function\s+(\w+)"
        r"|(?:(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>)"
        r"|(?:(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function)"
    ),
    CodeLanguage.TYPESCRIPT: re.compile(
        r"(?:(?:export\s+)?(?:async\s+)?function\s+(\w+)"
        r"|(?:(?:export\s+)?(?:async\s+)?function\s+\w+\s*<[^>]*>\s*\([^)]*\))"
        r"|(?:(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*:.*=>)"
        r"|(?:(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function)"
    ),
    CodeLanguage.JAVA: re.compile(
        r"(?:(?:public|private|protected)?\s*(?:static\s+)?(?:[\w<>\[\]]+)\s+(\w+)\s*\([^)]*\))"
    ),
    CodeLanguage.GO: re.compile(
        r"func\s+(?:\([^)]+\)\s+)?(\w+)\s*\([^)]*\)(?:\s*[\w,\s*]+)?(?:\s*error)?"
    ),
    CodeLanguage.RUST: re.compile(
        r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*(?:<[^>]*>)?\s*\([^)]*\)(?:\s*->\s*[^{]+)?"
    ),
    CodeLanguage.CPP: re.compile(
        r"(?:(?:[\w:*&<>]+)\s+(\w+)\s*\([^)]*\)(?:\s*(?:const|override|noexcept|\{|;)))"
    ),
    CodeLanguage.C: re.compile(
        r"(?:[\w*\s]+)\s+(\w+)\s*\([^)]*\)\s*\{"
    ),
    CodeLanguage.CSHARP: re.compile(
        r"(?:(?:public|private|protected|internal|static|async|virtual|override|abstract)\s+)*[\w<>\[\]]+\s+(\w+)\s*\([^)]*\)"
    ),
    CodeLanguage.RUBY: re.compile(
        r"def\s+(\w+(?:\?|!|=)?)"
    ),
    CodeLanguage.PHP: re.compile(
        r"(?:(?:public|private|protected|static)\s+)?function\s+(\w+)\s*\([^)]*\)"
    ),
    CodeLanguage.SWIFT: re.compile(
        r"(?:(?:public|private|internal|open|static|mutating|override)\s+)?func\s+(\w+)(?:<[^>]*>)?\s*\([^)]*\)(?:\s*->\s*[^{]+)?"
    ),
    CodeLanguage.KOTLIN: re.compile(
        r"(?:(?:public|private|protected|internal|open|override|suspend|inline|operator)\s+)?fun\s+(\w+)(?:<[^>]*>)?\s*\([^)]*\)(?:\s*:\s*[^{]+)?"
    ),
}

_CLASS_PATTERNS: dict[CodeLanguage, re.Pattern[str]] = {
    CodeLanguage.JAVASCRIPT: re.compile(r"class\s+(\w+)"),
    CodeLanguage.TYPESCRIPT: re.compile(r"(?:export\s+)?(?:abstract\s+)?class\s+(\w+)"),
    CodeLanguage.JAVA: re.compile(r"(?:public|private|protected)?\s*(?:abstract\s+)?class\s+(\w+)"),
    CodeLanguage.GO: re.compile(r"type\s+(\w+)\s+struct"),
    CodeLanguage.RUST: re.compile(r"(?:pub\s+)?struct\s+(\w+)"),
    CodeLanguage.CPP: re.compile(r"class\s+(\w+)"),
    CodeLanguage.CSHARP: re.compile(r"(?:public|internal)?\s*(?:partial\s+)?class\s+(\w+)"),
    CodeLanguage.RUBY: re.compile(r"class\s+(\w+)"),
    CodeLanguage.PHP: re.compile(r"(?:abstract\s+)?class\s+(\w+)"),
    CodeLanguage.SWIFT: re.compile(r"(?:public|open|internal)?\s*(?:final\s+)?class\s+(\w+)"),
    CodeLanguage.KOTLIN: re.compile(r"(?:data\s+)?(?:open\s+|abstract\s+|sealed\s+)?class\s+(\w+)"),
}


# ---------------------------------------------------------------------------
# AST helpers for Python
# ---------------------------------------------------------------------------

def _py_explain_node(node: ast.AST) -> str:
    """Produce a short human-readable explanation of a single AST node."""
    if isinstance(node, ast.Module):
        return "A Python module containing top-level code."
    if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncDef):
        kind = "async function" if isinstance(node, ast.AsyncDef) else "function"
        args = ", ".join(a.arg for a in node.args.args)
        return f"Defines a {kind} named `{node.name}` with parameters ({args})."
    if isinstance(node, ast.ClassDef):
        bases = ", ".join(b.id if isinstance(b, ast.Name) else ast.dump(b) for b in node.bases)
        return f"Defines a class `{node.name}`{f' inheriting from ({bases})' if bases else ''}."
    if isinstance(node, ast.Return):
        return "Returns a value from the function."
    if isinstance(node, ast.Assign):
        targets = ", ".join(ast.dump(t) for t in node.targets)
        return f"Assigns a value to `{targets}`."
    if isinstance(node, ast.If):
        return "Conditional branch based on a boolean expression."
    if isinstance(node, ast.For):
        return "For-loop iterating over a sequence."
    if isinstance(node, ast.While):
        return "While-loop repeating while a condition is true."
    if isinstance(node, ast.Try):
        return "Try block for exception handling."
    if isinstance(node, ast.ExceptHandler):
        return f"Catches exceptions{f' of type {node.name}' if node.name else ''}."
    if isinstance(node, ast.Import):
        names = ", ".join(a.name for a in node.names)
        return f"Imports module(s): {names}."
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        names = ", ".join(a.name for a in node.names)
        return f"Imports {names} from `{module}`."
    if isinstance(node, ast.With):
        return "Context manager block (auto-cleanup)."
    if isinstance(node, ast.Raise):
        return "Raises an exception."
    if isinstance(node, ast.Assert):
        return "Assertion — validates a condition for debugging."
    if isinstance(node, ast.Delete):
        return "Deletes a variable."
    if isinstance(node, ast.Global):
        return f"Declares global variable(s): {', '.join(node.names)}."
    if isinstance(node, ast.Nonlocal):
        return f"Refers to enclosing scope variable(s): {', '.join(node.names)}."
    if isinstance(node, ast.Lambda):
        return "Defines an anonymous (lambda) function."
    if isinstance(node, ast.ListComp):
        return "List comprehension — builds a list from an expression."
    if isinstance(node, ast.DictComp):
        return "Dictionary comprehension — builds a dict from an expression."
    if isinstance(node, ast.SetComp):
        return "Set comprehension — builds a set from an expression."
    if isinstance(node, ast.GeneratorExp):
        return "Generator expression — lazy iterator."
    if isinstance(node, ast.Yield):
        return "Yields a value (generator)."
    if isinstance(node, ast.YieldFrom):
        return "Yields values from a sub-generator."
    if isinstance(node, ast.Await):
        return "Awaits an asynchronous result."
    if isinstance(node, ast.AugAssign):
        return f"Augmented assignment ({type(node.op).__name__})."
    if isinstance(node, ast.AnnAssign):
        return "Annotated variable assignment."
    if isinstance(node, ast.Pass):
        return "No-op placeholder."
    if isinstance(node, ast.Break):
        return "Breaks out of the nearest loop."
    if isinstance(node, ast.Continue):
        return "Skips to the next loop iteration."
    if isinstance(node, ast.BoolOp):
        op = "and" if isinstance(node.op, ast.And) else "or"
        return f"Boolean `{op}` expression."
    if isinstance(node, ast.BinOp):
        op = type(node.op).__name__
        return f"Binary operation ({op})."
    if isinstance(node, ast.UnaryOp):
        op = type(node.op).__name__
        return f"Unary operation ({op})."
    if isinstance(node, ast.Compare):
        return "Comparison expression."
    if isinstance(node, ast.Call):
        return "Function/method call."
    if isinstance(node, ast.Constant):
        return f"Literal constant: {node.value!r}."
    if isinstance(node, ast.Name):
        return f"References variable `{node.id}`."
    if isinstance(node, ast.Attribute):
        return f"Accesses attribute `{node.attr}`."
    if isinstance(node, ast.Subscript):
        return "Subscript / index access."
    if isinstance(node, ast.Slice):
        return "Slice expression."
    if isinstance(node, ast.Starred):
        return "Star unpacking."
    if isinstance(node, ast.FormattedValue):
        return "f-string interpolated value."
    if isinstance(node, ast.JoinedStr):
        return "f-string (formatted string)."
    if isinstance(node, ast.NameConstant):
        return f"Boolean literal: {node.value}."
    if isinstance(node, ast.Num):
        return f"Numeric literal: {node.n}."
    if isinstance(node, ast.Str):
        return f"String literal: {node.s!r}."
    if isinstance(node, ast.Bytes):
        return f"Bytes literal."
    if isinstance(node, ast.List):
        return "List literal."
    if isinstance(node, ast.Tuple):
        return "Tuple literal."
    if isinstance(node, ast.Set):
        return "Set literal."
    if isinstance(node, ast.Dict):
        return "Dictionary literal."
    if isinstance(node, ast.Ellipsis):
        return "Ellipsis literal."
    return f"AST node: {type(node).__name__}."


def _py_walk_with_lines(tree: ast.Module, source: str) -> list[tuple[int, str]]:
    """Walk the AST and return (line_number, explanation) pairs."""
    lines = source.splitlines()
    results: list[tuple[int, str]] = []
    for node in ast.iter_child_nodes(tree):
        line = getattr(node, "lineno", 1)
        results.append((line, _py_explain_node(node)))
    return results


def _py_explain_function(source: str) -> str:
    """Extract and explain functions from Python source."""
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return "Unable to parse source — check for syntax errors."

    parts: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncDef)):
            kind = "async function" if isinstance(node, ast.AsyncDef) else "function"
            args = ", ".join(a.arg for a in node.args.args)
            parts.append(f"{kind} `{node.name}({args})`:")
            # Docstring
            ds = ast.get_docstring(node)
            if ds:
                parts.append(f"  Docstring: {ds.strip()}")
            # Body summary
            body_items = [_py_explain_node(n) for n in node.body if not isinstance(n, (ast.Expr,))]
            for b in body_items[:5]:
                parts.append(f"  - {b}")
    return "\n".join(parts) if parts else "No functions found."


def _py_explain_class(source: str) -> str:
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return "Unable to parse source — check for syntax errors."

    parts: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(b.id if isinstance(b, ast.Name) else ast.dump(b) for b in node.bases)
            parts.append(f"class `{node.name}`{f'({bases})' if bases else ''}:")
            ds = ast.get_docstring(node)
            if ds:
                parts.append(f"  Docstring: {ds.strip()}")
            methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncDef))]
            parts.append(f"  Methods: {len(methods)}")
            for m in methods:
                mkind = "async " if isinstance(m, ast.AsyncDef) else ""
                margs = ", ".join(a.arg for a in m.args.args)
                parts.append(f"    - {mkind}{m.name}({margs})")
            attrs = [n for n in node.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)]
            if attrs:
                parts.append(f"  Attributes: {len(attrs)}")
                for a in attrs:
                    parts.append(f"    - {a.target.id}")
    return "\n".join(parts) if parts else "No classes found."


def _py_explain_imports(source: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return [{"line": 0, "statement": "", "explanation": "Syntax error — unable to parse."}]

    results: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name
                results.append({
                    "line": node.lineno,
                    "statement": f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""),
                    "explanation": f"Imports the `{alias.name}` module (available as `{name}`).",
                })
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = ", ".join(alias.name for alias in node.names)
            results.append({
                "line": node.lineno,
                "statement": f"from {module} import {names}",
                "explanation": f"Imports `{names}` from the `{module}` module.",
            })
    return results


def _py_complexity(source: str) -> dict[str, Any]:
    """Cyclomatic complexity for Python using AST."""
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return {"error": "Syntax error — unable to parse.", "functions": {}}

    results: dict[str, Any] = {"functions": {}, "overall": 1}

    def _count_branches(node: ast.AST) -> int:
        count = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                count += 1
            elif isinstance(child, ast.BoolOp):
                count += len(child.values) - 1
            elif isinstance(child, ast.Assert):
                count += 1
            elif isinstance(child, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                count += 1
            elif isinstance(child, ast.Lambda):
                count += 1
            elif isinstance(child, ast.BoolOp):
                count += len(child.values) - 1
        return count

    total = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncDef)):
            cc = 1 + _count_branches(node)
            results["functions"][node.name] = cc
            total += cc - 1
    results["overall"] = total
    return results


# ---------------------------------------------------------------------------
# Regex-based explainers for non-Python
# ---------------------------------------------------------------------------

def _regex_explain(code: str, lang: CodeLanguage) -> str:
    """Use regex to extract structural elements and explain them."""
    keywords = _KEYWORD_DOCS.get(lang.value, {})
    tokens = _extract_tokens(code)
    explained: dict[str, str] = {}
    for tok in tokens:
        if tok in keywords and tok not in explained:
            explained[tok] = keywords[tok]

    sections: list[str] = []
    # Functions
    pat = _FUNC_PATTERNS.get(lang)
    if pat:
        for m in pat.finditer(code):
            fname = m.group(1) or m.group(2) or m.group(3) if m.lastindex else m.group(0)
            if fname:
                sections.append(f"Function `{fname}` — defined in source.")
    # Classes
    cpat = _CLASS_PATTERNS.get(lang)
    if cpat:
        for m in cpat.finditer(code):
            sections.append(f"Class/struct `{m.group(1)}` — defined in source.")
    # Keywords found
    if explained:
        sections.append("")
        sections.append("Keywords used:")
        for k, v in sorted(explained.items()):
            sections.append(f"  `{k}` — {v}")

    return "\n".join(sections) if sections else "No structural elements detected."


def _extract_tokens(code: str) -> set[str]:
    """Extract identifiers and keywords from code."""
    tokens = set(re.findall(r"[a-zA-Z_]\w*", code))
    # Also pull known keywords from all language docs
    all_kw: set[str] = set()
    for kw_dict in _KEYWORD_DOCS.values():
        all_kw.update(kw_dict.keys())
    return tokens & all_kw


def _regex_explain_function(code: str, lang: CodeLanguage) -> str:
    """Extract and explain functions for non-Python languages."""
    pat = _FUNC_PATTERNS.get(lang)
    if not pat:
        return f"Function detection not supported for {lang.value}."
    matches = list(pat.finditer(code))
    if not matches:
        return "No functions detected."
    parts: list[str] = []
    for m in matches:
        idx = m.lastindex or 0
        fname = m.group(idx) if idx and idx <= len(m.groups()) else m.group(0)
        parts.append(f"Function `{fname}`:")
        parts.append(f"  Detected at position {m.start()}.")
        # Try to extract the body (everything from { to matching })
        start = m.end()
        brace_pos = code.find("{", start)
        if brace_pos != -1:
            depth = 0
            end = brace_pos
            for i in range(brace_pos, len(code)):
                if code[i] == "{":
                    depth += 1
                elif code[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            body = code[brace_pos + 1:end - 1].strip()
            # Extract keywords from body
            body_tokens = _extract_tokens(body)
            kw_dict = _KEYWORD_DOCS.get(lang.value, {})
            body_keywords = [(t, kw_dict[t]) for t in body_tokens if t in kw_dict]
            if body_keywords:
                parts.append("  Body uses:")
                for k, v in body_keywords:
                    parts.append(f"    `{k}` — {v}")
    return "\n".join(parts)


def _regex_explain_class(code: str, lang: CodeLanguage) -> str:
    cpat = _CLASS_PATTERNS.get(lang)
    if not cpat:
        return f"Class detection not supported for {lang.value}."
    matches = list(cpat.finditer(code))
    if not matches:
        return "No classes detected."
    parts: list[str] = []
    for m in matches:
        cname = m.group(1)
        parts.append(f"Class/struct `{cname}`:")
        # Find methods inside the class body
        start = m.end()
        brace_pos = code.find("{", start)
        if brace_pos != -1:
            depth = 0
            end = brace_pos
            for i in range(brace_pos, len(code)):
                if code[i] == "{":
                    depth += 1
                elif code[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            body = code[brace_pos + 1:end - 1]
            method_pat = _FUNC_PATTERNS.get(lang)
            if method_pat:
                methods = method_pat.findall(body)
                if methods:
                    parts.append(f"  Methods: {', '.join(m for m in methods if m)}")
    return "\n".join(parts)


def _regex_explain_imports(code: str, lang: CodeLanguage) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    import_patterns: list[tuple[re.Pattern[str], str]] = []
    if lang in (CodeLanguage.JAVASCRIPT, CodeLanguage.TYPESCRIPT):
        import_patterns = [
            (re.compile(r"import\s+\{([^}]+)\}\s+from\s+['\"]([^'\"]+)['\"]"), "named"),
            (re.compile(r"import\s+(\w+)\s+from\s+['\"]([^'\"]+)['\"]"), "default"),
            (re.compile(r"const\s+\{([^}]+)\}\s*=\s*require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"), "destructured require"),
            (re.compile(r"const\s+(\w+)\s*=\s*require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"), "require"),
        ]
    elif lang == CodeLanguage.JAVA:
        import_patterns = [
            (re.compile(r"import\s+(static\s+)?([\w.]+\*?)\s*;"), "java import"),
        ]
    elif lang == CodeLanguage.GO:
        import_patterns = [
            (re.compile(r'import\s+"([^"]+)"'), "go import"),
            (re.compile(r'import\s+\w+\s+"([^"]+)"'), "go named import"),
        ]
    elif lang == CodeLanguage.RUST:
        import_patterns = [
            (re.compile(r"use\s+([\w:]+(?:\s*\{[^}]+\})?)\s*;"), "rust use"),
        ]
    elif lang in (CodeLanguage.CPP, CodeLanguage.C):
        import_patterns = [
            (re.compile(r'#include\s*[<"]([^>"]+)[>"]'), "include"),
        ]
    elif lang == CodeLanguage.CSHARP:
        import_patterns = [
            (re.compile(r"using\s+([\w.]+)\s*;"), "using"),
        ]
    elif lang == CodeLanguage.PHP:
        import_patterns = [
            (re.compile(r"use\s+([\w\\]+(?:\s+as\s+\w+)?)\s*;"), "php use"),
            (re.compile(r"require(?:_once)?\s*[\(]?['\"]([^'\"]+)['\"]"), "require"),
            (re.compile(r"include(?:_once)?\s*[\(]?['\"]([^'\"]+)['\"]"), "include"),
        ]
    elif lang == CodeLanguage.RUBY:
        import_patterns = [
            (re.compile(r"require\s+['\"]([^'\"]+)['\"]"), "require"),
            (re.compile(r"require_relative\s+['\"]([^'\"]+)['\"]"), "require_relative"),
        ]
    elif lang == CodeLanguage.SWIFT:
        import_patterns = [
            (re.compile(r"import\s+(\w+)"), "swift import"),
        ]
    elif lang == CodeLanguage.KOTLIN:
        import_patterns = [
            (re.compile(r"import\s+([\w.]+)"), "kotlin import"),
        ]

    for pat, kind in import_patterns:
        for m in pat.finditer(code):
            line_num = code[:m.start()].count("\n") + 1
            stmt = m.group(0).strip()
            if kind in ("named", "destructured require"):
                names = m.group(1)
                module = m.group(2)
                results.append({"line": line_num, "statement": stmt, "explanation": f"Imports {names} from `{module}`."})
            elif kind in ("default", "require"):
                name = m.group(1)
                module = m.group(2)
                results.append({"line": line_num, "statement": stmt, "explanation": f"Imports `{name}` from `{module}`."})
            elif kind == "java import":
                is_static = bool(m.group(1))
                path = m.group(2)
                if is_static:
                    results.append({"line": line_num, "statement": stmt, "explanation": f"Static import from `{path}` — makes members directly accessible."})
                else:
                    results.append({"line": line_num, "statement": stmt, "explanation": f"Imports classes/types from `{path}`."})
            elif kind.startswith("go"):
                pkg = m.group(1)
                results.append({"line": line_num, "statement": stmt, "explanation": f"Imports package `{pkg}`."})
            elif kind == "rust use":
                path = m.group(1)
                results.append({"line": line_num, "statement": stmt, "explanation": f"Imports items from `{path}` into scope."})
            elif kind == "include":
                header = m.group(1)
                results.append({"line": line_num, "statement": stmt, "explanation": f"Includes header `{header}`."})
            elif kind == "using":
                ns = m.group(1)
                results.append({"line": line_num, "statement": stmt, "explanation": f"Imports namespace `{ns}`."})
            elif kind.startswith("php"):
                path = m.group(1)
                results.append({"line": line_num, "statement": stmt, "explanation": f"Imports class/namespace `{path}`."})
            elif kind.startswith("require") or kind.startswith("include"):
                path = m.group(1)
                results.append({"line": line_num, "statement": stmt, "explanation": f"Loads file `{path}`."})
            elif kind.startswith("swift"):
                mod = m.group(1)
                results.append({"line": line_num, "statement": stmt, "explanation": f"Imports module `{mod}`."})
            elif kind.startswith("kotlin"):
                path = m.group(1)
                results.append({"line": line_num, "statement": stmt, "explanation": f"Imports from `{path}`."})

    return results


def _regex_complexity(code: str, lang: CodeLanguage) -> dict[str, Any]:
    """Estimate cyclomatic complexity using regex for non-Python languages."""
    branch_keywords = {
        CodeLanguage.JAVASCRIPT: ["if", "else if", "elif", "for", "while", "switch", "case", "catch", "&&", "||", "?"],
        CodeLanguage.TYPESCRIPT: ["if", "else if", "elif", "for", "while", "switch", "case", "catch", "&&", "||", "?"],
        CodeLanguage.JAVA: ["if", "else if", "elif", "for", "while", "switch", "case", "catch", "&&", "||", "?"],
        CodeLanguage.GO: ["if", "else if", "for", "switch", "case", "select", "case <-", "&&", "||"],
        CodeLanguage.RUST: ["if", "else if", "for", "while", "loop", "match", "&&", "||"],
        CodeLanguage.CPP: ["if", "else if", "for", "while", "switch", "case", "catch", "&&", "||", "?"],
        CodeLanguage.C: ["if", "else if", "for", "while", "switch", "case", "&&", "||", "?"],
        CodeLanguage.CSHARP: ["if", "else if", "for", "foreach", "while", "switch", "case", "catch", "&&", "||", "?"],
        CodeLanguage.RUBY: ["if", "elsif", "unless", "for", "while", "until", "case", "when", "rescue", "&&", "||"],
        CodeLanguage.PHP: ["if", "elseif", "for", "foreach", "while", "switch", "case", "catch", "&&", "||", "?"],
        CodeLanguage.SWIFT: ["if", "else if", "for", "while", "switch", "case", "catch", "&&", "||", "?", "where", "guard"],
        CodeLanguage.KOTLIN: ["if", "else if", "for", "while", "when", "case", "catch", "&&", "||", "?:"],
    }
    keywords = branch_keywords.get(lang, branch_keywords.get(CodeLanguage.JAVASCRIPT, []))
    total = 1
    for kw in keywords:
        total += code.count(kw)
    # Subtract false positives from string literals
    for m in re.finditer(r'"[^"]*"|\'[^\']*\'', code):
        for kw in keywords:
            total -= m.group(0).count(kw)
    total = max(total, 1)
    rating = "low" if total <= 5 else "moderate" if total <= 10 else "high" if total <= 20 else "very high"
    return {"cyclomatic_complexity": total, "rating": rating}


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class CodeExplainer:
    """Explain code in natural language using AST (Python) or regex (other languages)."""

    def _resolve_lang(self, language: str | CodeLanguage) -> CodeLanguage:
        if isinstance(language, CodeLanguage):
            return language
        return CodeLanguage.from_ext(language)

    # ------------------------------------------------------------------
    # explain
    # ------------------------------------------------------------------

    def explain(
        self,
        code: str,
        language: str | CodeLanguage = CodeLanguage.PYTHON,
        detail_level: str = "medium",
    ) -> CodingResult:
        """Full code explanation."""
        lang = self._resolve_lang(language)
        parts: list[str] = []

        parts.append(f"Language: {lang.value}")
        parts.append(f"Detail level: {detail_level}")
        parts.append("")

        # Line-by-line breakdown
        parts.append("=== Line-by-Line Breakdown ===")
        line_expl = self._line_by_line(code, lang)
        parts.append(line_expl)

        # Functions
        parts.append("")
        parts.append("=== Functions ===")
        func_expl = self.explain_function(code, lang)
        parts.append(func_expl)

        # Classes
        parts.append("")
        parts.append("=== Classes ===")
        class_expl = self.explain_class(code, lang)
        parts.append(class_expl)

        # Imports
        parts.append("")
        parts.append("=== Imports ===")
        imports = self.explain_imports(code, lang)
        for imp in imports:
            parts.append(f"  Line {imp['line']}: {imp['statement']}")
            parts.append(f"    → {imp['explanation']}")

        # Complexity
        parts.append("")
        parts.append("=== Complexity ===")
        comp = self.complexity_report(code, lang)
        if "error" in comp:
            parts.append(f"  {comp['error']}")
        else:
            parts.append(f"  Cyclomatic complexity: {comp.get('cyclomatic_complexity', 'N/A')}")
            parts.append(f"  Rating: {comp.get('rating', 'N/A')}")
            funcs = comp.get("functions", {})
            if funcs:
                parts.append("  Per-function:")
                for fn, cc in funcs.items():
                    parts.append(f"    {fn}: {cc}")

        explanation = "\n".join(parts)
        return CodingResult(
            success=True,
            task_type=TaskType.EXPLAIN,
            code=code,
            explanation=explanation,
            metadata={"language": lang.value, "detail_level": detail_level},
        )

    # ------------------------------------------------------------------
    # explain_line
    # ------------------------------------------------------------------

    def explain_line(self, line_num: int, code: str, language: str | CodeLanguage = CodeLanguage.PYTHON) -> str:
        """Explain a single line of code."""
        lang = self._resolve_lang(language)
        lines = code.splitlines()
        if line_num < 1 or line_num > len(lines):
            return f"Line {line_num} is out of range (1-{len(lines)})."

        line = lines[line_num - 1].strip()
        if not line:
            return "Empty line."

        if lang == CodeLanguage.PYTHON:
            return self._explain_python_line(line_num, line, code)
        return self._explain_generic_line(line_num, line, lang)

    # ------------------------------------------------------------------
    # explain_function
    # ------------------------------------------------------------------

    def explain_function(self, func_code: str, language: str | CodeLanguage = CodeLanguage.PYTHON) -> str:
        """Explain a function's purpose, parameters, and return value."""
        lang = self._resolve_lang(language)
        if lang == CodeLanguage.PYTHON:
            return _py_explain_function(func_code)
        return _regex_explain_function(func_code, lang)

    # ------------------------------------------------------------------
    # explain_class
    # ------------------------------------------------------------------

    def explain_class(self, class_code: str, language: str | CodeLanguage = CodeLanguage.PYTHON) -> str:
        """Explain a class structure."""
        lang = self._resolve_lang(language)
        if lang == CodeLanguage.PYTHON:
            return _py_explain_class(class_code)
        return _regex_explain_class(class_code, lang)

    # ------------------------------------------------------------------
    # explain_imports
    # ------------------------------------------------------------------

    def explain_imports(self, code: str, language: str | CodeLanguage = CodeLanguage.PYTHON) -> list[dict[str, Any]]:
        """Explain what each import does."""
        lang = self._resolve_lang(language)
        if lang == CodeLanguage.PYTHON:
            return _py_explain_imports(code)
        return _regex_explain_imports(code, lang)

    # ------------------------------------------------------------------
    # complexity_report
    # ------------------------------------------------------------------

    def complexity_report(self, code: str, language: str | CodeLanguage = CodeLanguage.PYTHON) -> dict[str, Any]:
        """Cyclomatic complexity analysis."""
        lang = self._resolve_lang(language)
        if lang == CodeLanguage.PYTHON:
            return _py_complexity(code)
        return _regex_complexity(code, lang)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _line_by_line(self, code: str, lang: CodeLanguage) -> str:
        lines = code.splitlines()
        if lang == CodeLanguage.PYTHON:
            return self._python_line_by_line(code, lines)
        return self._generic_line_by_line(lines, lang)

    def _python_line_by_line(self, code: str, lines: list[str]) -> str:
        try:
            tree = ast.parse(textwrap.dedent(code))
            explained = _py_walk_with_lines(tree, code)
        except SyntaxError:
            explained = []

        mapping = {line_no: exp for line_no, exp in explained}
        parts: list[str] = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped:
                parts.append(f"  {i:>4}: (empty)")
                continue
            if i in mapping:
                parts.append(f"  {i:>4}: {stripped}")
                parts.append(f"         ↳ {mapping[i]}")
            else:
                # Simple heuristic
                parts.append(f"  {i:>4}: {stripped}")
                parts.append(f"         ↳ {self._simple_heuristic(stripped)}")
        return "\n".join(parts)

    def _generic_line_by_line(self, lines: list[str], lang: CodeLanguage) -> str:
        kw_dict = _KEYWORD_DOCS.get(lang.value, {})
        parts: list[str] = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped:
                parts.append(f"  {i:>4}: (empty)")
                continue
            parts.append(f"  {i:>4}: {stripped}")
            parts.append(f"         ↳ {self._simple_heuristic(stripped, kw_dict)}")
        return "\n".join(parts)

    def _explain_python_line(self, line_num: int, line: str, full_code: str) -> str:
        try:
            tree = ast.parse(textwrap.dedent(full_code))
            for node in ast.walk(tree):
                if getattr(node, "lineno", None) == line_num:
                    return _py_explain_node(node)
        except SyntaxError:
            pass
        return self._simple_heuristic(line)

    def _explain_generic_line(self, line_num: int, line: str, lang: CodeLanguage) -> str:
        kw_dict = _KEYWORD_DOCS.get(lang.value, {})
        return self._simple_heuristic(line, kw_dict)

    @staticmethod
    def _simple_heuristic(line: str, keywords: dict[str, str] | None = None) -> str:
        """Quick keyword-based heuristic when no deeper analysis is available."""
        if keywords is None:
            keywords = {}
        tokens = re.findall(r"[a-zA-Z_]\w*", line)
        found: list[str] = []
        for t in tokens:
            if t in keywords:
                found.append(f"`{t}`: {keywords[t]}")
        if found:
            return " | ".join(found[:3])
        if line.startswith("#") or line.startswith("//"):
            return "Comment line."
        if "TODO" in line.upper():
            return "Contains a TODO marker."
        if line.strip().endswith(":"):
            return "Opens a new block."
        if "=" in line and not line.strip().startswith(("==", "!=", "<=", ">=")):
            return "Assignment or comparison."
        return "General statement."
