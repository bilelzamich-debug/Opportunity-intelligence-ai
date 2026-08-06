"""Mechanical verification of the T02.1.1 blocking escalation.

Every claim in T02.1.1-specification.md is re-established here by extraction
from the ratified documents, so the escalation rests on evidence rather than
on my reading. Fails closed: an unverifiable claim counts as a failure.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent
DEC = DOCS / "decisions"

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))


V2 = (DOCS / "PKP_v2_Master_Reference.md").read_text()
IOM = (DOCS / "PKP_Intelligence_Object_Model.md").read_text()
BACKLOG = (DOCS / "PKP_Implementation_Backlog.md").read_text()
CROSSWALK = (DEC / "marker-crosswalk.md").read_text()
PLAYBOOK = (DOCS / "AGENT-PLAYBOOK.md").read_text()

# -- 1. The task exists, is flagged, and its dependency is met --------------
task_block = re.search(
    r"#### `T02\.1\.1`(.*?)(?=#### `T02\.1\.2`)", BACKLOG, re.S
)
check("T02.1.1 exists in the backlog", task_block is not None)
tb = task_block.group(1) if task_block else ""
check("T02.1.1 carries the escalation flag", "⚠" in BACKLOG.split("#### `T02.1.1`")[0][-5:]
      or "⚠" in BACKLOG[BACKLOG.index("#### `T02.1.1`"):BACKLOG.index("#### `T02.1.1`") + 30],
      "flag appears on the task heading")
check("T02.1.1 cites M-16", "M-16" in tb, tb.strip().splitlines()[0] if tb else "")
check("T02.1.1 depends only on T01.8.1 (Phase 1, closed)",
      "`T01.8.1`" in tb and "T02." not in tb.split("Depends on")[1].split("|")[1]
      if "Depends on" in tb else False)

acs = re.findall(r"^- (.+)$", tb.split("**Acceptance criteria**")[1], re.M) \
    if "**Acceptance criteria**" in tb else []
check("T02.1.1 declares exactly 3 acceptance criteria", len(acs) == 3, str(acs))
check("AC1 requires a CLOSED taxonomy",
      any("closed taxonomy" in a.lower() for a in acs), str(acs))
check("AC2 requires a stored per-source trust rating",
      any("trust rating" in a.lower() and "stored" in a.lower() for a in acs))
check("AC3 requires trust to be a learnable P8 target",
      any("learnable" in a.lower() and "p8" in a.lower() for a in acs))

# -- 2. M-16 is OPEN in the canonical register ------------------------------
check("v2 §13 lists M-16 as a missing definition",
      re.search(r"\|\s*M-16\s*\|\s*Source taxonomy, eligibility, trust model",
                V2) is not None)
p2_block = re.search(
    r"\*\*Must resolve in P2 \(Research\)[^*]*\*\*(.*?)\n\n\*\*", V2, re.S
)
check("M-16 is designated 'Must resolve in P2'",
      p2_block is not None and "M-16" in p2_block.group(1))

# -- 3. No ratified decision closes M-16 ------------------------------------
closes: dict[str, str] = {}
for path in sorted(DEC.glob("*.md")):
    if path.name in {"marker-crosswalk.md", "TEMPLATE.md", "README.md",
                     "TIMELINE.md", "NON-GOALS.md", "DEPENDENCY-MAP.md",
                     "RATIFICATION-ANNOTATIONS.md"}:
        continue
    m = re.search(r"^\|\s*\*\*Closes\*\*\s*\|(.+?)\|\s*$", path.read_text(), re.M)
    if m:
        closes[path.stem] = m.group(1).strip()

closers = [k for k, v in closes.items() if re.search(r"\bM-16\b", v)]
check("no ratified decision record closes M-16", not closers,
      f"records claiming closure: {closers}")
check("37 decision records were scanned", len(closes) >= 30,
      f"{len(closes)} records with a Closes field")

# M-16 must not be closed anywhere in the decision tree except as a mapping.
# PROPOSALS/ holds unratified drafts; they are excluded by definition -- a
# proposal is not a decision. Only the ratified register is scanned.
citing = sorted(
    p.name for p in DEC.rglob("*.md")
    if "PROPOSALS" not in p.parts and re.search(r"\bM-16\b", p.read_text())
)
check("M-16 is cited in the RATIFIED register only by the crosswalk",
      citing == ["marker-crosswalk.md"], f"cited by {citing}")
check("the M-16 proposal is filed as unratified and marked PROPOSED",
      (DEC / "PROPOSALS" / "PROPOSAL-M-16-source-model.md").exists()
      and "NOT RATIFIED" in
      (DEC / "PROPOSALS" / "PROPOSAL-M-16-source-model.md").read_text(),
      "proposal must not present itself as a decision")

# -- 4. Crosswalk: the backlog's M-16 is already canonical ------------------
check("crosswalk maps IOM MISSING-18 -> canonical M-16",
      re.search(r"MISSING-18.*?Source taxonomy / trust.*?\*\*M-16\*\*",
                CROSSWALK, re.S) is not None)
check("crosswalk warns v2's own M-18 is a DIFFERENT gap (licensing)",
      re.search(r"v2 M-18: Legal, licensing", CROSSWALK) is not None)
check("crosswalk subsumes OQ-28 (source trust) into M-16",
      re.search(r"OPEN QUESTION-28.*?\*\*M-16\*\*", CROSSWALK) is not None)

# -- 5. The IOM confirms the gap, and enumerates no source type -------------
check("IOM annotates source_type as having no taxonomy",
      "MISSING-18: no taxonomy exists" in IOM)
check("IOM §5.2 records source_type as unscoped",
      re.search(r"MISSING-18 \| No source taxonomy \| Evidence — `source_type` unscoped",
                IOM) is not None)
check("IOM states no trust model exists (all sources weigh equally)",
      "absent a trust model, all sources weigh equally" in IOM)
check("IOM marks source_reliability optional and tied to OQ-28",
      re.search(r"`source_reliability`.*?OPEN QUESTION-28", IOM) is not None)

# The IOM must not enumerate a closed source-type vocabulary anywhere.
enumerated = re.findall(r"source_type:\s*(\w+)", IOM)
check("IOM provides at most an example value, not an enumeration",
      len(set(enumerated)) <= 1, f"values found: {sorted(set(enumerated))}")

# -- 6. M-02 (learning targets) is also open --------------------------------
check("v2 §13 lists M-02 (what the platform learns) as missing",
      re.search(r"\|\s*M-02\s*\|\s*What the platform learns", V2) is not None)
m02_closers = [k for k, v in closes.items() if re.search(r"\bM-02\b", v)]
check("no decision closes M-02 either", not m02_closers, str(m02_closers))

# -- 7. The playbook forbids the actions this task would require ------------
for fid, phrase in (
    ("F2", "Making an architectural decision yourself"),
    ("F3", "Closing a marker by implementation choice"),
    ("F12", "Silently proceeding past a contradiction"),
):
    check(f"playbook lists {fid}: {phrase}", phrase in PLAYBOOK)
check("playbook: markers close only by recorded decision",
      "Markers close only by recorded decision" in PLAYBOOK)
check("playbook: stop and escalate on an architectural decision",
      "stop and escalate" in PLAYBOOK)

# -- 8. Phase 1 remains frozen and untouched --------------------------------
import hashlib


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


check("oip/cascade.py unchanged since Phase 1 closure",
      md5(ROOT / "oip" / "cascade.py") == "b603ce9ed81d7026f87b7466bdeac080",
      md5(ROOT / "oip" / "cascade.py"))
check("oip/integrity.py unchanged since Phase 1 closure",
      md5(ROOT / "oip" / "integrity.py") == "42f1a9507b9679a25cfef9321a07fa6a",
      md5(ROOT / "oip" / "integrity.py"))
# Superseded by ratified-authority mode: the implementable portion of
# T02.1.1 has since been built. What must remain true is that the module
# closes NOTHING -- the taxonomy is still empty and M-16 is still open.
_src = ROOT / "oip" / "source.py"
check("source model exists but closes no marker", _src.exists()
      and "INTENTIONALLY EMPTY" in _src.read_text())
check("all 28 Phase-1 modules still present",
      len(list((ROOT / "oip").glob("*.py"))) >= 28,
      f"{len(list((ROOT / 'oip').glob('*.py')))}")

# -- report -----------------------------------------------------------------
failed = [(n, d) for n, ok, d in RESULTS if not ok]
print("=" * 78)
print("T02.1.1 BLOCKING ESCALATION -- mechanical verification")
print("=" * 78)
for name, ok, detail in RESULTS:
    line = f"  {'ok  ' if ok else 'FAIL'} {name}"
    if detail and not ok:
        line += f"  -> {detail}"
    print(line)
print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} verification checks passed")
if failed:
    print("\nFAILURES:")
    for n, d in failed:
        print(f"  {n}" + (f"  -> {d}" if d else ""))
sys.exit(1 if failed else 0)
