"""Retrieval planner for ATE KB query analysis and enhancement.

Analyzes user queries to detect ecosystem, doc family, expands Chinese terms
via glossary, extracts title-match terms, and infers Qdrant filters.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from ate_rag_kb.retrieval.glossary import GlossaryEntry, expand_query, match_glossary
from ate_rag_kb.utils.config import Config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ecosystem / doc-family detection vocabularies
# ---------------------------------------------------------------------------

_IGXL_ECOSYSTEM_TERMS: tuple[str, ...] = (
    "ig-xl",
    "igxl",
    "j750",
    "ultraflex",
    "mto800",
    "dsio200",
    "apmu",
    "ip750",
    "test analysis tool",
    "secs/gem",
    "available j750 features",
    "simulatedconfig_j750",
    "hsd800",
    "j750ex",
    "test program protection",
    "visual basic for test",
    "driverapi",
    "pattern tool",
    "mto",
    "vectors worksheet",
    "datatool",
    "bitmap tool",
    "redundancy analysis",
    "raplus",
    "production bit map",
    "tpprotection",
    "tppusing",
    "flow table",
    "pin map",
    "test instances",
    "vbt",
)

_V93000_ECOSYSTEM_TERMS: tuple[str, ...] = (
    "v93000",
    "smartest",
    "smt7",
    "smt8",
    "tdc",
    "test development center",
    "device preparation",
    "test program creation",
    "flow creator",
    "module",
    "test suite",
    "pin electronics",
    "channel card",
    "ps1600",
    "cmu",
    "dps",
    "dvi",
    "pvi",
    "uvi",
    "vector memory",
    "flextest",
)

_IGXL_DOC_FAMILY_TERMS: tuple[str, ...] = (
    "datatool",
    "pattern tool",
    "bitmap tool",
    "test analysis tool",
    "vbt",
    "visual basic for test",
    "driverapi",
    "mto800",
    "flow table",
    "pin map",
    "test instances",
    "secs/gem",
    "mto",
    "vectors worksheet",
)

_TDC_DOC_FAMILY_TERMS: tuple[str, ...] = (
    "tdc",
    "test development center",
    "device preparation",
    "test program creation",
    "flow creator",
    "module",
    "test suite",
)

_SMT7_DOC_FAMILY_TERMS: tuple[str, ...] = (
    "smt7",
    "smartest 7",
    "online help",
    "operator mode",
    "engineering mode",
)

_V93000_MANUAL_TERMS: tuple[str, ...] = (
    "v93000 manual",
    "hardware manual",
    "reference manual",
    "user guide",
    "getting started",
)

# Terms that strongly indicate a NON-IG-XL query
_NON_IGXL_TERMS: tuple[str, ...] = ("v93000", "smartest", "smt7", "smt8")


@dataclass
class RetrievalPlan:
    """The output of query planning: a structured retrieval strategy."""

    original_query: str
    enhanced_query: str  # Original + glossary expansions
    inferred_filters: dict[str, Any] | None
    ecosystem: str | None  # "igxl" | "v93000"
    doc_family: str | None  # "tdc" | "smt7_help" | "igxl_help" | "v93000_manual"
    title_match_terms: list[str]  # Proper nouns for title boosting
    is_igxl_query: bool
    is_v93000_smt7_query: bool


class RetrievalPlanner:
    """Analyzes ATE queries and produces structured retrieval plans."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config({})
        self._title_boost_factor = self.config.get(
            "retrieval.planner.title_boost_factor", 0.15
        )
        self._glossary_enabled = self.config.get(
            "retrieval.planner.glossary_enabled", True
        )
        self._auto_filter_enabled = self.config.get(
            "retrieval.planner.auto_filter_enabled", True
        )

    def plan(self, query: str) -> RetrievalPlan:
        """Analyze *query* and return a ``RetrievalPlan``."""
        ecosystem = self._detect_ecosystem(query)
        doc_family = self._detect_doc_family(query, ecosystem)

        if self._glossary_enabled:
            matched_glossary = self._compatible_glossary_entries(
                match_glossary(query), ecosystem
            )
            enhanced_query = expand_query(query, matched_glossary)
        else:
            matched_glossary = []
            enhanced_query = query

        # Backfill ecosystem / doc_family from glossary when the query is
        # ambiguous (no explicit platform mentioned by the user).
        if matched_glossary:
            glossary_ecosystem = None
            glossary_doc_family = None
            for entry in matched_glossary:
                if entry.ecosystem:
                    glossary_ecosystem = entry.ecosystem
                if entry.doc_family:
                    glossary_doc_family = entry.doc_family

            # Only backfill if the user did not explicitly specify an
            # ecosystem, or if the glossary value is compatible.
            if ecosystem is None and glossary_ecosystem is not None:
                ecosystem = glossary_ecosystem
            if doc_family is None and glossary_doc_family is not None and (
                ecosystem is None
                or glossary_ecosystem is None
                or ecosystem == glossary_ecosystem
            ):
                doc_family = glossary_doc_family

        title_match_terms = self._extract_title_match_terms(query, matched_glossary)

        if self._auto_filter_enabled:
            inferred_filters = self._infer_filters(ecosystem, doc_family, query)
        else:
            inferred_filters = None

        return RetrievalPlan(
            original_query=query,
            enhanced_query=enhanced_query,
            inferred_filters=inferred_filters,
            ecosystem=ecosystem,
            doc_family=doc_family,
            title_match_terms=title_match_terms,
            is_igxl_query=ecosystem == "igxl",
            is_v93000_smt7_query=ecosystem == "v93000",
        )

    @staticmethod
    def _compatible_glossary_entries(
        entries: list[GlossaryEntry], explicit_ecosystem: str | None
    ) -> list[GlossaryEntry]:
        """Drop glossary expansions that conflict with an explicit ecosystem.

        Generic entries without an ecosystem are allowed everywhere. Entries
        tied to IG-XL or V93000 only apply when the query did not already name
        the other ecosystem.
        """
        if explicit_ecosystem is None:
            return entries
        return [
            entry
            for entry in entries
            if entry.ecosystem is None or entry.ecosystem == explicit_ecosystem
        ]

    # -----------------------------------------------------------------------
    # Ecosystem detection
    # -----------------------------------------------------------------------

    @staticmethod
    def _detect_ecosystem(query: str) -> str | None:
        """Detect tester ecosystem from query text.

        Returns ``"igxl"``, ``"v93000"``, or ``None``.
        """
        normalized = query.lower()

        # If non-IGXL terms appear, prefer v93000 ecosystem
        has_non_igxl = any(term in normalized for term in _NON_IGXL_TERMS)
        if has_non_igxl:
            return "v93000"

        has_igxl = any(term in normalized for term in _IGXL_ECOSYSTEM_TERMS)
        if has_igxl:
            return "igxl"

        has_v93000 = any(term in normalized for term in _V93000_ECOSYSTEM_TERMS)
        if has_v93000:
            return "v93000"

        return None

    # -----------------------------------------------------------------------
    # Doc family detection
    # -----------------------------------------------------------------------

    @staticmethod
    def _detect_doc_family(query: str, ecosystem: str | None) -> str | None:
        """Detect document family within an ecosystem."""
        normalized = query.lower()

        # TDC is detected first because it is a sub-family under v93000
        if any(term in normalized for term in _TDC_DOC_FAMILY_TERMS):
            return "tdc"

        if ecosystem == "igxl":
            if any(term in normalized for term in _IGXL_DOC_FAMILY_TERMS):
                return "igxl_help"
            return "igxl_help"  # Default for IG-XL ecosystem

        if ecosystem == "v93000":
            if any(term in normalized for term in _SMT7_DOC_FAMILY_TERMS):
                return "smt7_help"
            if any(term in normalized for term in _V93000_MANUAL_TERMS):
                return "v93000_manual"
            return None

        return None

    # -----------------------------------------------------------------------
    # Title match term extraction
    # -----------------------------------------------------------------------

    @staticmethod
    def _extract_title_match_terms(
        query: str, matched_glossary: list[GlossaryEntry]
    ) -> list[str]:
        """Extract proper nouns (sheet names, commands, APIs) for title matching.

        Returns a list of lower-cased terms that should be searched in
        doc_title, section_title, subsection_title, and toc_path.
        """
        terms: list[str] = []

        # Add expansions from matched glossary entries
        for entry in matched_glossary:
            terms.extend(entry.expansions)
            terms.extend(entry.en_terms)

        # Extract capitalized phrases (e.g., "Job List Sheet", "MTO Resource Map")
        # Match sequences of capitalized words
        capitalized_phrases = re.findall(
            r"[A-Z][a-zA-Z0-9_]*(?:\s+[A-Z][a-zA-Z0-9_]*)+", query
        )
        terms.extend(capitalized_phrases)

        # Extract quoted phrases
        quoted = re.findall(r'"([^"]+)"', query)
        terms.extend(quoted)

        # Deduplicate and lower-case
        seen: set[str] = set()
        result: list[str] = []
        for term in terms:
            lowered = term.lower()
            if lowered not in seen and len(lowered) > 1:
                seen.add(lowered)
                result.append(lowered)
        return result

    # -----------------------------------------------------------------------
    # Filter inference
    # -----------------------------------------------------------------------

    @staticmethod
    def _infer_filters(
        ecosystem: str | None, doc_family: str | None, query: str
    ) -> dict[str, Any] | None:
        """Build Qdrant filters from detected ecosystem / doc_family."""
        normalized = query.lower()

        if ecosystem == "igxl":
            # IG-XL queries do NOT set a platform filter;
            # contamination is handled post-search by ecosystem filter.
            return None

        if ecosystem == "v93000":
            # Legacy compatibility: old index uses platform="TDC" for TDC docs.
            # TDC is logically a doc_family under the v93000 ecosystem.
            # Use a broad filter so TDC docs are included without locking
            # results to only TDC.
            if doc_family == "tdc":
                return {"platform": ["SMT7", "V93000", "TDC"]}

            # Direct platform terms
            if "smt7" in normalized or "smartest 7" in normalized:
                return {"platform": "SMT7"}
            if "v93000" in normalized:
                return {"platform": "V93000"}

            # If we know it's v93000 ecosystem but no specific platform,
            # allow both SMT7 and V93000 (and TDC)
            return {"platform": ["SMT7", "V93000", "TDC"]}

        return None
