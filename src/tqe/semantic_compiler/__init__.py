"""Semantic-expression compiler boundary for SCP-1."""

from tqe.semantic_compiler.gaps import (
    missing_operationalization_gap,
    missing_operationalization_gap_expression,
)
from tqe.semantic_compiler.lowering import compile_semantic_expression, load_expression_from_path
from tqe.semantic_compiler.meaning_expression import (
    BridgeRefusal,
    BridgeRefusalKind,
    MissingGapCodeError,
    MeaningExpressionV0,
    VocabularyGateError,
    load_meaning_expression_from_path,
    load_meaning_expression_result,
    load_pack_vocabulary,
    require_meaning_expression,
    stable_expression_json,
)
from tqe.semantic_compiler.models import (
    CompilerOutcome,
    FootballQueryNormalForm,
    SemanticCompilerResult,
    SemanticExpression,
    SemanticGap,
    SemanticGapKind,
    SupportFacts,
)
from tqe.semantic_compiler.target_synthesis import (
    bind_payload_for_document,
    derived_semantic_correspondence,
    document_payload_for_expression,
    synthesize_and_bind,
    synthesize_search_target,
    target_file_payload,
    validate_correspondence_with_r1c_guard,
)

__all__ = [
    "BridgeRefusal",
    "BridgeRefusalKind",
    "CompilerOutcome",
    "FootballQueryNormalForm",
    "MissingGapCodeError",
    "MeaningExpressionV0",
    "SemanticCompilerResult",
    "SemanticExpression",
    "SemanticGap",
    "SemanticGapKind",
    "SupportFacts",
    "VocabularyGateError",
    "bind_payload_for_document",
    "compile_semantic_expression",
    "derived_semantic_correspondence",
    "document_payload_for_expression",
    "load_meaning_expression_from_path",
    "load_meaning_expression_result",
    "load_expression_from_path",
    "load_pack_vocabulary",
    "missing_operationalization_gap",
    "missing_operationalization_gap_expression",
    "require_meaning_expression",
    "stable_expression_json",
    "synthesize_and_bind",
    "synthesize_search_target",
    "target_file_payload",
    "validate_correspondence_with_r1c_guard",
]
