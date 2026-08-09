# Opportunity Intelligence Platform
# Platform Constitution

**Status:** Constitutional. Highest authority in the project.
**Established:** 2026-08-02
**Nature:** Invariant principles only. This document does not specify how anything is built.

---

## Preamble

This is the platform's constitutional document. It states what the platform **is**, what it **may never do**, and the principles that hold regardless of implementation.

It is deliberately short. Everything here is expected to remain true for the platform's lifetime.

**What this document is not.** It is not a specification, a design, or a plan. It contains no schemas, no interfaces, no engines, no phases. Those live in the Project Knowledge Pack, the Intelligence Object Model, and the Implementation Backlog — all of which are subordinate to this document and may change without it changing.

**Amendment.** A constitutional article may be amended only by a recorded decision that explicitly names the article it changes and states what is lost. Amendment is expected to be rare. If an article is being amended to accommodate a delivery pressure, that is evidence the pressure should be resisted instead.

---

## Article I — Vision

> Build an AI-native Opportunity Intelligence Platform that discovers, validates, scores, and learns from market opportunities using evidence-first reasoning.

Five commitments are binding: the platform is **AI-native**; it **discovers** rather than merely filters; it **validates** before asserting; it **scores** comparably; and it **learns** from outcomes.

---

## Article II — Core Principles

Five principles govern all platform behaviour.

| # | Principle |
|---|---|
| 1 | **Evidence before conclusions** |
| 2 | **Explainable decisions** |
| 3 | **Traceable lineage** |
| 4 | **Modular engines** |
| 5 | **Continuous learning** |

These five are the platform's original and complete principle set. Articles III–IX elaborate their consequences; they do not extend the set.

---

## Article III — Evidence First

**No conclusion may exist without traceable evidence.**

Every claim the platform makes resolves, through an unbroken chain, to something observed outside the platform. A conclusion that cannot be traced to evidence is not a weak conclusion — it is not a conclusion the platform is permitted to hold.

The platform may not reason from what a model happens to know. It reasons from what it has gathered.

**Accepted cost.** The platform is slower, more expensive, and blind outside its evidence base. These costs were accepted knowingly. They are not defects to be optimised away.

---

## Article IV — Ground Truth Protection

**No platform-generated artifact may become Evidence directly. Evidence must always originate from external reality.**

The platform may never treat its own output as an observation of the world. Feedback may become only:

- a **Learning Signal**
- a **Knowledge Update**
- a **Research Trigger**
- a **Model Calibration**

These four are exhaustive.

**Why this is constitutional.** A learning system with any path from its own output back into its grounding layer will corroborate itself with itself. It becomes progressively more confident while becoming less grounded, and every internal check continues to pass. This article closes that path permanently.

The platform learns from reality by **looking at reality again** — never by mistaking its own conclusions for observations.

---

## Article V — Intelligence Objects

**Intelligence Objects are the platform's only currency.**

All knowledge the platform holds exists as Intelligence Objects. All communication between engines occurs through them. There is no other channel.

Consequently:
- An object must be interpretable without consulting whatever produced it.
- An object carries its own lineage, its own explanation, and its own confidence.
- Anything two parts of the platform need to exchange must be expressible as an object. Where that is inconvenient, the object model is extended by recorded decision — never bypassed.

**Objects are immutable.** What the platform believed at a moment in time remains recoverable. Change creates a new version; it does not overwrite the past.

**Configuration is infrastructure state, not intelligence.** How the platform is configured may be stored alongside what the platform knows, but it remains logically isolated from it. Configuration never participates in reasoning, scoring, pattern detection, or lineage. An object may record which settings produced it; those settings contribute nothing to what it claims or how strongly it is believed.

---

## Article VI — Advisory Platform

**The platform advises. It does not act.**

It produces scored, validated opportunities and solution candidates, and hands them to those who decide. It holds no budget, no operational authority, and no accountability for consequences.

The platform does not:
- execute a recommendation,
- decide which opportunity is pursued,
- design how a solution is built,
- operate in the markets it observes,
- or judge whether an execution succeeded.

**Why this is constitutional.** A platform that observes a market and also participates in it cannot be a neutral observer of that market: its own actions enter the evidence base. Advisory scope is what keeps the platform's evidence external, and therefore what makes Article IV enforceable.

---

## Article VII — Human-in-the-Loop

**Human judgement is required where the cost of error is highest.**

Three decisions are reserved to people:

1. **Which opportunities are pursued.**
2. **Which validated solutions are released.**
3. **Which learning updates take effect.**

Everywhere else, the platform operates autonomously.

These three are reserved because each depends on context the evidence base does not contain — organisational capacity, appetite for risk, tolerance for change in a live system. The platform can compute a score; it cannot know whether the organisation can act on it.

**Automation may inform these decisions. It may not replace them.** Removing a reserved decision transfers accountability to the platform, which Article VI places outside it.

---

## Article VIII — Explainability

**Every decision the platform makes must be accompanied by why.**

An explanation is part of the conclusion, not an artefact produced alongside it. It travels with the object, references the specific evidence and criteria used, and is recorded whether the outcome was to accept or to reject.

**Rejections are decisions.** What the platform declined is recorded with the same rigour as what it advanced — because a rejected candidate that later proves valuable is among the most informative signals the platform can receive.

An unexplained score is not actionable, cannot be challenged, and cannot be improved. The platform does not produce them.

---

## Article IX — Traceability

**Nothing the platform holds is unaccountable.**

For any object, the complete path from external observation to that object can be reconstructed: what produced it, from what inputs, under what configuration, at what time.

This extends to the platform's own behaviour. When the platform changes how it reasons, that change is recorded, attributed to the outcomes that motivated it, and **reversible**.

Traceability is not logging. It is a structural property: the record is the knowledge itself, not a description of it kept elsewhere.

---

## Article X — Honest Uncertainty

**The platform states what it does not know.**

Confidence never exceeds what the evidence supports. Certainty degrades as reasoning moves further from observation, and the platform's confidence must degrade with it — a conclusion drawn through four inferential steps is never more certain than the evidence beneath it.

Negative results, contradictions, and known gaps are recorded with the same standing as favourable findings. Where the platform's knowledge is thin, it says so rather than presenting fluency as confidence.

**Why this is constitutional.** The platform's output drives resource decisions. A confident wrong answer is more damaging than an uncertain one, because it is acted upon.

---

## Article XI — Precedence

Where documents conflict, this order governs:

1. **This Constitution**
2. Decision records (the architecture decision register)
3. Intelligence Object Model
4. Project Knowledge Pack
5. Implementation Backlog

A subordinate document that contradicts this Constitution is in error, and the contradiction is resolved in the Constitution's favour without amendment to it.

---

*Eleven articles. Amended only by recorded decision naming the article changed.*
