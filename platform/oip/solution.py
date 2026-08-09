"""Solution object type: the bridge between analysis and action.

Task: T01.7.6

Architecture References:
- S-V1   addresses_opportunity resolvable and ACTIVE
- S-V2   assumptions non-empty -- a Solution with no assumptions is invalid
- S-V3   Every assumption has criticality and testability
- S-V4   problem_fit_rationale references specific Problems via lineage
- S-V5   solution_statement is not a restatement of the Opportunity
- S-V6   feasibility_assessment present
- S-I1   Assumptions never removed, only superseded with rationale
- S-I2   Demonstrably addresses the Problems beneath its Opportunity
- S-I3   Sibling candidates never silently collapsed
- S-I4   Never modifies its Opportunity's assessment
- R-1    Objects immutable; assumption refinement produces a new version
- R-3    evidential_support inherited from the Opportunity; ceiling enforced
- R-6    DERIVES_FROM Opportunity; ADDRESSES Opportunity and Problem
- S-4    Solution inherits its Opportunity's sufficiency; adds no evidence
- N-6    Objects authoritative; the graph is a derived index
- N-14   Lineage-restricted read of the underlying Problems
- M-29   Solution depth / granularity OPEN (T07.2.1)
- M-69   Constraint model OPEN (T07.2.3); constraints carried, not typed
- M-31   Gate ownership OPEN: Validation reports, it does not gate
- IOM    section 3.6

The Solution object's most important function is generating the TESTABLE
SURFACE for Validation. Assumptions are what Validation tests, so a Solution
with unstated assumptions is unvalidatable and the platform's central
safeguard is bypassed. That is why S-V2 is unusual in requiring the PRESENCE
of uncertainty: a solution claiming no assumptions is either trivial or
concealing them, and concealment is this stage's most damaging failure.

Assumptions are structured rather than prose because Validation's TESTS
relationship targets INDIVIDUAL ASSUMPTIONS, not the Solution as a whole.
Unstructured prose would make claim-level validation impossible.

A NOTE ON GATING, reproduced deliberately. A Solution whose assumptions FAIL
validation does not automatically become REJECTED. Validation reports; it
does not gate, because gate ownership is unassigned under M-31. The Solution
remains ACTIVE with failed Validations attached until something decides
otherwise. This module does not invent that decider.

Scope: the Solution type and its rules. Formulation itself is Solution
Intelligence (T07.2.2); the typed constraint model (T07.2.3, M-69), the
granularity decision (T07.2.1, M-29) and sibling-candidate management
(T07.2.5) are deliberately absent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable

from oip.acceptance import AcceptanceContext, RuleOutcome, RuleResult
from oip.contract import UniversalAttributes
from oip.enums import Engine, ObjectStatus, ObjectType


class SolutionError(Exception):
    """Base class for Solution violations."""


class AssumptionError(SolutionError):
    """assumptions absent, duplicated, or incomplete. [S-V2, S-V3]"""


class AssumptionRemovalError(SolutionError):
    """An assumption was removed without rationale. [S-I1]"""


class OpportunityReferenceError(SolutionError):
    """addresses_opportunity absent or outside lineage. [S-V1]"""


class ProblemFitError(SolutionError):
    """problem_fit_rationale absent or citing unreachable Problems. [S-V4]"""


class FeasibilityError(SolutionError):
    """feasibility_assessment absent. [S-V6]"""


class CandidateGroupError(SolutionError):
    """candidate_group absent. [S-I3]"""


def _normalised(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().casefold())


def _verbatim_form(text: str) -> str:
    """Comparison form for the S-V5 restatement test.

    Case, spacing and punctuation are discarded; nothing else is. A statement
    differing from the Opportunity only in those respects is the same
    sentence, and treating it otherwise would let a restatement through
    behind a full stop -- the defect found at the Problem stage. Any
    difference beyond them is semantic and is NOT claimed to be caught.
    """
    return " ".join(re.findall(r"[a-z0-9]+", _normalised(text)))


# ---------------------------------------------------------------------------
# Assumptions  [S-V2, S-V3, S-I1]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Assumption:
    """One explicit, individually testable assumption. [IOM section 3.6]

    Addressable by assumption_id because Validation's TESTS relationship
    targets a single assumption, not the Solution as a whole.

    criticality and testability are required but their VOCABULARIES are not
    constrained. The IOM shows CRITICAL and MODERATE in prose and defines no
    closed taxonomy; inventing one here would fix a scale the architecture
    has not chosen, exactly as severity/frequency were left open at the
    Problem stage under M-12.
    """

    assumption_id: str
    assumption_statement: str
    criticality: str
    testability: str

    def __post_init__(self) -> None:
        if not (self.assumption_id or "").strip():
            raise AssumptionError("an assumption requires an assumption_id [S-V3]")
        if not (self.assumption_statement or "").strip():
            raise AssumptionError(
                f"assumption {self.assumption_id!r} states nothing; an "
                f"unstated assumption cannot be tested [S-V2]"
            )
        if not (self.criticality or "").strip():
            raise AssumptionError(
                f"assumption {self.assumption_id!r} requires criticality; "
                f"whether the solution fails if this is false must be stated "
                f"[S-V3]"
            )
        if not (self.testability or "").strip():
            raise AssumptionError(
                f"assumption {self.assumption_id!r} requires testability; an "
                f"untestable assumption bypasses Validation [S-V3]"
            )


@dataclass(frozen=True)
class AssumptionSupersession:
    """Why an assumption was withdrawn between versions. [S-I1]

    S-I1 permits supersession but not removal. The rationale is mandatory
    because a silently dropped assumption is indistinguishable from one that
    was concealed, and concealment is this stage's defining failure.
    """

    assumption_id: str
    rationale: str

    def __post_init__(self) -> None:
        if not (self.assumption_id or "").strip():
            raise AssumptionRemovalError(
                "a supersession must name the assumption it withdraws [S-I1]"
            )
        if not (self.rationale or "").strip():
            raise AssumptionRemovalError(
                f"withdrawing assumption {self.assumption_id!r} requires a "
                f"rationale; assumptions are superseded, never removed [S-I1]"
            )


# ---------------------------------------------------------------------------
# Problem fit  [S-V4, S-I2]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProblemFit:
    """How the approach addresses one underlying Problem. [S-V4]

    Structured so "references specific Problems" is mechanically checkable
    rather than an opinion, mirroring InferenceBasis at the Problem stage and
    GroupingRationale at the Pattern stage.
    """

    problem_ref: str
    how_addressed: str

    def __post_init__(self) -> None:
        if not (self.problem_ref or "").strip():
            raise ProblemFitError(
                "a problem fit must name the Problem it addresses [S-V4]"
            )
        if not (self.how_addressed or "").strip():
            raise ProblemFitError(
                f"fit for {self.problem_ref!r} is empty; lineage would be "
                f"intact but semantically empty [S-V4]"
            )


@dataclass(frozen=True)
class ProblemFitRationale:
    """Why this approach addresses the Problems beneath its Opportunity.

    shared_approach carries the claim; the fits say what each Problem
    contributes to it. Generic solutioning -- an approach that could have been
    written without reading the inputs -- is this stage's quiet failure, and
    naming specific Problems is what makes it detectable. [S-V4, S-I2]
    """

    shared_approach: str
    fits: tuple[ProblemFit, ...]

    def __post_init__(self) -> None:
        if not (self.shared_approach or "").strip():
            raise ProblemFitError(
                "problem_fit_rationale must state how the approach addresses "
                "the underlying structure [S-V4]"
            )
        if not self.fits:
            raise ProblemFitError(
                "problem_fit_rationale must reference specific Problems [S-V4]"
            )
        seen: set[str] = set()
        for fit in self.fits:
            if fit.problem_ref in seen:
                raise ProblemFitError(
                    f"Problem {fit.problem_ref!r} is addressed twice"
                )
            seen.add(fit.problem_ref)

    @property
    def referenced_problems(self) -> frozenset[str]:
        return frozenset(f.problem_ref for f in self.fits)

    def fit_for(self, problem_ref: str) -> ProblemFit | None:
        for fit in self.fits:
            if fit.problem_ref == problem_ref:
                return fit
        return None


# ---------------------------------------------------------------------------
# Solution
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Solution:
    """A concrete approach to an Opportunity, with assumptions stated.

    Composes the universal contract with the Solution-specific payload.
    Frozen: assumption refinement is a content change producing a new version
    under R-1, which is also what S-I1 requires -- an assumption is
    superseded with rationale, never edited away.
    """

    attributes: UniversalAttributes
    solution_statement: str
    addresses_opportunity: str
    assumptions: tuple[Assumption, ...]
    problem_fit_rationale: ProblemFitRationale
    feasibility_assessment: str
    candidate_group: str

    # Constraints are CARRIED, not typed. M-69 defines no constraint model,
    # so a vocabulary here would close a marker the architecture has not.
    constraints: tuple[str, ...] = ()

    # Optional attributes [IOM section 3.6]
    differentiators: str | None = None
    dependencies: tuple[str, ...] = ()
    risk_factors: tuple[str, ...] = ()
    precedents: tuple[str, ...] = ()
    superseded_assumptions: tuple[AssumptionSupersession, ...] = ()

    def __post_init__(self) -> None:
        if self.attributes.object_type is not ObjectType.SOLUTION:
            raise SolutionError(
                f"expected Solution, got {self.attributes.object_type.value}"
            )
        if self.attributes.produced_by_engine is not Engine.SOLUTION_INTELLIGENCE:
            raise SolutionError(
                f"only Solution Intelligence may create Solutions; got "
                f"{self.attributes.produced_by_engine.value} [V7]"
            )

        if not (self.solution_statement or "").strip():
            raise SolutionError("solution_statement is required [IOM section 3.6]")
        if not (self.feasibility_assessment or "").strip():
            raise FeasibilityError(
                "feasibility_assessment is required; validation effort spent "
                "on impossible approaches is wasted [S-V6]"
            )
        if not (self.candidate_group or "").strip():
            raise CandidateGroupError(
                "candidate_group is required; competing candidates must be "
                "groupable or comparative validation is impossible [S-I3]"
            )
        if not isinstance(self.problem_fit_rationale, ProblemFitRationale):
            raise ProblemFitError("problem_fit_rationale is required [S-V4]")

        # S-V2: the presence of uncertainty is mandatory.
        if not self.assumptions:
            raise AssumptionError(
                "a Solution with no assumptions is invalid; it is either "
                "trivial or concealing them, and concealment bypasses "
                "Validation entirely [S-V2]"
            )
        seen: set[str] = set()
        for assumption in self.assumptions:
            if assumption.assumption_id in seen:
                raise AssumptionError(
                    f"assumption_id {assumption.assumption_id!r} is not unique "
                    f"within the Solution; Validation could not address it "
                    f"[S-V3]"
                )
            seen.add(assumption.assumption_id)

        # S-V1: ADDRESSES is drawn from what the engine actually derived from.
        if not (self.addresses_opportunity or "").strip():
            raise OpportunityReferenceError(
                "addresses_opportunity is required [S-V1]"
            )
        upstream = {ref.object_id for ref in self.attributes.derives_from}
        if self.addresses_opportunity not in upstream:
            raise OpportunityReferenceError(
                f"addresses_opportunity {self.addresses_opportunity!r} is not "
                f"in derives_from; a Solution addresses the Opportunity it "
                f"read [R-6]"
            )
        wrong_type = sorted(
            ref.object_id
            for ref in self.attributes.derives_from
            if ref.object_type is not ObjectType.OPPORTUNITY
        )
        if wrong_type:
            raise SolutionError(
                f"a Solution derives from Opportunities only; {wrong_type} "
                f"are not Opportunities [R-6]"
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
    def assumption_count(self) -> int:
        return len(self.assumptions)

    @property
    def assumption_ids(self) -> frozenset[str]:
        return frozenset(a.assumption_id for a in self.assumptions)

    @property
    def addressed_problems(self) -> frozenset[str]:
        return self.problem_fit_rationale.referenced_problems

    def assumption(self, assumption_id: str) -> Assumption | None:
        """Resolve one assumption. Validation TESTS these individually."""
        for a in self.assumptions:
            if a.assumption_id == assumption_id:
                return a
        return None

    def withdrew(self, assumption_id: str) -> AssumptionSupersession | None:
        for record in self.superseded_assumptions:
            if record.assumption_id == assumption_id:
                return record
        return None

    def addresses(self, problem_ref: str) -> bool:
        """Whether problem_fit_rationale names this Problem. [S-V4]"""
        return problem_ref in self.addressed_problems

    def retains_assumptions_of(self, earlier: "Solution") -> tuple[str, ...]:
        """Assumption ids dropped without a recorded supersession. [S-I1]"""
        dropped = set(earlier.assumption_ids) - set(self.assumption_ids)
        return tuple(
            sorted(aid for aid in dropped if self.withdrew(aid) is None)
        )

    def is_sibling_of(self, other: "Solution") -> bool:
        """Whether both are competing candidates for one Opportunity. [S-I3]"""
        return (
            self.candidate_group == other.candidate_group
            and self.object_id != other.object_id
        )


# ---------------------------------------------------------------------------
# Solution-specific acceptance rules  [S-V1 .. S-V6]
# ---------------------------------------------------------------------------

def _skip(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.SKIP, detail)


def _ok(rule_id: str, detail: str = "") -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.PASS, detail)


def _fail(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.FAIL, detail)


def _solution_of(ctx: AcceptanceContext) -> "Solution | None":
    return getattr(ctx, "solution", None)


def sv1_opportunity_resolves_and_is_active(ctx: AcceptanceContext) -> RuleResult:
    """addresses_opportunity resolvable and ACTIVE. [S-V1]

    ACTIVE specifically, not merely resolvable. Building on a withdrawn or
    rejected Opportunity is how declined knowledge re-enters the pipeline,
    which I8 forbids universally and S-V1 states for this reference.
    """
    if ctx.attributes.object_type is not ObjectType.SOLUTION:
        return _skip("S-V1", "not a Solution")
    solution = _solution_of(ctx)
    if solution is None:
        return _skip("S-V1", "no Solution payload supplied")

    ref = solution.addresses_opportunity
    if not (ref or "").strip():
        return _fail("S-V1", "addresses_opportunity is absent")

    if ctx.resolve_type is None:
        return _skip("S-V1", "opportunity declared; no resolver supplied")

    actual = ctx.resolve_type(ref)
    if actual is None:
        return _fail("S-V1", f"opportunity {ref!r} does not resolve")
    if actual is not ObjectType.OPPORTUNITY:
        return _fail(
            "S-V1", f"{ref!r} is a {actual.value}, not an Opportunity"
        )

    if ctx.upstream_status is None:
        return _skip("S-V1", "opportunity resolves; no status provider")
    status = ctx.upstream_status(ref)
    if status is not ObjectStatus.ACTIVE:
        return _fail(
            "S-V1",
            f"opportunity {ref!r} is "
            f"{status.value if status else 'UNRESOLVED'}, not ACTIVE; a "
            f"Solution may not address a withdrawn Opportunity",
        )
    return _ok("S-V1", f"addresses ACTIVE opportunity {ref!r}")


def sv2_assumptions_present(ctx: AcceptanceContext) -> RuleResult:
    """assumptions non-empty. [S-V2]

    Unusual in requiring the PRESENCE of uncertainty. A Solution claiming no
    assumptions is either trivial or concealing them, and Validation would
    then have nothing to test.
    """
    if ctx.attributes.object_type is not ObjectType.SOLUTION:
        return _skip("S-V2", "not a Solution")
    solution = _solution_of(ctx)
    if solution is None:
        return _skip("S-V2", "no Solution payload supplied")

    if not solution.assumptions:
        return _fail(
            "S-V2",
            "no assumptions stated; a Solution with none is either trivial or "
            "concealing them, and Validation would have nothing to test",
        )
    return _ok(
        "S-V2", f"{solution.assumption_count} assumption(s) stated"
    )


def sv3_assumptions_are_testable(ctx: AcceptanceContext) -> RuleResult:
    """Every assumption has criticality and testability. [S-V3]

    Presence only. No criticality scale is asserted: the IOM shows CRITICAL
    and MODERATE in prose and defines no closed vocabulary.
    """
    if ctx.attributes.object_type is not ObjectType.SOLUTION:
        return _skip("S-V3", "not a Solution")
    solution = _solution_of(ctx)
    if solution is None:
        return _skip("S-V3", "no Solution payload supplied")

    incomplete: list[str] = []
    for assumption in solution.assumptions:
        missing = [
            name
            for name in ("criticality", "testability")
            if not (getattr(assumption, name) or "").strip()
        ]
        if missing:
            incomplete.append(f"{assumption.assumption_id} lacks {sorted(missing)}")
    if incomplete:
        return _fail(
            "S-V3",
            f"assumptions are not individually testable: {incomplete}; "
            f"Validation TESTS single assumptions",
        )
    ids = sorted(solution.assumption_ids)
    return _ok("S-V3", f"all assumptions addressable and testable: {ids}")


def sv4_problem_fit_references_lineage(ctx: AcceptanceContext) -> RuleResult:
    """problem_fit_rationale references specific Problems via lineage. [S-V4]

    Two halves. The rationale must name Problems, and those Problems must be
    genuinely reachable upstream. Citing a Problem the Solution does not
    derive from is generic solutioning wearing a lineage citation -- the
    failure mode where lineage is intact but semantically empty. [N-14]
    """
    if ctx.attributes.object_type is not ObjectType.SOLUTION:
        return _skip("S-V4", "not a Solution")
    solution = _solution_of(ctx)
    if solution is None:
        return _skip("S-V4", "no Solution payload supplied")

    rationale = solution.problem_fit_rationale
    if not (rationale.shared_approach or "").strip():
        return _fail(
            "S-V4",
            "problem_fit_rationale states no approach; a list of Problems is "
            "not a demonstration of fit",
        )
    referenced = rationale.referenced_problems
    if not referenced:
        return _fail("S-V4", "problem_fit_rationale references no Problem")

    if ctx.lineage_problems is None:
        return _skip(
            "S-V4",
            f"{len(referenced)} Problem(s) named; no lineage provider to "
            f"verify reachability",
        )
    reachable = ctx.lineage_problems(ctx.attributes.object_id)
    if reachable is None:
        return _skip("S-V4", "lineage not traversable for this object")

    stray = sorted(referenced - set(reachable))
    if stray:
        return _fail(
            "S-V4",
            f"problem_fit_rationale cites Problems outside this Solution's "
            f"lineage: {stray}; the fit is asserted, not demonstrated",
        )
    return _ok(
        "S-V4", f"{len(referenced)} Problem(s) cited, all reachable in lineage"
    )


def sv5_not_an_opportunity_restatement(ctx: AcceptanceContext) -> RuleResult:
    """solution_statement is not a restatement of the Opportunity. [S-V5]

    A restatement performs no transformation: it advances nothing and leaves
    Validation with the Opportunity's own wording to test. Comparison ignores
    case, spacing and punctuation only; semantic paraphrase is not claimed to
    be caught.
    """
    if ctx.attributes.object_type is not ObjectType.SOLUTION:
        return _skip("S-V5", "not a Solution")
    solution = _solution_of(ctx)
    if solution is None:
        return _skip("S-V5", "no Solution payload supplied")

    if not (solution.solution_statement or "").strip():
        return _fail(
            "S-V5",
            "solution_statement is absent; an unstated approach cannot be "
            "shown to transform the Opportunity",
        )

    statement_of = getattr(ctx, "opportunity_statement_text", None)
    if statement_of is None:
        return _skip(
            "S-V5",
            "no opportunity statement provider; textual restatement unchecked",
        )
    original = statement_of(solution.addresses_opportunity)
    if original is None:
        return _skip("S-V5", "opportunity statement unavailable")

    if _verbatim_form(original) == _verbatim_form(solution.solution_statement):
        return _fail(
            "S-V5",
            f"solution_statement restates opportunity "
            f"{solution.addresses_opportunity!r} verbatim; no transformation "
            f"was performed",
        )
    return _ok("S-V5", "statement differs from the Opportunity")


def sv6_feasibility_present(ctx: AcceptanceContext) -> RuleResult:
    """feasibility_assessment present. [S-V6]

    Presence only. Assessment AGAINST the constraint model is T07.2.6 and
    depends on M-69, which defines no constraint model yet.
    """
    if ctx.attributes.object_type is not ObjectType.SOLUTION:
        return _skip("S-V6", "not a Solution")
    solution = _solution_of(ctx)
    if solution is None:
        return _skip("S-V6", "no Solution payload supplied")

    if not (solution.feasibility_assessment or "").strip():
        return _fail(
            "S-V6",
            "feasibility_assessment is absent; validation effort would be "
            "spent on a possibly impossible approach",
        )
    return _ok(
        "S-V6", "feasibility stated; not assessed against constraints [M-69]"
    )


sv1_opportunity_resolves_and_is_active.rule_id = "S-V1"   # type: ignore[attr-defined]
sv2_assumptions_present.rule_id = "S-V2"                  # type: ignore[attr-defined]
sv3_assumptions_are_testable.rule_id = "S-V3"             # type: ignore[attr-defined]
sv4_problem_fit_references_lineage.rule_id = "S-V4"       # type: ignore[attr-defined]
sv5_not_an_opportunity_restatement.rule_id = "S-V5"       # type: ignore[attr-defined]
sv6_feasibility_present.rule_id = "S-V6"                  # type: ignore[attr-defined]

SOLUTION_RULES = (
    sv1_opportunity_resolves_and_is_active,
    sv2_assumptions_present,
    sv3_assumptions_are_testable,
    sv4_problem_fit_references_lineage,
    sv5_not_an_opportunity_restatement,
    sv6_feasibility_present,
)


# ---------------------------------------------------------------------------
# Solution integrity constraints  [S-I1 .. S-I4]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SolutionViolation:
    """A breached Solution integrity constraint."""

    constraint_id: str
    object_id: str
    detail: str


@dataclass
class SolutionIntegrity:
    """Continuous verification of S-I1..S-I4. [IOM section 3.6]

    Detective, mirroring the earlier type verifiers. S-I4 in particular
    cannot be a write-time check: whether a Solution altered its Opportunity's
    assessment is only observable by comparing that assessment over time.
    """

    solution_of: Callable[[str], "Solution | None"]
    store: "object"
    _opportunity_assessments: dict[str, tuple] = field(
        default_factory=dict, init=False
    )

    def verify(self) -> tuple[SolutionViolation, ...]:
        violations: list[SolutionViolation] = []
        violations.extend(self._check_si1())
        violations.extend(self._check_si2())
        violations.extend(self._check_si3())
        violations.extend(self._check_si4())
        return tuple(violations)

    def _all_solutions(self) -> Iterable[tuple[str, "Solution"]]:
        for stored in self.store.objects_of_type(ObjectType.SOLUTION):
            solution = self.solution_of(stored.object_id)
            if solution is not None:
                yield stored.object_id, solution

    def _by_lineage(self) -> dict[str, list[tuple[int, str, "Solution"]]]:
        grouped: dict[str, list[tuple[int, str, "Solution"]]] = {}
        for object_id, solution in self._all_solutions():
            grouped.setdefault(solution.lineage_id, []).append(
                (solution.attributes.version, object_id, solution)
            )
        for versions in grouped.values():
            versions.sort(key=lambda item: item[0])
        return grouped

    # -- S-I4 support -----------------------------------------------------

    def record_opportunity_assessment(self, solution: "Solution") -> None:
        """Snapshot the Opportunity's assessment when a Solution attaches.

        S-I4 says a Solution never modifies its Opportunity's assessment.
        Detecting that requires knowing what the assessment was at the moment
        the Solution was accepted, so it is recorded then and compared later.
        """
        assessment = self._assessment_of(solution.addresses_opportunity)
        if assessment is not None:
            self._opportunity_assessments.setdefault(
                solution.addresses_opportunity, assessment
            )

    def _assessment_of(self, opportunity_ref: str) -> tuple | None:
        stored = self.store.find(opportunity_ref)
        if stored is None or stored.object_type is not ObjectType.OPPORTUNITY:
            return None
        confidence = stored.attributes.confidence
        registry = getattr(self.store, "opportunities", None)
        payload = registry.get(opportunity_ref) if registry is not None else None
        fingerprint = (
            payload.score_fingerprint() if payload is not None else None
        )
        return (
            round(confidence.effective_confidence, 12),
            round(confidence.evidential_support, 12),
            round(confidence.assertion_confidence, 12),
            fingerprint,
        )

    @property
    def recorded_assessment_count(self) -> int:
        return len(self._opportunity_assessments)

    def _check_si1(self) -> list[SolutionViolation]:
        """Assumptions never removed, only superseded with rationale. [S-I1]

        Checked across a supersession chain. A dropped assumption is
        permitted only where the later version records why it was withdrawn;
        an unexplained drop is indistinguishable from concealment.
        """
        violations: list[SolutionViolation] = []
        for versions in self._by_lineage().values():
            for (_, _, earlier), (_, later_id, later) in zip(
                versions, versions[1:]
            ):
                dropped = later.retains_assumptions_of(earlier)
                if dropped:
                    violations.append(
                        SolutionViolation(
                            "S-I1", later_id,
                            f"assumptions removed without rationale: "
                            f"{list(dropped)}; assumptions are superseded, "
                            f"never removed",
                        )
                    )
        return violations

    def _check_si2(self) -> list[SolutionViolation]:
        """Demonstrably addresses the Problems beneath its Opportunity. [S-I2]

        Every cited Problem must still be reachable upstream. Read from the
        derived index, so an unindexed Solution yields no verdict rather than
        a false one. [N-6]
        """
        violations: list[SolutionViolation] = []
        graph = getattr(self.store, "graph", None)
        if graph is None:
            return violations
        for object_id, solution in self._all_solutions():
            if not graph.contains(object_id):
                continue
            reachable = {
                ancestor
                for ancestor in graph.ancestors(object_id)
                if graph.type_of(ancestor) is ObjectType.PROBLEM
            }
            stray = sorted(solution.addressed_problems - reachable)
            if stray:
                violations.append(
                    SolutionViolation(
                        "S-I2", object_id,
                        f"claims to address {stray}, which are not beneath its "
                        f"Opportunity; lineage is intact but semantically "
                        f"empty",
                    )
                )
        return violations

    def _check_si3(self) -> list[SolutionViolation]:
        """Sibling candidates never silently collapsed. [S-I3]

        Competing candidates coexisting is expected, not exceptional, and
        premature convergence removes the comparison Validation depends on.

        The mechanical check is candidate_group STABILITY across a
        supersession chain, mirroring V11's object_type stability. A version
        that changes its group silently removes a candidate from the original
        comparison: the group looks converged when nothing was decided, and
        no other rule would notice. Deletion is already impossible under I4,
        and a missing withdrawal reason is already impossible under V9, so
        neither is re-checked here.
        """
        violations: list[SolutionViolation] = []
        for versions in self._by_lineage().values():
            for (_, _, earlier), (_, later_id, later) in zip(
                versions, versions[1:]
            ):
                if later.candidate_group != earlier.candidate_group:
                    violations.append(
                        SolutionViolation(
                            "S-I3", later_id,
                            f"candidate_group changed across versions: "
                            f"{earlier.candidate_group!r} -> "
                            f"{later.candidate_group!r}; the original group "
                            f"silently loses a candidate and appears to have "
                            f"converged",
                        )
                    )
                if later.addresses_opportunity != earlier.addresses_opportunity:
                    violations.append(
                        SolutionViolation(
                            "S-I3", later_id,
                            f"addressed opportunity changed across versions: "
                            f"{earlier.addresses_opportunity!r} -> "
                            f"{later.addresses_opportunity!r}; a candidate "
                            f"cannot migrate between comparisons",
                        )
                    )
        return violations

    def _check_si4(self) -> list[SolutionViolation]:
        """Never modifies its Opportunity's assessment. [S-I4]

        Compares each addressed Opportunity's assessment against the snapshot
        taken when the Solution attached. The Solution stage answers for
        whether an approach fits; it has no basis to revise the value
        judgement above it, and doing so would let the two accountabilities
        the object model separates leak back together.
        """
        violations: list[SolutionViolation] = []
        seen: set[str] = set()
        for object_id, solution in self._all_solutions():
            ref = solution.addresses_opportunity
            recorded = self._opportunity_assessments.get(ref)
            if recorded is None or ref in seen:
                continue
            seen.add(ref)
            current = self._assessment_of(ref)
            if current is None:
                violations.append(
                    SolutionViolation(
                        "S-I4", object_id,
                        f"addressed opportunity {ref!r} is no longer "
                        f"retrievable; its assessment cannot be shown intact",
                    )
                )
            elif current != recorded:
                violations.append(
                    SolutionViolation(
                        "S-I4", object_id,
                        f"opportunity {ref!r} assessment changed after this "
                        f"Solution attached: recorded {recorded}, now "
                        f"{current}. A Solution never revises the value "
                        f"judgement above it",
                    )
                )
        return violations


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass
class SolutionRegistry:
    """Holds Solution payloads and groups competing candidates. [S-I3]

    Mirrors the earlier registries. Selection among candidates is absent:
    gate ownership is unassigned under M-31, and Validation reports rather
    than gates.
    """

    store: "object"
    _payloads: dict[str, Solution] = field(default_factory=dict, init=False)
    _integrity: "SolutionIntegrity | None" = field(default=None, init=False)

    def register(self, solution: Solution) -> Solution:
        self._payloads[solution.object_id] = solution
        self.integrity().record_opportunity_assessment(solution)
        return solution

    def get(self, object_id: str) -> Solution | None:
        return self._payloads.get(object_id)

    def active_solutions(self) -> tuple[Solution, ...]:
        found = []
        for object_id, solution in self._payloads.items():
            stored = self.store.find(object_id)
            if stored is not None and stored.status is ObjectStatus.ACTIVE:
                found.append(solution)
        return tuple(found)

    def candidates_for(self, opportunity_ref: str) -> tuple[Solution, ...]:
        """Every candidate addressing one Opportunity. [S-I3]"""
        return tuple(
            s for s in self._payloads.values()
            if s.addresses_opportunity == opportunity_ref
        )

    def candidate_group(self, group: str) -> tuple[Solution, ...]:
        """Competing candidates sharing a group identifier. [S-I3]"""
        return tuple(
            s for s in self._payloads.values() if s.candidate_group == group
        )

    def siblings_of(self, object_id: str) -> tuple[Solution, ...]:
        """Competing candidates other than this one. [S-I3]"""
        solution = self._payloads.get(object_id)
        if solution is None:
            return ()
        return tuple(
            s for s in self._payloads.values() if solution.is_sibling_of(s)
        )

    def testable_surface(self, object_id: str) -> tuple[Assumption, ...]:
        """The assumptions Validation may TEST individually. [S-V2, S-V3]"""
        solution = self._payloads.get(object_id)
        return solution.assumptions if solution is not None else ()

    def integrity(self) -> SolutionIntegrity:
        if self._integrity is None:
            self._integrity = SolutionIntegrity(
                solution_of=self.get, store=self.store
            )
        return self._integrity

    def __len__(self) -> int:
        return len(self._payloads)
