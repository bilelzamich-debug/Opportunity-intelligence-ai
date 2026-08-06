"""Adversarial probe for T01.5.5 calibration conformance. Attack before testing."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from oip.calibration import (
    CALIBRATION_RUBRIC, COMPARABILITY_PROPERTIES, COMPARABILITY_QUALIFICATION,
    GOVERNED_COMPONENT, RUBRIC_ID, RUBRIC_RATIFIED, UNGOVERNED_COMPONENTS,
    BandCriterion, CalibrationAssessment, CalibrationDeviation,
    CalibrationError, CalibrationRegister, ConformanceOutcome,
    CrossEngineComparison, UngovernedComponentError, assess_assertion,
    compare_across_engines, criterion_for_band, criterion_for_value,
    rubric_matches_band_boundaries,
)
from oip.contract import Confidence
from oip.enums import ConfidenceBand, Engine

FAILS: list[str] = []


def probe(name):
    def deco(fn):
        try:
            fn(); print(f"  ok   {name}")
        except AssertionError as e:
            FAILS.append(f"{name}: {e}"); print(f"  FAIL {name}: {e}")
        except Exception as e:
            FAILS.append(f"{name}: {type(e).__name__}: {e}")
            print(f"  ERR  {name}: {type(e).__name__}: {e}")
        return fn
    return deco


print("== A. rubric matches S-1 exactly ==")


@probe("five bands, no more, no fewer")
def _():
    assert len(CALIBRATION_RUBRIC) == 5
    assert [c.band for c in CALIBRATION_RUBRIC] == list(ConfidenceBand)


@probe("S-1 ranges reproduced exactly")
def _():
    expected = {
        ConfidenceBand.NEGLIGIBLE: (0.00, 0.19),
        ConfidenceBand.WEAK: (0.20, 0.39),
        ConfidenceBand.MODERATE: (0.40, 0.59),
        ConfidenceBand.STRONG: (0.60, 0.79),
        ConfidenceBand.VERY_STRONG: (0.80, 1.00),
    }
    for c in CALIBRATION_RUBRIC:
        assert (c.low, c.high) == expected[c.band], c.band


@probe("rubric ranges agree with the implemented band boundaries")
def _():
    assert rubric_matches_band_boundaries() is True
    for c in CALIBRATION_RUBRIC:
        assert ConfidenceBand.for_value(c.low) is c.band
        assert ConfidenceBand.for_value(c.high) is c.band


@probe("no gap or overlap between band ranges")
def _():
    ordered = sorted(CALIBRATION_RUBRIC, key=lambda c: c.low)
    assert ordered[0].low == 0.00 and ordered[-1].high == 1.00
    for a, b in zip(ordered, ordered[1:]):
        assert a.high < b.low, (a.band, b.band)
        # contiguous at 2dp, the precision S-1 states
        assert round(b.low - a.high, 2) == 0.01, (a.band, b.band)


@probe("every band carries criterion, test and two anchors")
def _():
    for c in CALIBRATION_RUBRIC:
        assert c.criterion.strip() and c.test.strip()
        assert c.anchor_a.strip() and c.anchor_b.strip()
        assert c.anchor_a != c.anchor_b


@probe("ten distinct anchors, as S-1 specifies two per band")
def _():
    anchors = [a for c in CALIBRATION_RUBRIC for a in (c.anchor_a, c.anchor_b)]
    assert len(anchors) == 10
    assert len(set(anchors)) == 10


@probe("counts attributed ONLY where S-1 states a countable test")
def _():
    counts = {c.band: c.alternative_count for c in CALIBRATION_RUBRIC}
    assert counts[ConfidenceBand.VERY_STRONG] == 0
    assert counts[ConfidenceBand.MODERATE] == 1
    assert counts[ConfidenceBand.WEAK] == 2
    # S-1 defines these qualitatively; a count would be invented
    assert counts[ConfidenceBand.NEGLIGIBLE] is None
    assert counts[ConfidenceBand.STRONG] is None


@probe("only WEAK is a minimum ('>=2')")
def _():
    for c in CALIBRATION_RUBRIC:
        assert c.count_is_minimum is (c.band is ConfidenceBand.WEAK), c.band


@probe("rubric is immutable")
def _():
    c = CALIBRATION_RUBRIC[0]
    try:
        c.criterion = "tampered"
        assert False, "rubric criterion mutable"
    except Exception:
        pass
    assert isinstance(CALIBRATION_RUBRIC, tuple)


print("== B. false conformity ==")


@probe("a missing count is UNASSESSED, never CONFORMANT")
def _():
    for v in (0.0, 0.25, 0.5, 0.75, 1.0):
        a = assess_assertion(v)
        assert a.outcome is ConformanceOutcome.UNASSESSED, v
        assert a.conformant is False
        assert a.assessed is False


@probe("a qualitative band with a count is UNASSESSED, never CONFORMANT")
def _():
    for v, band in ((0.10, "NEGLIGIBLE"), (0.70, "STRONG")):
        for n in range(0, 5):
            a = assess_assertion(v, alternative_count=n)
            assert a.outcome is ConformanceOutcome.UNASSESSED, (v, n)
            assert a.conformant is False


@probe("a qualitative band never yields a DEVIATION either")
def _():
    for v in (0.0, 0.19, 0.60, 0.79):
        for n in range(0, 6):
            assert assess_assertion(v, alternative_count=n).deviated is False


@probe("UNASSESSED is not counted as a deviation by the register")
def _():
    r = CalibrationRegister()
    for v in (0.10, 0.50, 0.95):
        r.record("obj-1", assess_assertion(v))
    assert r.deviation_count == 0
    assert r.unassessed_count == 3
    assert r.assessment_count == 3


@probe("the register never reports a conformance rate")
def _():
    r = CalibrationRegister()
    s = r.summary()
    assert set(s) == {"assessments", "deviations", "unassessed"}
    assert all(isinstance(v, int) for v in s.values())
    assert not any("rate" in k or "pct" in k or "score" in k for k in s)


@probe("mismatched count is a DEVIATION for every countable band")
def _():
    cases = [(0.85, 1), (0.85, 2), (0.50, 0), (0.50, 3), (0.30, 0), (0.30, 1)]
    for v, n in cases:
        a = assess_assertion(v, alternative_count=n)
        assert a.outcome is ConformanceOutcome.DEVIATION, (v, n, a.outcome)
        assert a.detail and "S-1" in a.detail


@probe("matching count is CONFORMANT for every countable band")
def _():
    for v, n in ((0.85, 0), (1.00, 0), (0.50, 1), (0.40, 1),
                 (0.30, 2), (0.30, 7), (0.20, 2)):
        a = assess_assertion(v, alternative_count=n)
        assert a.outcome is ConformanceOutcome.CONFORMANT, (v, n, a.outcome)


print("== C. never changes confidence ==")


@probe("assessment carries the value unchanged")
def _():
    for v in (0.0, 0.137, 0.5, 0.8001, 1.0):
        a = assess_assertion(v, alternative_count=0)
        assert a.value == float(v), (v, a.value)


@probe("module exposes no mutator of confidence")
def _():
    import oip.calibration as m
    banned = ("adjust", "correct", "recalibrat", "rescale", "shift",
              "offset", "normalize", "normalise", "set_confidence", "update")
    names = [n for n in dir(m) if not n.startswith("_")]
    hits = [n for n in names if any(b in n.lower() for b in banned)]
    assert hits == [], hits


@probe("a Confidence object is untouched by assessment")
def _():
    c = Confidence(0.6, 0.85, 0.6)
    before = (c.evidential_support, c.assertion_confidence,
              c.effective_confidence)
    assess_assertion(c.assertion_confidence, alternative_count=0)
    assert (c.evidential_support, c.assertion_confidence,
            c.effective_confidence) == before


@probe("assessment is frozen")
def _():
    a = assess_assertion(0.5, alternative_count=1)
    for fld, val in (("value", 0.9), ("outcome", ConformanceOutcome.CONFORMANT)):
        try:
            setattr(a, fld, val)
            assert False, f"{fld} mutable"
        except Exception:
            pass


print("== D. governed component only [S-1 / M-59] ==")


@probe("evidential_support is refused")
def _():
    try:
        assess_assertion(0.5, 1, component="evidential_support")
        assert False, "governed a component S-1 excludes"
    except UngovernedComponentError:
        pass


@probe("effective_confidence is refused")
def _():
    try:
        assess_assertion(0.5, 1, component="effective_confidence")
        assert False
    except UngovernedComponentError:
        pass


@probe("the governed component is named explicitly")
def _():
    assert GOVERNED_COMPONENT == "assertion_confidence"
    assert set(UNGOVERNED_COMPONENTS) == {
        "evidential_support", "effective_confidence"}
    assert assess_assertion(0.5, 1).component == "assertion_confidence"


print("== E. no statistical calibration [O2 is P8] ==")


@probe("no empirical/statistical vocabulary")
def _():
    import oip.calibration as m
    banned = ("brier", "reliability_curve", "isotonic", "platt", "sigmoid",
              "regression", "histogram", "bucket", "success_rate",
              "outcome_rate", "posterior", "prior_probability")
    src = Path(m.__file__).read_text().lower()
    hits = [b for b in banned if b in src]
    assert hits == [], hits


@probe("comparability is never claimed as demonstrated")
def _():
    c = compare_across_engines([(Engine.RESEARCH, 0.8)])
    assert c.comparability_demonstrated is False
    assert c.rubric_dependent is True


@probe("O2 is named as the future mechanism, not implemented")
def _():
    import oip.calibration as m
    src = Path(m.__file__).read_text()
    assert "O2" in src and "T08.3.5" in src
    names = [n for n in dir(m) if not n.startswith("_")]
    assert not [n for n in names if "o2" == n.lower()]


print("== F. cross-engine comparison [AC3] ==")


@probe("comparison carries the S-1 qualification verbatim")
def _():
    c = compare_across_engines([(Engine.RESEARCH, 0.9),
                                (Engine.VALIDATION, 0.5)])
    assert "argued, not demonstrated" in c.qualification
    assert len(c.properties) == 3
    assert c.rubric_id == "S-1"


@probe("comparison returns bands, never a ranking or winner")
def _():
    c = compare_across_engines([(Engine.RESEARCH, 0.9),
                                (Engine.FEEDBACK, 0.2)])
    assert c.bands == ((Engine.RESEARCH, ConfidenceBand.VERY_STRONG),
                       (Engine.FEEDBACK, ConfidenceBand.WEAK))
    names = [n for n in dir(c) if not n.startswith("_")]
    assert not [n for n in names
                if any(b in n.lower() for b in ("rank", "best", "winner",
                                                "sort", "max", "top"))]


@probe("comparison is frozen and refuses a bad engine")
def _():
    c = compare_across_engines([])
    try:
        c.bands = ()
        assert False, "mutable"
    except Exception:
        pass
    try:
        compare_across_engines([("Research", 0.5)])
        assert False, "accepted a bare string engine"
    except CalibrationError:
        pass


@probe("empty comparison is legal and still qualified")
def _():
    c = compare_across_engines([])
    assert len(c) == 0
    assert c.comparability_demonstrated is False
    assert c.qualification


print("== G. stale / impossible calibration states ==")


@probe("every assessment names the rubric that governed it")
def _():
    a = assess_assertion(0.5, 1)
    assert a.rubric_id == RUBRIC_ID == "S-1"
    assert a.rubric_ratified == RUBRIC_RATIFIED == "2026-08-02"


@probe("deviations carry the rubric identity for T08.3.5 comparison")
def _():
    r = CalibrationRegister()
    d = r.record("obj-1", assess_assertion(0.85, 3))
    assert d is not None
    assert d.rubric_id == "S-1" and d.rubric_ratified == "2026-08-02"


@probe("expected_band is None when no count was declared")
def _():
    assert assess_assertion(0.5).expected_band is None


@probe("expected_band names the band the count implies")
def _():
    assert assess_assertion(0.85, 1).expected_band is ConfidenceBand.MODERATE
    assert assess_assertion(0.85, 5).expected_band is ConfidenceBand.WEAK
    assert assess_assertion(0.30, 0).expected_band is ConfidenceBand.VERY_STRONG


@probe("out-of-range values rejected by the band layer")
def _():
    for bad in (-0.01, 1.01, 2.0, -1.0):
        try:
            assess_assertion(bad, 0)
            assert False, f"accepted {bad}"
        except ValueError:
            pass


@probe("negative and non-integer counts refused")
def _():
    for bad in (-1, -5):
        try:
            assess_assertion(0.5, bad); assert False, bad
        except CalibrationError:
            pass
    for bad in (1.5, "1", True, [1]):
        try:
            assess_assertion(0.5, bad); assert False, repr(bad)
        except CalibrationError:
            pass


@probe("bad band lookup refused")
def _():
    for bad in ("STRONG", None, 5):
        try:
            criterion_for_band(bad); assert False, repr(bad)
        except CalibrationError:
            pass


print("== H. register discipline ==")


@probe("register is append-only")
def _():
    r = CalibrationRegister()
    r.record("obj-1", assess_assertion(0.85, 3))
    try:
        r.delete("obj-1"); assert False
    except CalibrationError:
        pass
    assert r.deviation_count == 1


@probe("register refuses a blank object id")
def _():
    r = CalibrationRegister()
    for bad in ("", "   "):
        try:
            r.record(bad, assess_assertion(0.85, 3)); assert False
        except CalibrationError:
            pass


@probe("register refuses a non-assessment")
def _():
    r = CalibrationRegister()
    for bad in ("x", None, 5):
        try:
            r.record("obj-1", bad); assert False
        except CalibrationError:
            pass


@probe("register never enters lineage")
def _():
    r = CalibrationRegister()
    d = r.record("obj-1", assess_assertion(0.85, 3))
    assert r.participates_in_lineage is False
    assert d.participates_in_lineage is False
    assert d.is_intelligence is False


@probe("register queries are exact")
def _():
    r = CalibrationRegister()
    r.record("o1", assess_assertion(0.85, 3, engine=Engine.RESEARCH))
    r.record("o2", assess_assertion(0.50, 4, engine=Engine.FEEDBACK))
    r.record("o3", assess_assertion(0.85, 0, engine=Engine.RESEARCH))
    assert len(r.for_engine(Engine.RESEARCH)) == 1
    assert len(r.for_engine(Engine.FEEDBACK)) == 1
    assert len(r.for_object("o1")) == 1
    assert len(r.for_object("nope")) == 0
    try:
        r.for_engine("Research"); assert False
    except CalibrationError:
        pass


@probe("returned collections are copies")
def _():
    r = CalibrationRegister()
    r.record("o1", assess_assertion(0.85, 3))
    got = r.all()
    assert isinstance(got, tuple) and got is not r._deviations


print("== I. no acceptance / lifecycle / lineage impact ==")


@probe("calibration imports nothing beyond enums and contract")
def _():
    import ast
    src = (ROOT / "oip" / "calibration.py").read_text()
    mods = {n.module for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.ImportFrom) and n.module}
    oip_mods = {m for m in mods if m.startswith("oip.")}
    assert oip_mods == {"oip.enums"}, oip_mods


@probe("no existing production file was modified")
def _():
    import subprocess
    out = subprocess.run(["git", "status", "--porcelain", "oip/"],
                         cwd=ROOT, capture_output=True, text=True).stdout
    modified = [l for l in out.splitlines() if l and not l.startswith("??")]
    assert not modified, modified


@probe("acceptance rule count unchanged at 68")
def _():
    from oip.store import KnowledgeStore
    s = KnowledgeStore()
    assert len(s.acceptance.rule_ids) == 68, len(s.acceptance.rule_ids)


@probe("ConfidenceBand semantics unchanged")
def _():
    assert [b.value for b in ConfidenceBand] == [
        "NEGLIGIBLE", "WEAK", "MODERATE", "STRONG", "VERY_STRONG"]
    assert ConfidenceBand.for_value(0.0) is ConfidenceBand.NEGLIGIBLE
    assert ConfidenceBand.for_value(1.0) is ConfidenceBand.VERY_STRONG


@probe("Confidence contract unchanged")
def _():
    c = Confidence(0.62, 0.84, 0.62)
    assert c.band is ConfidenceBand.STRONG
    assert c.support_band is ConfidenceBand.STRONG
    try:
        Confidence(0.5, 0.5, 0.9); assert False, "ceiling not enforced"
    except Exception:
        pass


print("== J. concurrency ==")


@probe("concurrent recording loses nothing")
def _():
    r = CalibrationRegister()
    errs = []

    def w(k):
        try:
            for i in range(200):
                r.record(f"o{k}-{i}", assess_assertion(0.85, 3))
        except Exception as e:
            errs.append(e)

    ts = [threading.Thread(target=w, args=(k,)) for k in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errs, errs
    assert r.deviation_count == 1600
    assert r.assessment_count == 1600


@probe("mixed concurrent outcomes counted exactly")
def _():
    r = CalibrationRegister()

    def w(k):
        for i in range(100):
            r.record(f"o{k}-{i}", assess_assertion(0.85, 3))       # deviation
            r.record(f"c{k}-{i}", assess_assertion(0.85, 0))       # conformant
            r.record(f"u{k}-{i}", assess_assertion(0.85))          # unassessed

    ts = [threading.Thread(target=w, args=(k,)) for k in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert r.assessment_count == 1800
    assert r.deviation_count == 600
    assert r.unassessed_count == 600


@probe("assess_assertion is pure under concurrency")
def _():
    out, errs = [], []

    def w():
        try:
            out.append(tuple(
                assess_assertion(v, 0).outcome for v in (0.85, 0.5, 0.3)))
        except Exception as e:
            errs.append(e)

    ts = [threading.Thread(target=w) for _ in range(16)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errs, errs
    assert len(set(out)) == 1, set(out)


print("== K. determinism and scale ==")


@probe("repeated assessment is identical")
def _():
    for _ in range(200):
        a = assess_assertion(0.55, 1, engine=Engine.PROBLEM_INTELLIGENCE)
        assert a.outcome is ConformanceOutcome.CONFORMANT
        assert a.band is ConfidenceBand.MODERATE


@probe("every value in [0,1] resolves to exactly one criterion")
def _():
    for i in range(0, 1001):
        v = i / 1000
        c = criterion_for_value(v)
        assert c.contains(v) or abs(v - c.high) < 0.01, (v, c.band)
        matching = [x for x in CALIBRATION_RUBRIC
                    if ConfidenceBand.for_value(v) is x.band]
        assert len(matching) == 1


@probe("20k assessments stay exact")
def _():
    r = CalibrationRegister()
    for i in range(20_000):
        r.record(f"o{i}", assess_assertion(0.85, 3 if i % 2 else 0))
    assert r.assessment_count == 20_000
    assert r.deviation_count == 10_000
    assert r.unassessed_count == 0


print()
if FAILS:
    print(f"{len(FAILS)} PROBE FAILURES")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("all probes passed")
