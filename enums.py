"""Closed vocabularies for the object contract.

Task: T01.1.2

Architecture References:
- R-2   Seven-state object lifecycle
- R-3   Two-component confidence with five bands
- R-6   Closed ten-type relationship taxonomy
- R-7   Feedback Record is the ninth Intelligence Object
- AD-02 Intelligence Objects are the sole inter-engine contract
- IOM   sections 2.1, 2.3, 2.5, 2.6, 3

Every vocabulary here is CLOSED. Extension requires a superseding decision
record, never an inline addition.
"""

from __future__ import annotations

from enum import Enum


class ObjectType(str, Enum):
    """The nine Intelligence Object types. [R-7, IOM section 2.6]"""

    EVIDENCE = "Evidence"
    FACT = "Fact"
    PROBLEM = "Problem"
    PATTERN = "Pattern"
    OPPORTUNITY = "Opportunity"
    SOLUTION = "Solution"
    VALIDATION = "Validation"
    EXECUTION_RECORD = "ExecutionRecord"
    FEEDBACK_RECORD = "FeedbackRecord"

    @property
    def is_root(self) -> bool:
        """Evidence is the only type permitted empty lineage. [E-V1, V2]"""
        return self is ObjectType.EVIDENCE

    @property
    def stage(self) -> int:
        """Owning pipeline stage, 1-9. [IOM section 2.6]"""
        return _STAGE_BY_TYPE[self]


_STAGE_BY_TYPE: dict[ObjectType, int] = {
    ObjectType.EVIDENCE: 1,
    ObjectType.FACT: 2,
    ObjectType.PROBLEM: 3,
    ObjectType.PATTERN: 4,
    ObjectType.OPPORTUNITY: 5,
    ObjectType.SOLUTION: 6,
    ObjectType.VALIDATION: 7,
    ObjectType.EXECUTION_RECORD: 8,
    ObjectType.FEEDBACK_RECORD: 9,
}


class Engine(str, Enum):
    """The nine engines. [AD-04, IOM section 2.5]"""

    RESEARCH = "Research"
    FACT_EXTRACTION = "FactExtraction"
    PROBLEM_INTELLIGENCE = "ProblemIntelligence"
    PATTERN_INTELLIGENCE = "PatternIntelligence"
    OPPORTUNITY_INTELLIGENCE = "OpportunityIntelligence"
    SOLUTION_INTELLIGENCE = "SolutionIntelligence"
    VALIDATION = "Validation"
    FEEDBACK = "Feedback"
    ORCHESTRATION = "Orchestration"


class ObjectStatus(str, Enum):
    """The seven lifecycle states. [R-2]"""

    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"
    RETRACTED = "RETRACTED"
    INVALIDATED = "INVALIDATED"
    ARCHIVED = "ARCHIVED"

    @property
    def is_terminal(self) -> bool:
        """Terminal states may never transition. [R-2]"""
        return self in _TERMINAL_STATES

    @property
    def requires_reason(self) -> bool:
        """status_reason required for all non-ACTIVE states. [V9]"""
        return self is not ObjectStatus.ACTIVE


_TERMINAL_STATES = frozenset(
    {
        ObjectStatus.SUPERSEDED,
        ObjectStatus.REJECTED,
        ObjectStatus.RETRACTED,
        ObjectStatus.INVALIDATED,
        ObjectStatus.ARCHIVED,
    }
)


class ConfidenceBand(str, Enum):
    """Mandatory band labels preventing false precision. [R-3, S-1]"""

    NEGLIGIBLE = "NEGLIGIBLE"
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"

    @classmethod
    def for_value(cls, value: float) -> "ConfidenceBand":
        """Map a 0.00-1.00 value to its band. [R-3]"""
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {value}")
        if value < 0.20:
            return cls.NEGLIGIBLE
        if value < 0.40:
            return cls.WEAK
        if value < 0.60:
            return cls.MODERATE
        if value < 0.80:
            return cls.STRONG
        return cls.VERY_STRONG


class RelationshipType(str, Enum):
    """The closed ten-type relationship taxonomy. [R-6]

    Engines may not invent relationships. Extension requires superseding R-6.
    """

    DERIVES_FROM = "DERIVES_FROM"
    SUPPORTS = "SUPPORTS"
    CONSTITUENT_OF = "CONSTITUENT_OF"
    ADDRESSES = "ADDRESSES"
    TESTS = "TESTS"
    OUTCOME_OF = "OUTCOME_OF"
    SUPERSEDES = "SUPERSEDES"
    DUPLICATES = "DUPLICATES"
    CONTRADICTS = "CONTRADICTS"
    INFORMS = "INFORMS"


