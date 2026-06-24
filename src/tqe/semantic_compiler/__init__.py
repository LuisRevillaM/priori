"""Semantic-expression compiler boundary for SCP-1."""

from tqe.semantic_compiler.lowering import compile_semantic_expression, load_expression_from_path
from tqe.semantic_compiler.models import (
    CompilerOutcome,
    FootballQueryNormalForm,
    SemanticCompilerResult,
    SemanticExpression,
    SemanticGap,
    SemanticGapKind,
    SupportFacts,
)

__all__ = [
    "CompilerOutcome",
    "FootballQueryNormalForm",
    "SemanticCompilerResult",
    "SemanticExpression",
    "SemanticGap",
    "SemanticGapKind",
    "SupportFacts",
    "compile_semantic_expression",
    "load_expression_from_path",
]
