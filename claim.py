"""Structured claims and semantic equivalence.

Task: T01.7.2a (claim structure and equivalence)

Architecture References:
- S-3    Claim decomposition: subject, predicate, qualifier, value
- S-3    Equivalence test: four conditions, all must hold
- S-3    Merge policy: conservative; under-merge preferred over over-merge
- S-3    Containment: narrower claim canonical, broader recorded separately
- R-5    Facts are canonical claims, not extraction events
- D-05   Equivalent extractions attach; they do not create a new Fact
- I2     Object identity is permanent, so merge errors are irreversible
- M-62   Semantic equivalence criterion (closed by S-3)

The asymmetry driving every choice here: under-merging inflates apparent
corroboration but leaves both claims visible, linked and correctable.
Over-merging destroys information irreversibly, because object identity is
permanent under I2 and merged attachments cannot be separated again.

Where equivalence cannot be established, the answer is UNCERTAIN and the
claims are NOT merged -- a deliberate bias recorded in S-3.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

# S-3 requires an explicit qualifier; an unqualified claim states NONE
# rather than leaving the field empty, so "unqualified" and "unrecorded"
# stay distinguishable.
UNQUALIFIED = "NONE"


class ClaimError(Exception):
    """Base class for claim structure violations."""


class ClaimStructureError(ClaimError):
    """A required claim component is absent. [S-3]"""


class PrecisionError(ClaimError):
    """A quantitative value lacks a stated precision. [S-3]"""


class Verdict(str, Enum):
    """Outcome of the S-3 equivalence test.

    Four outcomes, each mapping to a distinct merge action. CONTAINMENT is
    separate from EQUIVALENT because S-3 treats it differently: the narrower
    claim is canonical and the broader is recorded separately, since a broad
    claim is not evidence for a narrow one.
    """

    EQUIVALENT = "EQUIVALENT"
    CONTAINMENT = "CONTAINMENT"
    NOT_EQUIVALENT = "NOT_EQUIVALENT"
    UNCERTAIN = "UNCERTAIN"


class MergeAction(str, Enum):
    """What the merge policy dictates for a verdict. [S-3]"""

    MERGE = "MERGE"                      # add an attachment to the canonical Fact
    SEPARATE = "SEPARATE"                # create a distinct Fact, no link
    SEPARATE_WITH_DUPLICATES = "SEPARATE_WITH_DUPLICATES"


# S-3 merge policy, stated as data so it cannot drift from the decision.
MERGE_POLICY: dict[Verdict, MergeAction] = {
    Verdict.EQUIVALENT: MergeAction.MERGE,
    Verdict.CONTAINMENT: MergeAction.SEPARATE_WITH_DUPLICATES,
    Verdict.NOT_EQUIVALENT: MergeAction.SEPARATE,
    Verdict.UNCERTAIN: MergeAction.SEPARATE_WITH_DUPLICATES,
}


@dataclass(frozen=True)
class Quantity:
    """A numeric value with the precision at which it may be compared. [S-3]

    Precision is mandatory: S-3 requires values to "agree within stated
    precision", so an unstated precision makes the comparison undefined.
    """

    value: float
    precision: float
    unit: str = ""

    def __post_init__(self) -> None:
        if self.precision < 0:
            raise PrecisionError("precision must be non-negative [S-3]")

    def agrees_with(self, other: "Quantity") -> bool:
        """Whether two values agree within the coarser stated precision."""
        if self.unit != other.unit:
            return False
        tolerance = max(self.precision, other.precision)
        return abs(self.value - other.value) <= tolerance


def _normalise(text: str) -> str:
    """Case- and whitespace-insensitive comparison form.

    Deliberately shallow. S-3 records that subject and predicate identity
    "still require judgement" -- resolving "sellers" against "merchants" is
    outside what the structure makes automatic. Anything this cannot decide
    is reported UNCERTAIN, never guessed.
    """
    return re.sub(r"\s+", " ", text.strip().casefold())


@dataclass(frozen=True)
class Claim:
    """A claim decomposed into the four S-3 components.

    Structure is what makes equivalence checkable rather than an opinion,
    satisfying Principle 2: an engine can state *why* two claims were judged
    equivalent by pointing at the components.
    """

    subject: str
    predicate: str
    qualifier: str = UNQUALIFIED
    value: Quantity | None = None

    def __post_init__(self) -> None:
        if not (self.subject or "").strip():
            raise ClaimStructureError("claim subject is required [S-3]")
        if not (self.predicate or "").strip():
            raise ClaimStructureError("claim predicate is required [S-3]")
        if not (self.qualifier or "").strip():
            raise ClaimStructureError(
                f"claim qualifier is required; state {UNQUALIFIED!r} if "
                f"unqualified [S-3]"
            )

    @property
    def is_unqualified(self) -> bool:
        return _normalise(self.qualifier) == _normalise(UNQUALIFIED)

    @property
    def is_quantitative(self) -> bool:
        return self.value is not None

    def as_text(self) -> str:
        """Human-readable rendering, for explanation and audit."""
        parts = [self.subject, self.predicate]
        if self.value is not None:
            unit = f" {self.value.unit}" if self.value.unit else ""
            parts.append(f"{self.value.value}{unit}")
        if not self.is_unqualified:
            parts.append(f"({self.qualifier})")
        return " ".join(parts)

    # -- component comparison --------------------------------------------

    def same_subject(self, other: "Claim") -> bool:
        return _normalise(self.subject) == _normalise(other.subject)

    def same_predicate(self, other: "Claim") -> bool:
        return _normalise(self.predicate) == _normalise(other.predicate)

    def same_qualifier(self, other: "Claim") -> bool:
        return _normalise(self.qualifier) == _normalise(other.qualifier)

    def qualifier_contains(self, other: "Claim") -> bool:
        """Whether this claim's qualifier strictly contains the other's. [S-3]

        Only the unambiguous case is recognised: an unqualified claim is
        broader than any qualified one. Textual containment between two
        qualified claims is exactly the "subtle" case S-3 warns will be
        applied inconsistently, so it is reported UNCERTAIN instead.
        """
        return self.is_unqualified and not other.is_unqualified

    def values_agree(self, other: "Claim") -> bool | None:
        """Whether values agree. None when the comparison is undecidable."""
        if self.value is None and other.value is None:
            return True
        if self.value is None or other.value is None:
            # One side quantifies and the other does not: not the same claim.
            return False
        if self.value.unit != other.value.unit:
            return False
        return self.value.agrees_with(other.value)


@dataclass(frozen=True)
class EquivalenceResult:
    """The verdict plus the reasoning behind it. [Principle 2]"""

    verdict: Verdict
    reason: str
    canonical: Claim | None = None
    broader: Claim | None = None

    @property
    def action(self) -> MergeAction:
        return MERGE_POLICY[self.verdict]

    @property
    def may_merge(self) -> bool:
        return self.action is MergeAction.MERGE

    @property
    def requires_duplicates_link(self) -> bool:
        return self.action is MergeAction.SEPARATE_WITH_DUPLICATES


def assess_equivalence(left: Claim, right: Claim) -> EquivalenceResult:
    """Apply the four-condition S-3 equivalence test.

    Conditions are evaluated in order, and the first failure decides. Where
    a condition cannot be decided from structure alone, the result is
    UNCERTAIN and the claims are not merged.
    """
    # Condition 1 -- subjects refer to the same entity or class.
    if not left.same_subject(right):
        return EquivalenceResult(
            Verdict.NOT_EQUIVALENT,
            f"subjects differ: {left.subject!r} vs {right.subject!r}",
        )

    # Condition 2 -- predicates assert the same property or relation.
    if not left.same_predicate(right):
        return EquivalenceResult(
            Verdict.NOT_EQUIVALENT,
            f"predicates differ: {left.predicate!r} vs {right.predicate!r}",
        )

    # Condition 4 -- values, where both present, agree within precision.
    # Evaluated before qualifiers so a numeric disagreement is reported as
    # such rather than being masked by a qualifier verdict.
    values = left.values_agree(right)
    if values is False:
        return EquivalenceResult(
            Verdict.NOT_EQUIVALENT,
            "values disagree or only one claim is quantified",
        )

    # Condition 3 -- qualifiers identical, or one strictly contains the other.
    if left.same_qualifier(right):
        return EquivalenceResult(
            Verdict.EQUIVALENT,
            "subject, predicate, qualifier and value all agree",
            canonical=left,
        )

    if left.qualifier_contains(right):
        # The narrower claim is canonical; the broader is recorded separately.
        return EquivalenceResult(
            Verdict.CONTAINMENT,
            f"qualifier {left.qualifier!r} contains {right.qualifier!r}; "
            f"a broad claim is not evidence for a narrow one",
            canonical=right,
            broader=left,
        )
    if right.qualifier_contains(left):
        return EquivalenceResult(
            Verdict.CONTAINMENT,
            f"qualifier {right.qualifier!r} contains {left.qualifier!r}; "
            f"a broad claim is not evidence for a narrow one",
            canonical=left,
            broader=right,
        )

    # Two differently-qualified claims: containment is undecidable from
    # structure, which S-3 anticipates. Do not merge.
    return EquivalenceResult(
        Verdict.UNCERTAIN,
        f"qualifiers differ and containment is undecidable: "
        f"{left.qualifier!r} vs {right.qualifier!r}",
    )
