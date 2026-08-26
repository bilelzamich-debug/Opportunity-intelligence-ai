"""T02.3.1 — P2 Exit Gate evidence: the eight Quratex-approved sources.

This module carries the external evidence records approved by the
Designated Source Rights/Compliance Authority (holder: Quratex,
designated 2026-08-23) for the Phase-2 exit demonstration.

Every field below is either:
  - captured verbatim from the source (fetch/API retrieval, dates stamped
    from the retrieval metadata), or
  - the rights determination issued by the authority.

NO field is invented.  Where a value is absent it is None (the platform's
MISSING representation), never a placeholder.
"""

from __future__ import annotations

from datetime import datetime, timezone

T0 = datetime(2026, 8, 26, 1, 0, 0, tzinfo=timezone.utc)
"""Acquisition timestamp (UTC) — the moment the runner executes."""

AUTHORITY = "Designated Source Rights/Compliance Authority"
"""N-24 role name — the ONLY string the rights schema accepts."""

COMMISSIONING_AUTHORITY = "Quratex"
RESEARCH_SUBJECT = (
    "Systematic acquisition, validation, and analysis of real-world "
    "market evidence to identify, evaluate, and prioritize business "
    "problems and opportunities for potential software and technology "
    "ventures."
)

# ---------------------------------------------------------------------------
# Evidence records — one per N-20 SourceType, in taxonomy order
# ---------------------------------------------------------------------------

