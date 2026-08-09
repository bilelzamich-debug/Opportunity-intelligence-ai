"""Round 2: hidden drift, boundary semantics, float edges, S-1 fidelity."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent
sys.path.insert(0, str(ROOT))

from oip.calibration import (
    CALIBRATION_RUBRIC, COMPARABILITY_PROPERTIES, COMPARABILITY_QUALIFICATION,
    RUBRIC_ID, RUBRIC_RATIFIED, CalibrationError, CalibrationRegister,
    ConformanceOutcome, assess_assertion, compare_across_engines,
    criterion_for_value,
)
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


S1 = (DOCS / "decisions" / "S-01-calibration-rubric.md").read_text()


print("== L. fidelity to the S-1 document itself ==")


@probe("every criterion string appears verbatim in S-1")
def _():
    missing = [c.band.value for c in CALIBRATION_RUBRIC
               if c.criterion not in S1.replace("\n", " ")]
    assert missing == [], missing


@probe("every anchor appears verbatim in S-1")
def _():
    flat = " ".join(S1.split())
    missing = []
    for c in CALIBRATION_RUBRIC:
        for anchor in (c.anchor_a, c.anchor_b):
            if " ".join(anchor.split()) not in flat:
                missing.append((c.band.value, anchor[:40]))
    assert missing == [], missing


@probe("the qualification is S-1's own wording")
def _():
    assert "comparability is **argued, not demonstrated**" in S1
    assert "argued, not demonstrated" in COMPARABILITY_QUALIFICATION


@probe("S-1 is RATIFIED and closes M-60")
def _():
    assert "| **Status** | `RATIFIED` |" in S1
    assert "| **Closes** | M-60 |" in S1
    assert RUBRIC_ID == "S-1"
    assert RUBRIC_RATIFIED in S1


@probe("S-1 binds T01.5.5")
def _():
    assert "**`T01.5.5`** calibration conformance" in S1


@probe("S-1 restricts the rubric to assertion_confidence")
def _():
    assert "only `assertion_confidence` is governed by this rubric" in S1


@probe("the three comparability properties match S-1's count")
def _():
    assert len(COMPARABILITY_PROPERTIES) == 3
    assert "Comparability rests on three properties" in S1


@probe("S-1's countable tests are exactly the three implemented")
def _():
    # The literal test strings that contain a number/absence claim.
    assert "Are there ≥2 equally good alternative conclusions? *Yes.*" in S1
    assert "Is there exactly one credible alternative? *Yes.*" in S1
    assert "Can I construct any non-contradictory alternative? *No.*" in S1
    # And the two that do not.
    assert "Would I defend this if challenged? *No.*" in S1
    assert "Do alternatives need extra assumptions? *Yes.*" in S1
    countable = {c.band for c in CALIBRATION_RUBRIC if c.is_countable}
    assert countable == {ConfidenceBand.WEAK, ConfidenceBand.MODERATE,
                         ConfidenceBand.VERY_STRONG}


print("== M. boundary semantics ==")


@probe("exact band boundaries land in the right criterion")
def _():
    cases = [(0.19, "NEGLIGIBLE"), (0.20, "WEAK"), (0.39, "WEAK"),
             (0.40, "MODERATE"), (0.59, "MODERATE"), (0.60, "STRONG"),
             (0.79, "STRONG"), (0.80, "VERY_STRONG")]
    for v, expected in cases:
        assert criterion_for_value(v).band.value == expected, v


@probe("values between S-1's 2dp gridpoints still resolve")
def _():
    # S-1 states 0.00-0.19 then 0.20-...; 0.195 lies in the printed gap.
    for v in (0.195, 0.395, 0.595, 0.795):
        c = criterion_for_value(v)
        assert c is not None
        # must agree with the implemented boundary, not the printed range
        assert c.band is ConfidenceBand.for_value(v)


@probe("contains() agrees with the authoritative band, printed gaps included")
def _():
    # S-1 prints 0.00-0.19 then 0.20-...; 0.195 is in no printed range but is
    # plainly NEGLIGIBLE. contains() must not answer False for it.
    for v in (0.195, 0.199, 0.395, 0.599, 0.799):
        c = criterion_for_value(v)
        assert c.contains(v) is True, (v, c.band)
        assert c.band is ConfidenceBand.for_value(v)
    # and it must reject out-of-range values outright
    assert criterion_for_value(0.5).contains(1.5) is False
    assert criterion_for_value(0.5).contains(-0.1) is False


@probe("contains() is exclusive across bands")
def _():
    for i in range(0, 1001):
        v = i / 1000
        holding = [c for c in CALIBRATION_RUBRIC if c.contains(v)]
        assert len(holding) == 1, (v, [c.band for c in holding])


@probe("float noise near a boundary does not flip the criterion")
def _():
    import math
    for base in (0.2, 0.4, 0.6, 0.8):
        below = math.nextafter(base, 0.0)
        assert criterion_for_value(below).band is ConfidenceBand.for_value(below)
        assert criterion_for_value(base).band is ConfidenceBand.for_value(base)


@probe("0.0 and 1.0 are handled")
def _():
    assert criterion_for_value(0.0).band is ConfidenceBand.NEGLIGIBLE
    assert criterion_for_value(1.0).band is ConfidenceBand.VERY_STRONG
    assert assess_assertion(1.0, 0).outcome is ConformanceOutcome.CONFORMANT
    assert assess_assertion(0.0, 0).outcome is ConformanceOutcome.UNASSESSED


@probe("integer-valued confidence accepted like a float")
def _():
    a = assess_assertion(1, 0)
    assert a.value == 1.0 and isinstance(a.value, float)


print("== N. hidden calibration drift ==")


@probe("a huge alternative count still maps to WEAK, never off the scale")
def _():
    for n in (2, 10, 1000, 10**9):
        a = assess_assertion(0.30, n)
        assert a.outcome is ConformanceOutcome.CONFORMANT, n
        assert a.expected_band is ConfidenceBand.WEAK


@probe("count 0 never implies WEAK, count 2 never implies VERY_STRONG")
def _():
    assert assess_assertion(0.85, 0).expected_band is ConfidenceBand.VERY_STRONG
    assert assess_assertion(0.30, 2).expected_band is ConfidenceBand.WEAK
    assert assess_assertion(0.30, 0).expected_band is ConfidenceBand.VERY_STRONG


@probe("expected_band is unique for every count")
def _():
    for n in range(0, 20):
        matches = [c.band for c in CALIBRATION_RUBRIC if c.matches_count(n)]
        assert len(matches) == 1, (n, matches)


@probe("the rubric cannot be extended at runtime")
def _():
    import oip.calibration as m
    before = len(m.CALIBRATION_RUBRIC)
    try:
        m.CALIBRATION_RUBRIC.append(None)   # tuple -> no append
        assert False, "rubric extensible"
    except AttributeError:
        pass
    assert len(m.CALIBRATION_RUBRIC) == before


@probe("deviation detail always names the rubric")
def _():
    for v, n in ((0.85, 2), (0.50, 0), (0.30, 1)):
        a = assess_assertion(v, n)
        assert a.deviated and "S-1" in a.detail


@probe("assessment of the same input is byte-identical across calls")
def _():
    import dataclasses
    a = assess_assertion(0.55, 1, engine=Engine.VALIDATION)
    b = assess_assertion(0.55, 1, engine=Engine.VALIDATION)
    assert dataclasses.asdict(a) == dataclasses.asdict(b)


print("== O. register cannot overstate conformance ==")


@probe("summary counts never imply a pass rate")
def _():
    r = CalibrationRegister()
    r.record("a", assess_assertion(0.85, 0))     # conformant
    r.record("b", assess_assertion(0.85, 2))     # deviation
    r.record("c", assess_assertion(0.85))        # unassessed
    s = r.summary()
    assert s == {"assessments": 3, "deviations": 1, "unassessed": 1}
    # conformant count is NOT reported as a rate or a score
    assert "conformance_rate" not in s and "score" not in s


@probe("unassessed cannot be mistaken for conformant in the totals")
def _():
    r = CalibrationRegister()
    for _ in range(50):
        r.record("x", assess_assertion(0.70, 1))   # qualitative -> unassessed
    s = r.summary()
    assert s["unassessed"] == 50
    assert s["deviations"] == 0
    assert s["assessments"] == 50


@probe("recording a conformant assessment returns None, not a deviation")
def _():
    r = CalibrationRegister()
    assert r.record("a", assess_assertion(0.85, 0)) is None
    assert r.deviation_count == 0


@probe("register len equals deviation count, not assessment count")
def _():
    r = CalibrationRegister()
    r.record("a", assess_assertion(0.85, 0))
    r.record("b", assess_assertion(0.85, 2))
    assert len(r) == 1 and r.assessment_count == 2


print("== P. cross-engine comparison cannot be over-read ==")


@probe("identical numbers from different engines are not asserted equal")
def _():
    c = compare_across_engines([(Engine.RESEARCH, 0.7),
                                (Engine.PATTERN_INTELLIGENCE, 0.7)])
    assert c.comparability_demonstrated is False
    # bands agree, but the object refuses to claim the assertions are equal
    assert not hasattr(c, "equivalent")
    assert not hasattr(c, "agree")


@probe("all nine engines can be compared")
def _():
    c = compare_across_engines([(e, 0.5) for e in Engine])
    assert len(c) == 9
    assert set(c.engines) == set(Engine)


@probe("comparison rejects an out-of-range value")
def _():
    try:
        compare_across_engines([(Engine.RESEARCH, 1.5)])
        assert False
    except ValueError:
        pass


@probe("duplicate engines preserved, not silently collapsed")
def _():
    c = compare_across_engines([(Engine.RESEARCH, 0.9),
                                (Engine.RESEARCH, 0.1)])
    assert len(c) == 2, "a caller's data was silently deduplicated"


print("== Q. thread safety of the register internals ==")


@probe("concurrent reads during writes never see a torn tuple")
def _():
    r = CalibrationRegister()
    stop = threading.Event()
    errs = []

    def reader():
        while not stop.is_set():
            try:
                got = r.all()
                assert all(d.rubric_id == "S-1" for d in got)
            except Exception as e:
                errs.append(e); return

    t = threading.Thread(target=reader); t.start()
    for i in range(2000):
        r.record(f"o{i}", assess_assertion(0.85, 2))
    stop.set(); t.join()
    assert not errs, errs
    assert r.deviation_count == 2000


@probe("summary is internally consistent under contention")
def _():
    r = CalibrationRegister()

    def w(k):
        for i in range(300):
            r.record(f"{k}-{i}", assess_assertion(0.85, 2))

    ts = [threading.Thread(target=w, args=(k,)) for k in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    s = r.summary()
    assert s["assessments"] == 1800 == s["deviations"]
    assert s["unassessed"] == 0
    assert len(r.all()) == 1800


print()
if FAILS:
    print(f"{len(FAILS)} PROBE FAILURES")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("all round-2 probes passed")
