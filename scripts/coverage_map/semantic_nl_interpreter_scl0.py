#!/usr/bin/env python3
"""SCL-NL-0 request-to-football-meaning interpreter.

This module is deliberately vocabulary-blind. It turns terse user wording into
football meaning descriptions or clarification requests. It does not inspect
the downstream element vocabulary, provider catalog, target format, or search
machinery; the verification harness enforces that boundary by source check.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


MEANING_DEFINITION = "MEANING_DEFINITION"
CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"


@dataclass(frozen=True)
class NLMeaning:
    status: str
    request: str
    meaning_definition: str | None = None
    clarification_codes: tuple[str, ...] = ()
    clarification_questions: tuple[str, ...] = ()
    interpretation_rules: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "meaning_definition": self.meaning_definition,
            "clarification_codes": list(self.clarification_codes),
            "clarification_questions": list(self.clarification_questions),
            "interpretation_rules": list(self.interpretation_rules),
            "meaning_hash": meaning_hash(self),
        }


def interpret_request(
    request: str,
    *,
    disabled_downstream_elements: list[str] | tuple[str, ...] | None = None,
) -> NLMeaning:
    """Interpret a user request without reading downstream vocabulary state.

    ``disabled_downstream_elements`` is accepted only so the verifier can prove
    vocabulary-invariance: changing downstream availability must not change this
    layer's meaning output.
    """

    _ = tuple(disabled_downstream_elements or ())
    lower = normalize(request)

    if is_ambiguous_attack_request(lower):
        return NLMeaning(
            status=CLARIFICATION_REQUIRED,
            request=request,
            clarification_codes=("TACTICAL_MEANING_UNDERSPECIFIED",),
            clarification_questions=(
                "Specify what should make the attack dangerous, such as shot outcome, box entry, pressure, or expected-value model.",
            ),
            interpretation_rules=("nl.ambiguity.dangerous_attack",),
        )

    if is_give_and_go_request(lower):
        return meaning(
            request,
            "A give-and-go is a two-pass combination where the original passer plays to a teammate and then receives the return pass back as the terminal receiver.",
            "nl.meaning.two_pass_return_combination",
        )

    if is_onward_two_pass_request(lower):
        return meaning(
            request,
            "An onward two-pass sequence is a connected two-pass action where the original passer plays to a teammate and the teammate continues the ball to a different terminal receiver.",
            "nl.meaning.two_pass_onward_combination",
        )

    if is_progressive_carry_under_pressure_request(lower):
        return meaning(
            request,
            "A carry under defender pressure that also progresses forward.",
            "nl.meaning.carry_forward_under_pressure",
        )

    if is_line_break_without_underneath_support_request(lower):
        return meaning(
            request,
            "A controlled pass where the receiver moves beyond the observed second defending line and no underneath support outlet arrives in the behind-ball support region after reception.",
            "nl.meaning.line_break_without_underneath_support",
        )

    if is_receive_under_pressure_request(lower):
        return meaning(
            request,
            "A receiver controls the ball while under observed defender pressure.",
            "nl.meaning.receive_under_pressure",
        )

    if is_expected_completion_request(lower):
        return meaning(
            request,
            "Expected pass completion means a learned probability or likelihood that a pass will be completed.",
            "nl.meaning.learned_pass_expectation",
        )

    if is_body_orientation_request(lower):
        return meaning(
            request,
            "Goalkeeper set position means a goalkeeper body orientation or stance before the shot.",
            "nl.meaning.body_orientation_state",
        )

    if is_blindside_rotation_request(lower):
        return meaning(
            request,
            "A blindside rotation is a coordinated supporting movement around the opponent blind side that changes teammate positioning away from the ball.",
            "nl.meaning.blindside_rotation",
        )

    return NLMeaning(
        status=CLARIFICATION_REQUIRED,
        request=request,
        clarification_codes=("REQUEST_NOT_RECOGNIZED",),
        clarification_questions=("Restate the football situation with the action, actors, anchor, and outcome you want identified.",),
        interpretation_rules=("nl.ambiguity.unrecognized_request",),
    )


def meaning(request: str, definition: str, rule_id: str) -> NLMeaning:
    return NLMeaning(
        status=MEANING_DEFINITION,
        request=request,
        meaning_definition=definition,
        interpretation_rules=(rule_id,),
    )


def meaning_hash(value: NLMeaning) -> str:
    payload = {
        "status": value.status,
        "meaning_definition": value.meaning_definition,
        "clarification_codes": list(value.clarification_codes),
        "clarification_questions": list(value.clarification_questions),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def is_ambiguous_attack_request(lower: str) -> bool:
    return any(phrase in lower for phrase in ("dangerous attack", "dangerous attacks", "threatening attack", "good attack"))


def is_give_and_go_request(lower: str) -> bool:
    return any(
        phrase in lower
        for phrase in (
            "give-and-go",
            "give and go",
            "one-two",
            "one two",
            "wall pass",
            "wall passes",
            "bounce pass",
            "bounce passes",
            "up-back-through",
        )
    )


def is_onward_two_pass_request(lower: str) -> bool:
    return (
        "two-pass" in lower
        and any(phrase in lower for phrase in ("different receiver", "different terminal receiver", "onward", "third player"))
    )


def is_progressive_carry_under_pressure_request(lower: str) -> bool:
    has_carry = any(token in lower for token in ("carry", "carries", "carrying"))
    has_pressure = "pressure" in lower
    has_forward = any(token in lower for token in ("forward", "progress", "progressive"))
    return has_carry and has_pressure and has_forward


def is_line_break_without_underneath_support_request(lower: str) -> bool:
    has_line_break = any(
        phrase in lower
        for phrase in (
            "line break",
            "line-break",
            "line-breaking",
            "break the line",
            "broke the line",
            "breaks the line",
            "breaks second line",
            "break the second line",
            "second line",
        )
    )
    has_absence = any(phrase in lower for phrase in ("no ", "without", "empty", "absent", "stays empty"))
    has_support = any(phrase in lower for phrase in ("underneath", "support", "outlet"))
    return has_line_break and has_absence and has_support


def is_receive_under_pressure_request(lower: str) -> bool:
    return "receive" in lower and "pressure" in lower


def is_expected_completion_request(lower: str) -> bool:
    return "pass" in lower and any(token in lower for token in ("expected", "probability", "likelihood"))


def is_body_orientation_request(lower: str) -> bool:
    return any(token in lower for token in ("stance", "body orientation", "facing", "set position"))


def is_blindside_rotation_request(lower: str) -> bool:
    return "blindside" in lower and "rotation" in lower