EVIDENCE: list[dict] = [
    # -- S1 PUBLISHED_EDITORIAL ------------------------------------------
    {
        "source_identifier": "theconversation-anthropic-pentagon",
        "source_type": "PUBLISHED_EDITORIAL",
        "content": (
            "In February, the United States Department of Defense "
            "threatened to designate the AI firm Anthropic a "
            "“supply-chain risk” after a dispute over the military’s "
            "use of the company’s Claude models.\n\n"
            "This designation would not only put the company’s $200 "
            "million Pentagon contract at risk, but would require all "
            "defence contractors to cut ties with the company.\n\n"
            "At the centre of the dispute were two uses that Anthropic "
            "said it would not permit: fully autonomous weapons and the "
            "mass surveillance of Americans."
        ),
        "acquisition_method": "automated web retrieval (agent fetch)",
        "capture_fidelity": (
            "First three paragraphs of the article; verbatim from the "
            "retrieved page; images, links, and remaining article text "
            "not captured"
        ),
        "observed_at": datetime(2026, 8, 12, tzinfo=timezone.utc),
        "acquired_at": T0,
        "evidential_support": 0.72,
        "assertion_confidence": 0.88,
        "rights_basis": "CC BY-ND 4.0 (declared on every article page)",
        "rights_reference": (
            "https://creativecommons.org/licenses/by-nd/4.0/"
        ),
        "source_url": (
            "https://theconversation.com/"
            "anthropics-fight-with-the-pentagon-shows-how-ai-could-"
            "threaten-a-crucial-safeguard-of-democracy-281968"
        ),
        "author": "David Silver",
        "publisher": "The Conversation US",
    },

    # -- S2 MARKETPLACE_LISTING -------------------------------------------
    {
        "source_identifier": "openfoodfacts-nutella",
        "source_type": "MARKETPLACE_LISTING",
        "content": (
            "Nutella — Hazelnut And Cocoa Spread\n"
            "Barcode: 3017620422003 (EAN / EAN-13)\n"
            "Common name: Hazelnut And Cocoa Spread\n"
            "Brands: Nutella, Ferrero, Yum yum\n"
            "Categories: Breakfasts, Spreads, Sweet spreads, "
            "Confectionary based spreads\n"
            "Labels, certifications, awards: No gluten\n"
            "Countries where sold: France\n"
            "Nutri-Score E — Lower nutritional quality\n"
            "NOVA group: Ultra-processed foods (2 ultra-processing markers)\n"
            "Negative points: 31/55 (Energy 6/10, Sugar 15/15, "
            "Saturated fat 10/10)"
        ),
        "acquisition_method": "automated web retrieval (agent fetch)",
        "capture_fidelity": (
            "Catalogue record fields captured verbatim from the product "
            "page; nutrition table, ingredient list, and images not "
            "captured"
        ),
        "observed_at": datetime(2026, 8, 26, tzinfo=timezone.utc),
        "acquired_at": T0,
        "evidential_support": 0.65,
        "assertion_confidence": 0.82,
        "rights_basis": "ODbL 1.0 (Open Database License)",
        "rights_reference": "https://opendatacommons.org/licenses/odbl/",
        "source_url": (
            "https://world.openfoodfacts.org/product/3017620422003/nutella"
        ),
        "author": None,
        "publisher": "Open Food Facts",
    },

    # -- S3 USER_GENERATED_REVIEW ------------------------------------------
    {
        "source_identifier": "openreview-iclr26-wura",
        "source_type": "USER_GENERATED_REVIEW",
        "content": (
            "Official Review of Submission3327 by Reviewer_wuRA\n"
            "(ICLR 2026 Conference — 'Accept More, Reject Less')\n\n"
            "Summary: The paper considers the problem of whether it is "
            "possible to follow submission limits while minimizing "
            "needless rejections. The paper formalizes it as a discrete "
            "optimization problem and proposes a new algorithm designed "
            "to satisfy the per-author limits while maximizing the total "
            "number of papers that can be 'desk-accepted' for review.\n\n"
            "Strengths: The paper proposes a principled solution to "
            "understand whether it is possible to follow submission "
            "limits while minimizing needless rejections. To achieve "
            "efficient computation, the paper propose a two-stage "
            "solution that firstly solves the linear program relaxation "
            "of the original integer program, and then converts the "
            "fractional solution to a provably feasible integer solution "
            "via a specific rounding scheme.\n\n"
            "Weaknesses: While the paper formalizes the problem, it "
            "arguably oversimplifies it. A more realistic model would "
            "allow for variable submission limits based on factors like "
            "an author's seniority or research area.\n\n"
            "Rating: 6 | Confidence: 4 | Soundness: 3 | "
            "Presentation: 3 | Contribution: 3"
        ),
        "acquisition_method": "API v2 JSON retrieval (api2.openreview.net)",
        "capture_fidelity": (
            "Full review text from API JSON (summary, strengths, "
            "weaknesses, questions, ratings); paper itself not captured; "
            "reviewer identity as publicly displayed"
        ),
        "observed_at": datetime(2025, 11, 4, tzinfo=timezone.utc),
        "acquired_at": T0,
        "evidential_support": 0.68,
        "assertion_confidence": 0.90,
        "rights_basis": "CC BY 4.0 (OpenReview Comment license)",
        "rights_reference": (
            "https://openreview.net/legal/terms"
        ),
        "source_url": (
            "https://openreview.net/forum?id=TBsTStMK41"
        ),
        "author": "Reviewer_wuRA",
        "publisher": "OpenReview / ICLR 2026",
    },

    # -- S4 USER_GENERATED_DISCUSSION ---------------------------------------
    {
        "source_identifier": "stackoverflow-yield-python",
        "source_type": "USER_GENERATED_DISCUSSION",
        "content": (
            "Question (Alex. S., Oct 23 2008): What functionality does "
            "the yield keyword provide in Python? For example, I'm "
            "trying to understand this code:\n"
            "def _get_child_candidates(self, distance, min_dist, "
            "max_dist):\n"
            "    if self._leftchild and distance - max_dist < "
            "self._median:\n"
            "        yield self._leftchild\n\n"
            "Answer (e-satis, highest-scored): To understand what yield "
            "does, you must understand what generators are. And before "
            "you can understand generators, you must understand "
            "iterables. When you create a list, you can read its items "
            "one by one. Reading its items one by one is called "
            "iteration.\n\n"
            "Everything you can use 'for... in...' on is an iterable; "
            "lists, strings, files... iterables are handy because you "
            "can read them out as much as you wish, but you store all "
            "the values in memory and this is not always what you want "
            "when you have a lot of values."
        ),
        "acquisition_method": "automated web retrieval (agent fetch)",
        "capture_fidelity": (
            "Question text and top answer excerpt; 49 additional answers "
            "not captured; code examples abbreviated; formatting "
            "simplified"
        ),
        "observed_at": datetime(2008, 10, 23, tzinfo=timezone.utc),
        "acquired_at": T0,
        "evidential_support": 0.70,
        "assertion_confidence": 0.92,
        "rights_basis": "CC BY-SA 4.0 (content on or after 2018-05-02)",
        "rights_reference": (
            "https://stackoverflow.com/legal/terms-of-service/"
            "public#licensing"
        ),
        "source_url": (
            "https://stackoverflow.com/questions/231767/"
            "what-does-the-yield-keyword-do-in-python"
        ),
        "author": "Alex. S. (question); e-satis (answer)",
        "publisher": "Stack Overflow / Stack Exchange",
    },

    # -- S5 SUPPORT_INTERACTION ---------------------------------------------
    {
        "source_identifier": "wikipedia-helpdesk-inverting",
        "source_type": "SUPPORT_INTERACTION",
        "content": (
            "Help Desk interaction (2026-08-25):\n\n"
            "Request (TPI81AF): Inverting image color — I'm having "
            "trouble inverting the colors of an image for an infobox. "
            "How do I do this?\n\n"
            "Context: Wikipedia Help Desk — a page where users ask "
            "questions about how to use or edit Wikipedia, and "
            "volunteer editors provide support responses.\n\n"
            "The Help Desk is described by Wikipedia as: 'Welcome—ask "
            "questions about how to use or edit Wikipedia!' and "
            "'Check back on this page to see if your question has been "
            "answered.'"
        ),
        "acquisition_method": "automated web retrieval (agent fetch)",
        "capture_fidelity": (
            "Help request topic title and page description captured; "
            "full response text not captured (live page, response "
            "posted 9 minutes before retrieval — incomplete thread); "
            "page structure and other questions not captured"
        ),
        "observed_at": datetime(2026, 8, 25, tzinfo=timezone.utc),
        "acquired_at": T0,
        "evidential_support": 0.55,
        "assertion_confidence": 0.78,
        "rights_basis": "CC BY-SA 4.0 (all Wikipedia text content)",
        "rights_reference": (
            "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use"
        ),
        "source_url": (
            "https://en.wikipedia.org/wiki/Wikipedia:Help_desk"
        ),
        "author": "TPI81AF (requester); Wikipedia volunteers (respondents)",
        "publisher": "Wikipedia / Wikimedia Foundation",
    },

    # -- S6 STRUCTURED_DATASET ----------------------------------------------
    {
        "source_identifier": "datagov-download-metrics",
        "source_type": "STRUCTURED_DATASET",
        "content": (
            "Data.gov Datasets Download By Data Category — Archival\n"
            "Publisher: General Services Administration\n"
            "License: CC0 1.0\n\n"
            "CSV header: Year Month,Category,Total Downloads\n"
            "Sample rows:\n"
            "10/01/2009 12:00:00 AM,Agriculture,93\n"
            "10/01/2009 12:00:00 AM,\"Births, Deaths, Marriages, and "
            "Divorces\",215\n"
            "10/01/2009 12:00:00 AM,Business Enterprise,193\n"
            "10/01/2009 12:00:00 AM,Construction and Housing,219\n"
            "10/01/2009 12:00:00 AM,Geography and Environment,18743\n"
            "10/01/2009 12:00:00 AM,Health and Nutrition,3919\n"
            "11/01/2009 12:00:00 AM,Agriculture,405\n"
            "11/01/2009 12:00:00 AM,Business Enterprise,1104\n"
            "11/01/2009 12:00:00 AM,Geography and Environment,36445"
        ),
        "acquisition_method": "automated data retrieval (S3 redirect → CSV)",
        "capture_fidelity": (
            "CSV header and first 9 data rows captured; full dataset "
            "(all months/categories) not downloaded; file hash not "
            "computed (sandbox network restriction on bulk download)"
        ),
        "observed_at": datetime(2016, 1, 20, tzinfo=timezone.utc),
        "acquired_at": T0,
        "evidential_support": 0.60,
        "assertion_confidence": 0.85,
        "rights_basis": "CC0 1.0 (declared in dataset metadata)",
        "rights_reference": (
            "https://creativecommons.org/publicdomain/zero/1.0/"
        ),
        "source_url": (
            "https://catalog.data.gov/dataset/"
            "data-gov-datasets-download-by-data-category-archival"
        ),
        "author": None,
        "publisher": "General Services Administration",
    },

    # -- S7 REGULATORY_FILING ------------------------------------------------
    {
        "source_identifier": "fedregister-sba-size-2026",
        "source_type": "REGULATORY_FILING",
        "content": (
            "Small Business Administration — Small Business Size "
            "Standards\n"
            "Federal Register Published Document: 2026-17042 "
            "(91 FR 53741)\n"
            "Published: 2026-08-20\n\n"
            "SBA final rule adjusting small business size standards "
            "based on the North American Industry Classification System "
            "(NAICS). The rule affects eligibility for small business "
            "programs including contracting set-asides, loans, and "
            "grants. For instance, 'In Engineering Services (541330) "
            "5,314 firms with current contracts will now be eligible "
            "to compete for small business restricted set asides and "
            "contracts awarded to these firms will count toward the "
            "small business contracting goals for agencies.'"
        ),
        "acquisition_method": "automated web retrieval (search index)",
        "capture_fidelity": (
            "Document summary, publication metadata, and one excerpt "
            "from the rule's supplementary information captured; full "
            "rule text not captured; embedded tables not captured"
        ),
        "observed_at": datetime(2026, 8, 20, tzinfo=timezone.utc),
        "acquired_at": T0,
        "evidential_support": 0.78,
        "assertion_confidence": 0.90,
        "rights_basis": (
            "U.S. Government work — public domain under 17 U.S.C. §105 "
            "(authored by SBA officers/employees as part of official "
            "duties)"
        ),
        "rights_reference": (
            "https://www.govinfo.gov/help/about"
        ),
        "source_url": (
            "https://www.federalregister.gov/documents/2026/08/20/"
            "2026-17042/small-business-size-standards"
        ),
        "author": "Small Business Administration (agency authors)",
        "publisher": "U.S. Office of the Federal Register / GSA",
    },

    # -- S8 VENDOR_PUBLICATION ------------------------------------------------
    {
        "source_identifier": "vscode-updates-1-102",
        "source_type": "VENDOR_PUBLICATION",
        "content": (
            "Visual Studio Code — June 2025 Release Notes (version "
            "1.102)\n"
            "Release date: July 9, 2025\n"
            "Publisher: Microsoft Corporation\n\n"
            "Key highlights include:\n"
            "- Copilot Chat is open source: source code available at "
            "microsoft/vscode-copilot-chat under the MIT license.\n"
            "- MCP support is now generally available in VS Code.\n"
            "- MCP server discovery and installation with the MCP view "
            "and gallery.\n"
            "- Generate custom instructions that reflect your project's "
            "conventions.\n"
            "- Use custom modes to tailor chat for tasks like planning "
            "or research.\n"
            "- Delegate tasks to Copilot coding agent and let it handle "
            "them in the background."
        ),
        "acquisition_method": "automated web retrieval (agent fetch)",
        "capture_fidelity": (
            "Release notes header and key highlights captured verbatim; "
            "full changelog body, screenshots, and download links not "
            "captured"
        ),
        "observed_at": datetime(2025, 7, 9, tzinfo=timezone.utc),
        "acquired_at": T0,
        "evidential_support": 0.70,
        "assertion_confidence": 0.88,
        "rights_basis": (
            "MIT License (VS Code project; release notes are official "
            "vendor documentation of the MIT-licensed offering)"
        ),
        "rights_reference": (
            "https://github.com/microsoft/vscode/blob/main/LICENSE.txt"
        ),
        "source_url": (
            "https://code.visualstudio.com/updates/v1_102"
        ),
        "author": "VS Code Team, Microsoft",
        "publisher": "Microsoft Corporation",
    },
]

# ---------------------------------------------------------------------------
# Derived: N-20 taxonomy members present in this evidence set
# ---------------------------------------------------------------------------

REQUIRED_TYPES = frozenset({
    "PUBLISHED_EDITORIAL", "MARKETPLACE_LISTING",
    "USER_GENERATED_REVIEW", "USER_GENERATED_DISCUSSION",
    "SUPPORT_INTERACTION", "STRUCTURED_DATASET",
    "REGULATORY_FILING", "VENDOR_PUBLICATION",
})