# Create authority: exactly one engine per object type. [IOM section 2.5]
# ExecutionRecord is deliberately absent -- C-02 remains open, no engine holds
# create authority for it. Resolution is scheduled at T08.1.1.
CREATE_AUTHORITY: dict[ObjectType, Engine] = {
    ObjectType.EVIDENCE: Engine.RESEARCH,
    ObjectType.FACT: Engine.FACT_EXTRACTION,
    ObjectType.PROBLEM: Engine.PROBLEM_INTELLIGENCE,
    ObjectType.PATTERN: Engine.PATTERN_INTELLIGENCE,
    ObjectType.OPPORTUNITY: Engine.OPPORTUNITY_INTELLIGENCE,
    ObjectType.SOLUTION: Engine.SOLUTION_INTELLIGENCE,
    ObjectType.VALIDATION: Engine.VALIDATION,
    ObjectType.FEEDBACK_RECORD: Engine.FEEDBACK,
}


# Owning pipeline stage per engine, 1-9. [IOM section 2.6]
# Orchestration is deliberately absent: it owns no stage and produces no
# object -- it is cross-cutting, not pipeline-aligned (IOM section 4.6).
# Stage 8 (Execution Record) has no owning engine, so no engine maps to it;
# C-02 remains open and no producer may be invented. A stage-8 work item is
# therefore classifiable only by the object type it produces.
ENGINE_STAGE: dict[Engine, int] = {
    Engine.RESEARCH: 1,
    Engine.FACT_EXTRACTION: 2,
    Engine.PROBLEM_INTELLIGENCE: 3,
    Engine.PATTERN_INTELLIGENCE: 4,
    Engine.OPPORTUNITY_INTELLIGENCE: 5,
    Engine.SOLUTION_INTELLIGENCE: 6,
    Engine.VALIDATION: 7,
    Engine.FEEDBACK: 9,
}

# The N-11 boundary, quoted from the decision's own table:
#
#   | 1 Evidence, 2 Facts   | Concurrent -- operations are independent per source |
#   | 3 Problems ... 9 Feedback | Serialised -- one batch at a time              |
#
# The line falls between stage 2 and stage 3 and nowhere else. [N-11]
CONCURRENT_STAGES: frozenset[int] = frozenset({1, 2})
SERIALISED_STAGES: frozenset[int] = frozenset({3, 4, 5, 6, 7, 8, 9})


# The object type each engine consumes as its DIRECT input. [N-14]
#
# Quoted from N-14's table ("Engine | Direct input"):
#     Fact Extraction        <- Evidence
#     Problem Intelligence   <- Facts
#     Pattern Intelligence   <- Problems
#     Opportunity Intelligence <- Patterns
#     Solution Intelligence  <- Opportunities
#     Validation             <- Solutions
#     Feedback               <- Execution Records
#
# RESEARCH is deliberately absent: N-14 gives it no direct input, and Evidence
# is the pipeline root whose derives_from must be empty (E-V1, V2). Research
# therefore has no input to wait for.
#
# ORCHESTRATION is deliberately absent: it consumes no object type and creates
# none (IOM 4.6). It is cross-cutting, not pipeline-aligned.
#
# Feedback's input type is ExecutionRecord even though no engine produces one
# -- C-02 remains open. The dependency is expressible by type; the producer is
# not, and none is invented here.
ENGINE_INPUT_TYPE: dict[Engine, ObjectType] = {
    Engine.FACT_EXTRACTION: ObjectType.EVIDENCE,
    Engine.PROBLEM_INTELLIGENCE: ObjectType.FACT,
    Engine.PATTERN_INTELLIGENCE: ObjectType.PROBLEM,
    Engine.OPPORTUNITY_INTELLIGENCE: ObjectType.PATTERN,
    Engine.SOLUTION_INTELLIGENCE: ObjectType.OPPORTUNITY,
    Engine.VALIDATION: ObjectType.SOLUTION,
    Engine.FEEDBACK: ObjectType.EXECUTION_RECORD,
}

# Engines that require no input to exist before they may run. [N-14, E-V1]
# Exactly one: Research acquires from external reality, not from the platform.
ROOT_ENGINES: frozenset[Engine] = frozenset({Engine.RESEARCH})
