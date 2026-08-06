"""Problem object type: the platform's first interpretive leap.

Task: T01.7.3

Architecture References:
- P-V1   supporting_facts non-empty; S-4 sufficiency threshold enforced
- P-V2   problem_statement contains no solution, proposed or implied
- P-V3   affected_population non-empty and specific
- P-V4   severity and frequency present
- P-V5   inference_basis references specific supporting Facts
- P-V6   Not a restatement of a single Fact
- P-I1   Remains solution-independent across all versions
- P-I2   Every supporting Fact resolves and is ACTIVE
- P-I3   Affected population never widened without supporting Facts
- P-I4   Weight never asserted beyond what Facts support
- S-4    Problem sufficiency: 2 independent sources across supporting Facts
- S-2    Support properties; P6 bounds support by contributing objects
- S-3    Conservative treatment of undecidable text comparison
- R-3    Two-component confidence; assertion_confidence is the interpretive half
- R-6    Closed taxonomy: DERIVES_FROM Problem -> Fact; SUPPORTS Fact -> Problem
- N-16   independent_source_count carried on every object
- V7     Create authority: Problem Intelligence
- M-12   Severity/frequency scales OPEN; bands land at T04.1.4
- M-21   Problem qualification criteria OPEN
- M-22   Problem identity and deduplication OPEN; deliberately not implemented
- IOM    section 3.3

Facts describe what is; a Problem asserts that something is *wrong*. A Fact
needs an anchor, a Problem needs an argument -- which is why inference_basis
exists separately from the universal explanation. `explanation` says why the
object exists in this form; `inference_basis` justifies the leap from
description to deficiency.

P-V2 guards solution smuggling: a problem framed as "lack of X" pre-determines
the Opportunity and Solution stages and collapses three engines into one.
Detection here is LEXICAL and therefore partial -- the IOM rates this failure
"Medium" detectability, and nothing in this module claims otherwise. What is
caught is the explicit framing; implicit smuggling in otherwise neutral prose
remains a residual risk, and problem qualification criteria are open [M-21].

Scope: the Problem type and its rules. Inference itself is the Problem
Intelligence Engine (T04.1.1); severity/frequency bands (T04.1.4) and
deduplication (T04.1.5, M-22) are deliberately absent here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable

from oip.acceptance import AcceptanceContext, RuleOutcome, RuleResult
from oip.contract import UniversalAttributes
from oip.enums import Engine, ObjectStatus, ObjectType
from oip.support import meets_sufficiency, sufficiency_threshold


class ProblemError(Exception):
    """Base class for Problem violations."""


class SupportingFactError(ProblemError):
    """supporting_facts absent, duplicated, or outside derives_from. [P-V1]"""


class SolutionSmugglingError(ProblemError):
    """problem_statement proposes or implies a solution. [P-V2]"""


class PopulationError(ProblemError):
    """affected_population absent or unspecific. [P-V3]"""


class WeightError(ProblemError):
    """severity or frequency absent. [P-V4]"""


class InferenceBasisError(ProblemError):
    """inference_basis absent or referencing non-supporting Facts. [P-V5]"""


# ---------------------------------------------------------------------------
# Text handling
# ---------------------------------------------------------------------------

def _normalised(text: str) -> str:
    """Case- and whitespace-insensitive comparison form.

    Deliberately shallow, matching the S-3 treatment of claim text: anything
    this cannot decide is reported as undecidable rather than guessed.
    """
    return re.sub(r"\s+", " ", (text or "").strip().casefold())


def _terms(text: str) -> frozenset[str]:
    """Content terms of a descriptor, for the P-I3 widening test."""
    return frozenset(re.findall(r"[a-z0-9]+", _normalised(text)))


def _verbatim_form(text: str) -> str:
    """Comparison form for the P-V6 restatement test.

    Case, spacing and punctuation are discarded; nothing else is. A statement
    differing from a claim only in those respects is the same sentence, and
    treating it otherwise would let a restatement through behind a full stop.
    Any difference beyond them is left to Layer-2-style semantic judgement and
    is NOT claimed to be caught here.
    """
    return " ".join(re.findall(r"[a-z0-9]+", _normalised(text)))


# Lexical markers of solution language. [P-V2]
#
# TUNING PARAMETERS, not architecture: the marker set may be extended without
# a decision record provided P-V2's meaning is unchanged. Two families are
# distinguished because they fail differently -- absence framing states the
# deficiency AS the missing remedy, remedy language names the remedy outright.
ABSENCE_MARKERS: tuple[str, ...] = (
    "lack of",
    "lacks",
    "lacking",
    "absence of",
    "no way to",
    "no ability to",
    "no mechanism",
    "no tool",
    "no feature",
    "no system",
    "there is no",
    "not available",
    "unavailable",
)

REMEDY_MARKERS: tuple[str, ...] = (
    "should be able to",
    "should have",
    "should provide",
    "should support",
    "needs a",
    "need a",
    "needs an",
    "need an",
    "needs to have",
    "requires a",
    "requires an",
    "would benefit from",
    "by adding",
    "by implementing",
    "by introducing",
    "by automating",
    "we propose",
    "we recommend",
    "the solution",
    "a solution",
    "solution is",
    "must be built",
    "should be built",
)

SOLUTION_MARKERS: tuple[str, ...] = ABSENCE_MARKERS + REMEDY_MARKERS

# Population descriptors carrying no discriminating content. [P-V3]
GENERIC_POPULATIONS: frozenset[str] = frozenset(
    {
        "everyone",
        "anyone",
        "all users",
        "users",
        "people",
        "customers",
        "the market",
        "everybody",
        "all customers",
        "the public",
        "n/a",
        "unknown",
        "various",
        "general population",
    }
)


def _marker_pattern(marker: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])")


# Compiled once: P-V2 scans every statement against every marker.
_MARKER_PATTERNS: dict[str, re.Pattern[str]] = {
    marker: _marker_pattern(marker) for marker in SOLUTION_MARKERS
}


def detect_solution_language(
    statement: str, markers: tuple[str, ...] = SOLUTION_MARKERS
) -> tuple[str, ...]:
    """Markers of solution framing found in a statement. [P-V2]

    LEXICAL ONLY. Catches the explicit "lack of X" framing the IOM names as
    the failure mode; it cannot catch a remedy implied by otherwise neutral
    prose. The residual is recorded, never presented as covered. [M-21]

    Matching is word-bounded. A plain substring test reported "blacklacks" as
    the marker "lacks", and a rule that fires on innocent prose would be
    switched off by the engines it is meant to constrain.
    """
    text = _normalised(statement)
    return tuple(
        marker
        for marker in markers
        if _MARKER_PATTERNS.get(marker, _marker_pattern(marker)).search(text)
    )


def is_generic_population(population: str) -> bool:
    """Whether a population descriptor discriminates nobody. [P-V3]"""
    return _normalised(population) in GENERIC_POPULATIONS


# ---------------------------------------------------------------------------
# Inference basis  [P-V5]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FactContribution:
    """What one supporting Fact establishes toward the inference. [P-V5]

    Structured rather than prose so that P-V5 -- "references specific
    supporting Facts" -- is mechanically checkable rather than an opinion,
    mirroring how S-3 decomposes a claim to make equivalence checkable.
    """

    fact_ref: str
    contribution: str

    def __post_init__(self) -> None:
        if not (self.fact_ref or "").strip():
            raise InferenceBasisError(
                "a contribution must name the Fact it comes from [P-V5]"
            )
        if not (self.contribution or "").strip():
            raise InferenceBasisError(
                f"contribution of {self.fact_ref!r} is empty; the inference "
                f"would rest on an unstated step [P-V5]"
            )


@dataclass(frozen=True)
class InferenceBasis:
    """Why these Facts indicate a problem. [P-V5, IOM section 3.3]

    Separate from the universal explanation by design: explanation says why
    the object exists in this form, inference_basis justifies the leap from
    description to deficiency. This is the one stage where those differ
    enough to warrant separate attributes.
    """

    contributions: tuple[FactContribution, ...]
    synthesis: str

    def __post_init__(self) -> None:
        if not self.contributions:
            raise InferenceBasisError(
                "inference_basis must reference at least one supporting Fact "
                "[P-V5]"
            )
        if not (self.synthesis or "").strip():
            raise InferenceBasisError(
                "inference_basis must state why the Facts TOGETHER indicate a "
                "deficiency, not merely what each says [P-V5, P-V6]"
            )
        seen: set[str] = set()
        for contribution in self.contributions:
            if contribution.fact_ref in seen:
                raise InferenceBasisError(
                    f"Fact {contribution.fact_ref!r} contributes twice"
                )
            seen.add(contribution.fact_ref)

    @property
    def referenced_facts(self) -> frozenset[str]:
        return frozenset(c.fact_ref for c in self.contributions)

    def contribution_of(self, fact_ref: str) -> FactContribution | None:
        for contribution in self.contributions:
            if contribution.fact_ref == fact_ref:
                return contribution
        return None


# ---------------------------------------------------------------------------
# Problem
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Problem:
    """A deficiency experienced by an identified population. [IOM section 3.3]

    Composes the universal contract with the Problem-specific payload. Frozen
    throughout: reformulation, added support and revised weight are all
    content changes and produce a new version under R-1.
    """

    attributes: UniversalAttributes
    problem_statement: str
    affected_population: str
    supporting_facts: tuple[str, ...]
    severity: str
    frequency: str
    problem_domain: str
    inference_basis: InferenceBasis

    # Optional attributes [IOM section 3.3]
    population_size_estimate: int | None = None
    existing_workarounds: str | None = None
    problem_persistence: str | None = None
    cost_indication: str | None = None

    def __post_init__(self) -> None:
        if self.attributes.object_type is not ObjectType.PROBLEM:
            raise ProblemError(
                f"expected Problem, got {self.attributes.object_type.value}"
            )
        if self.attributes.produced_by_engine is not Engine.PROBLEM_INTELLIGENCE:
            raise ProblemError(
                f"only Problem Intelligence may create Problems; got "
                f"{self.attributes.produced_by_engine.value} [V7]"
            )

        # Required attributes. Presence is checked at construction so a
        # Problem missing its argument cannot exist even transiently.
        if not (self.problem_statement or "").strip():
            raise ProblemError("problem_statement is required [IOM section 3.3]")
        if not (self.affected_population or "").strip():
            raise PopulationError(
                "affected_population is required; without it the deficiency "
                "belongs to nobody and cannot be sized [P-V3]"
            )
        if not (self.severity or "").strip():
            raise WeightError("severity is required [P-V4]")
        if not (self.frequency or "").strip():
            raise WeightError("frequency is required [P-V4]")
        if not (self.problem_domain or "").strip():
            raise ProblemError("problem_domain is required [IOM section 3.3]")
        if not isinstance(self.inference_basis, InferenceBasis):
            raise InferenceBasisError("inference_basis is required [P-V5]")

        # P-V1: at least one supporting Fact, no duplicates.
        if not self.supporting_facts:
            raise SupportingFactError(
                "a Problem requires at least one supporting Fact [P-V1]"
            )
        if len(set(self.supporting_facts)) != len(self.supporting_facts):
            raise SupportingFactError(
                "the same Fact supports the Problem twice; corroboration "
                "cannot be manufactured by repetition [P-V1]"
            )

        # SUPPORTS is drawn from the subset of DERIVES_FROM that evidences the
        # problem, so it can never name a Fact the engine did not read. [R-6]
        upstream = {ref.object_id for ref in self.attributes.derives_from}
        stray = sorted(set(self.supporting_facts) - upstream)
        if stray:
            raise SupportingFactError(
                f"supporting_facts {stray} are not in derives_from; SUPPORTS "
                f"is a subset of the Facts actually read [R-6, IOM section 3.3]"
            )
        wrong_type = sorted(
            ref.object_id
            for ref in self.attributes.derives_from
            if ref.object_type is not ObjectType.FACT
        )
        if wrong_type:
            raise ProblemError(
                f"a Problem derives from Facts only; {wrong_type} are not "
                f"Facts [R-6]"
            )

        # P-V5: the basis may not cite a Fact that does not support it.
        phantom = sorted(
            self.inference_basis.referenced_facts - set(self.supporting_facts)
        )
        if phantom:
            raise InferenceBasisError(
                f"inference_basis cites {phantom}, which do not support this "
                f"Problem [P-V5]"
            )

        if self.population_size_estimate is not None:
            if self.population_size_estimate < 0:
                raise PopulationError(
                    "population_size_estimate must be non-negative"
                )

    # -- delegated identity ----------------------------------------------

    @property
    def object_id(self) -> str:
        return self.attributes.object_id

    @property
    def lineage_id(self) -> str:
        return self.attributes.lineage_id

    @property
    def status(self) -> ObjectStatus:
        return self.attributes.status

    @property
    def independent_source_count(self) -> int:
        return self.attributes.independent_source_count

    @property
    def supporting_fact_count(self) -> int:
        return len(self.supporting_facts)

    @property
    def rests_on_a_single_fact(self) -> bool:
        """Whether the Problem could only be a restatement. [P-V6]"""
        return self.supporting_fact_count == 1

    @property
    def solution_markers(self) -> tuple[str, ...]:
        """Solution language detected in the statement. [P-V2]"""
        return detect_solution_language(self.problem_statement)

    @property
    def is_solution_independent(self) -> bool:
        """Whether no solution language is detectable. [P-V2, P-I1]"""
        return not self.solution_markers

    @property
    def meets_sufficiency(self) -> bool:
        """Whether the declared independent sources clear the S-4 floor."""
        return meets_sufficiency(
            ObjectType.PROBLEM, self.attributes.independent_source_count
        )

    @property
    def population_terms(self) -> frozenset[str]:
        return _terms(self.affected_population)

    def cites(self, fact_ref: str) -> bool:
        """Whether inference_basis names this supporting Fact. [P-V5]"""
        return fact_ref in self.inference_basis.referenced_facts

    def widens_population_of(self, earlier: "Problem") -> bool:
        """Whether this version broadens the earlier population. [P-I3]

        Only the unambiguous cases are recognised, mirroring S-3's treatment
        of containment: dropping qualifying terms broadens the population, and
        a raised size estimate broadens it numerically. Two descriptors that
        merely differ are undecidable from structure and are NOT reported as
        widening -- an unreliable widening signal would be worse than none.
        """
        later_terms, earlier_terms = self.population_terms, earlier.population_terms
        if later_terms < earlier_terms:
            return True
        if (
            self.population_size_estimate is not None
            and earlier.population_size_estimate is not None
            and self.population_size_estimate > earlier.population_size_estimate
        ):
            return True
        return False

    def adds_support_over(self, earlier: "Problem") -> bool:
        """Whether this version rests on strictly more Facts. [P-I3]"""
        return set(earlier.supporting_facts) < set(self.supporting_facts)


# ---------------------------------------------------------------------------
# Problem-specific acceptance rules  [P-V1 .. P-V6]
# ---------------------------------------------------------------------------

def _skip(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.SKIP, detail)


def _ok(rule_id: str, detail: str = "") -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.PASS, detail)


def _fail(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.FAIL, detail)


def _problem_of(ctx: AcceptanceContext) -> "Problem | None":
    return getattr(ctx, "problem", None)


def pv1_supporting_facts_sufficient(ctx: AcceptanceContext) -> RuleResult:
    """supporting_facts non-empty and sufficient. [P-V1, S-4]

    The IOM records the threshold as undefined (MISSING-06). S-4 subsequently
    closed M-06 and names P-V1 explicitly: a Problem requires 2 independent
    sources across its supporting Facts, and an object below the floor is
    REJECTED rather than accepted with low confidence.
    """
    if ctx.attributes.object_type is not ObjectType.PROBLEM:
        return _skip("P-V1", "not a Problem")
    problem = _problem_of(ctx)
    if problem is None:
        return _skip("P-V1", "no Problem payload supplied")

    if not problem.supporting_facts:
        return _fail("P-V1", "a Problem requires at least one supporting Fact")

    threshold = sufficiency_threshold(ObjectType.PROBLEM)
    declared = problem.independent_source_count
    if declared < threshold:
        return _fail(
            "P-V1",
            f"{declared} independent source(s) across {problem.supporting_fact_count} "
            f"supporting Fact(s); S-4 requires {threshold}. An inference of "
            f"deficiency from a single source is that source's opinion",
        )
    return _ok(
        "P-V1",
        f"{problem.supporting_fact_count} supporting Fact(s), {declared} "
        f"independent source(s) [S-4 floor {threshold}]",
    )


def pv2_solution_independent(ctx: AcceptanceContext) -> RuleResult:
    """problem_statement contains no solution, proposed or implied. [P-V2]

    Lexical detection. It catches the explicit framing -- "lack of X",
    "should provide Y" -- which is the failure mode the IOM names. It does
    not catch a remedy implied by neutral prose, and does not pretend to:
    problem qualification criteria remain open [M-21].
    """
    if ctx.attributes.object_type is not ObjectType.PROBLEM:
        return _skip("P-V2", "not a Problem")
    problem = _problem_of(ctx)
    if problem is None:
        return _skip("P-V2", "no Problem payload supplied")

    if not (problem.problem_statement or "").strip():
        return _fail(
            "P-V2",
            "problem_statement is absent; an unstated deficiency cannot be "
            "shown to be solution-independent",
        )

    markers = problem.solution_markers
    if markers:
        return _fail(
            "P-V2",
            f"problem_statement smuggles a solution: {list(markers)}. A "
            f"problem framed as a missing remedy pre-determines the "
            f"Opportunity and Solution stages",
        )
    return _ok(
        "P-V2",
        "no solution language detected; implicit smuggling not covered [M-21]",
    )


def pv3_population_specific(ctx: AcceptanceContext) -> RuleResult:
    """affected_population non-empty and specific. [P-V3]

    Structural check: present, and not a descriptor that discriminates
    nobody. Genuine specificity is a semantic judgement and is not claimed
    to be verified here [M-21].
    """
    if ctx.attributes.object_type is not ObjectType.PROBLEM:
        return _skip("P-V3", "not a Problem")
    problem = _problem_of(ctx)
    if problem is None:
        return _skip("P-V3", "no Problem payload supplied")

    if not (problem.affected_population or "").strip():
        return _fail("P-V3", "affected_population is absent")
    if is_generic_population(problem.affected_population):
        return _fail(
            "P-V3",
            f"affected_population {problem.affected_population!r} identifies "
            f"no one in particular; opportunity sizing becomes impossible",
        )
    return _ok("P-V3", "affected_population stated; specificity not proven [M-21]")


def pv4_weight_present(ctx: AcceptanceContext) -> RuleResult:
    """severity and frequency present. [P-V4]

    Presence only. No ordinal scale exists yet -- M-12 is open and the bands
    land at T04.1.4 -- so no ordering or comparison is asserted here.
    """
    if ctx.attributes.object_type is not ObjectType.PROBLEM:
        return _skip("P-V4", "not a Problem")
    problem = _problem_of(ctx)
    if problem is None:
        return _skip("P-V4", "no Problem payload supplied")

    missing = [
        name
        for name in ("severity", "frequency")
        if not (getattr(problem, name) or "").strip()
    ]
    if missing:
        return _fail(
            "P-V4", f"weight incomplete: {sorted(missing)}"
        )
    return _ok("P-V4", "severity and frequency present; no scale defined [M-12]")


def pv5_inference_basis_references_facts(ctx: AcceptanceContext) -> RuleResult:
    """inference_basis references specific supporting Facts. [P-V5]

    Distinct from V6, which checks the universal explanation. A Problem may
    have a complete explanation and still fail here: explanation says why the
    object exists in this form, inference_basis justifies the leap from
    description to deficiency.
    """
    if ctx.attributes.object_type is not ObjectType.PROBLEM:
        return _skip("P-V5", "not a Problem")
    problem = _problem_of(ctx)
    if problem is None:
        return _skip("P-V5", "no Problem payload supplied")

    basis = problem.inference_basis
    referenced = basis.referenced_facts
    if not referenced:
        return _fail("P-V5", "inference_basis references no Fact")
    if not (basis.synthesis or "").strip():
        return _fail(
            "P-V5",
            "inference_basis states no synthesis; a list of Facts is not an "
            "argument that a deficiency exists",
        )

    phantom = sorted(referenced - set(problem.supporting_facts))
    if phantom:
        return _fail(
            "P-V5",
            f"inference_basis cites {phantom}, which do not support this "
            f"Problem",
        )
    return _ok(
        "P-V5",
        f"{len(referenced)} of {problem.supporting_fact_count} supporting "
        f"Fact(s) cited by name",
    )


def pv6_not_a_single_fact_restatement(ctx: AcceptanceContext) -> RuleResult:
    """Not a restatement of a single Fact. [P-V6]

    Two checks. A Problem resting on one Fact can be nothing more than that
    Fact re-worded, so plural support is required. Where the Facts' claims are
    resolvable, the statement is additionally compared against each: a
    statement identical to a claim is a restatement however many Facts are
    attached.
    """
    if ctx.attributes.object_type is not ObjectType.PROBLEM:
        return _skip("P-V6", "not a Problem")
    problem = _problem_of(ctx)
    if problem is None:
        return _skip("P-V6", "no Problem payload supplied")

    if problem.rests_on_a_single_fact:
        return _fail(
            "P-V6",
            f"a single supporting Fact {problem.supporting_facts[0]!r} cannot "
            f"establish a Problem; the object would restate the Fact and "
            f"inflate its weight",
        )

    claim_text_of = getattr(ctx, "fact_claim_text", None)
    if claim_text_of is None:
        return _ok(
            "P-V6",
            f"{problem.supporting_fact_count} supporting Facts; claim text "
            f"unavailable, textual restatement unchecked",
        )

    statement = _verbatim_form(problem.problem_statement)
    for fact_ref in problem.supporting_facts:
        claim = claim_text_of(fact_ref)
        if claim is None:
            continue
        if _verbatim_form(claim) == statement:
            return _fail(
                "P-V6",
                f"problem_statement restates the claim of {fact_ref!r} "
                f"verbatim; no interpretive step was taken",
            )
    return _ok(
        "P-V6",
        f"{problem.supporting_fact_count} supporting Facts; statement differs "
        f"from every resolvable claim",
    )


pv1_supporting_facts_sufficient.rule_id = "P-V1"        # type: ignore[attr-defined]
pv2_solution_independent.rule_id = "P-V2"               # type: ignore[attr-defined]
pv3_population_specific.rule_id = "P-V3"                # type: ignore[attr-defined]
pv4_weight_present.rule_id = "P-V4"                     # type: ignore[attr-defined]
pv5_inference_basis_references_facts.rule_id = "P-V5"   # type: ignore[attr-defined]
pv6_not_a_single_fact_restatement.rule_id = "P-V6"      # type: ignore[attr-defined]

PROBLEM_RULES = (
    pv1_supporting_facts_sufficient,
    pv2_solution_independent,
    pv3_population_specific,
    pv4_weight_present,
    pv5_inference_basis_references_facts,
    pv6_not_a_single_fact_restatement,
)


# ---------------------------------------------------------------------------
# Problem integrity constraints  [P-I1 .. P-I4]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProblemViolation:
    """A breached Problem integrity constraint."""

    constraint_id: str
    object_id: str
    detail: str


@dataclass
class ProblemIntegrity:
    """Continuous verification of P-I1..P-I4. [IOM section 3.3]

    Detective, mirroring the universal, Evidence and Fact verifiers. Each of
    these can be breached by a path no single write controls: a later version
    reformulating the statement, an upstream Fact retracted afterwards, or a
    weight revised without the support to carry it.
    """

    problem_of: Callable[[str], "Problem | None"]
    store: "object"

    def verify(self) -> tuple[ProblemViolation, ...]:
        violations: list[ProblemViolation] = []
        violations.extend(self._check_pi1())
        violations.extend(self._check_pi2())
        violations.extend(self._check_pi3())
        violations.extend(self._check_pi4())
        return tuple(violations)

    def _all_problems(self) -> Iterable[tuple[str, "Problem"]]:
        for stored in self.store.objects_of_type(ObjectType.PROBLEM):
            problem = self.problem_of(stored.object_id)
            if problem is not None:
                yield stored.object_id, problem

    def _by_lineage(self) -> dict[str, list[tuple[int, str, "Problem"]]]:
        grouped: dict[str, list[tuple[int, str, "Problem"]]] = {}
        for object_id, problem in self._all_problems():
            grouped.setdefault(problem.lineage_id, []).append(
                (problem.attributes.version, object_id, problem)
            )
        for versions in grouped.values():
            versions.sort(key=lambda item: item[0])
        return grouped

    def _distinct_evidence_beneath(self, problem: "Problem") -> int | None:
        """Distinct Evidence objects grounding the supporting Facts. [N-16]

        Read from the derived graph index, which is rebuildable from objects
        and therefore never authoritative on its own [N-6]. Returns None when
        the graph cannot answer, so an unindexed store yields no verdict
        rather than a false one.
        """
        graph = getattr(self.store, "graph", None)
        if graph is None:
            return None
        grounding: set[str] = set()
        for fact_ref in problem.supporting_facts:
            if not graph.contains(fact_ref):
                return None
            grounding |= set(graph.evidence_set(fact_ref))
        return len(grounding)

    def _check_pi1(self) -> list[ProblemViolation]:
        """Remains solution-independent across all versions. [P-I1]

        Every version is re-checked, not only the current one. A reformulation
        that smuggles a remedy in version 4 breaches P-I1 even if version 1
        was clean, and P-V2 alone would not surface it afterwards.
        """
        violations: list[ProblemViolation] = []
        for object_id, problem in self._all_problems():
            markers = problem.solution_markers
            if markers:
                violations.append(
                    ProblemViolation(
                        "P-I1", object_id,
                        f"version {problem.attributes.version} states a "
                        f"solution: {list(markers)}; solution-independence "
                        f"must hold across all versions",
                    )
                )
        return violations

    def _check_pi2(self) -> list[ProblemViolation]:
        """Every supporting Fact resolves and is ACTIVE. [P-I2]

        Resolution is required of every version -- a broken reference is a
        broken lineage whatever the object's status. Currency (ACTIVE) is
        required only of ACTIVE Problems: a SUPERSEDED or INVALIDATED version
        asserts nothing, and demanding live support from it would report a
        completed cascade as a violation.
        """
        violations: list[ProblemViolation] = []
        for object_id, problem in self._all_problems():
            stored = self.store.find(object_id)
            is_current = stored is not None and stored.status is ObjectStatus.ACTIVE
            for fact_ref in problem.supporting_facts:
                upstream = self.store.find(fact_ref)
                if upstream is None:
                    violations.append(
                        ProblemViolation(
                            "P-I2", object_id,
                            f"supporting Fact {fact_ref!r} is not stored; the "
                            f"inference has no verifiable support",
                        )
                    )
                    continue
                if upstream.object_type is not ObjectType.FACT:
                    violations.append(
                        ProblemViolation(
                            "P-I2", object_id,
                            f"supporting reference {fact_ref!r} is a "
                            f"{upstream.object_type.value}, not a Fact",
                        )
                    )
                elif is_current and upstream.status is not ObjectStatus.ACTIVE:
                    violations.append(
                        ProblemViolation(
                            "P-I2", object_id,
                            f"is ACTIVE but supporting Fact {fact_ref!r} is "
                            f"{upstream.status.value}",
                        )
                    )
        return violations

    def _check_pi3(self) -> list[ProblemViolation]:
        """Population never widened without supporting Facts. [P-I3]

        Compared across consecutive versions of a lineage. Only unambiguous
        widening is recognised (see Problem.widens_population_of): an
        unreliable signal here would either block legitimate reformulation or
        wave through genuine over-generalisation.
        """
        violations: list[ProblemViolation] = []
        for versions in self._by_lineage().values():
            for (_, _, earlier), (_, later_id, later) in zip(
                versions, versions[1:]
            ):
                if not later.widens_population_of(earlier):
                    continue
                if later.adds_support_over(earlier):
                    continue
                violations.append(
                    ProblemViolation(
                        "P-I3", later_id,
                        f"affected population widened from "
                        f"{earlier.affected_population!r} to "
                        f"{later.affected_population!r} without additional "
                        f"supporting Facts",
                    )
                )
        return violations

    def _check_pi4(self) -> list[ProblemViolation]:
        """Weight never asserted beyond what Facts support. [P-I4]

        Three bounds, each derived from a ratified decision and each
        mechanical:

        - independent_source_count may not exceed the sum of the supporting
          Facts' own counts [N-16, S-4].
        - independent_source_count may not exceed the number of DISTINCT
          Evidence objects beneath those Facts. Evidence contributes exactly
          one independent source by definition [N-16, EVIDENCE_SOURCE_COUNT],
          so two Facts attesting the same Evidence cannot supply two sources.
          Without this the sum above is defeated by shared grounding.
        - evidential_support may not exceed the support of the contributing
          Facts [S-2 P6].

        All three are UPPER bounds. Syndicated but distinct Evidence still
        counts more than once here; collapsing it requires independence
        grouping, which is T02.1.3 and remains open [M-23].

        Severity and frequency themselves are NOT compared: no scale exists
        (M-12), and inventing an ordering here would pre-empt T04.1.4.
        """
        violations: list[ProblemViolation] = []
        for object_id, problem in self._all_problems():
            available = 0
            supports: list[float] = []
            resolved = 0
            for fact_ref in problem.supporting_facts:
                upstream = self.store.find(fact_ref)
                if upstream is None or upstream.object_type is not ObjectType.FACT:
                    continue  # P-I2 reports the broken reference
                resolved += 1
                available += upstream.attributes.independent_source_count
                supports.append(upstream.attributes.confidence.evidential_support)

            if resolved == 0:
                continue

            declared = problem.independent_source_count
            if declared > available:
                violations.append(
                    ProblemViolation(
                        "P-I4", object_id,
                        f"asserts {declared} independent source(s) but its "
                        f"supporting Facts carry at most {available}; weight "
                        f"exceeds what the Facts support",
                    )
                )
            elif resolved == len(problem.supporting_facts):
                grounding = self._distinct_evidence_beneath(problem)
                if grounding is not None and declared > grounding:
                    violations.append(
                        ProblemViolation(
                            "P-I4", object_id,
                            f"asserts {declared} independent source(s) but "
                            f"rests on only {grounding} distinct Evidence "
                            f"object(s); supporting Facts share grounding "
                            f"[N-16]",
                        )
                    )

            asserted_support = problem.attributes.confidence.evidential_support
            ceiling = min(supports)
            if asserted_support > ceiling + 1e-9:
                violations.append(
                    ProblemViolation(
                        "P-I4", object_id,
                        f"evidential_support {asserted_support} exceeds the "
                        f"weakest supporting Fact's {ceiling} [S-2 P6]",
                    )
                )
        return violations


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass
class ProblemRegistry:
    """Holds Problem payloads. [IOM section 3.3]

    Mirrors EvidenceRegistry and FactRegistry: the universal contract carries
    identity, confidence and status; the payload carries the statement, the
    population, the weight and the argument.

    Deduplication is deliberately absent. Problem identity is open under M-22
    and lands at T04.1.5; a provisional merge here would be irreversible under
    I2.
    """

    store: "object"
    _payloads: dict[str, Problem] = field(default_factory=dict, init=False)

    def register(self, problem: Problem) -> Problem:
        self._payloads[problem.object_id] = problem
        return problem

    def get(self, object_id: str) -> Problem | None:
        return self._payloads.get(object_id)

    def active_problems(self) -> tuple[Problem, ...]:
        problems = []
        for object_id, problem in self._payloads.items():
            stored = self.store.find(object_id)
            if stored is not None and stored.status is ObjectStatus.ACTIVE:
                problems.append(problem)
        return tuple(problems)

    def supported_by(self, fact_ref: str) -> tuple[Problem, ...]:
        """Problems resting on a given Fact, for impact inspection. [P-I2]"""
        return tuple(
            problem
            for problem in self._payloads.values()
            if fact_ref in problem.supporting_facts
        )

    def integrity(self) -> ProblemIntegrity:
        return ProblemIntegrity(problem_of=self.get, store=self.store)

    def __len__(self) -> int:
        return len(self._payloads)
