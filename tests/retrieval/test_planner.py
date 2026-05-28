"""Unit tests for RetrievalPlanner."""

from __future__ import annotations

import pytest

from ate_rag_kb.retrieval.planner import RetrievalPlanner


class TestRetrievalPlanner:
    @pytest.fixture
    def planner(self) -> RetrievalPlanner:
        return RetrievalPlanner()

    # -------------------------------------------------------------------
    # Ecosystem detection
    # -------------------------------------------------------------------

    def test_detect_ecosystem_igxl(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("ig-xl job list")
        assert plan.ecosystem == "igxl"
        assert plan.is_igxl_query is True

    def test_detect_ecosystem_v93000(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("v93000 timing configuration")
        assert plan.ecosystem == "v93000"
        assert plan.is_v93000_smt7_query is True

    def test_detect_ecosystem_smt7(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("smt7 array handling")
        assert plan.ecosystem == "v93000"

    def test_detect_ecosystem_tdc(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("tdc flow creator usage")
        assert plan.ecosystem == "v93000"

    def test_detect_ecosystem_neutral(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("how does testing work in general")
        assert plan.ecosystem is None

    def test_non_igxl_terms_override_igxl(self, planner: RetrievalPlanner) -> None:
        # "v93000" should win even if "pattern tool" is an IG-XL term
        plan = planner.plan("v93000 pattern tool")
        assert plan.ecosystem == "v93000"

    # -------------------------------------------------------------------
    # Doc family detection
    # -------------------------------------------------------------------

    def test_detect_doc_family_tdc(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("tdc test development center")
        assert plan.doc_family == "tdc"
        assert plan.ecosystem == "v93000"

    def test_detect_doc_family_igxl_help(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("datatool pin map configuration")
        assert plan.doc_family == "igxl_help"
        assert plan.ecosystem == "igxl"

    def test_detect_doc_family_smt7_help(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("smt7 online help")
        assert plan.doc_family == "smt7_help"
        assert plan.ecosystem == "v93000"

    def test_detect_doc_family_v93000_manual(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("v93000 hardware manual")
        assert plan.doc_family == "v93000_manual"
        assert plan.ecosystem == "v93000"

    # -------------------------------------------------------------------
    # Glossary expansion
    # -------------------------------------------------------------------

    def test_expand_glossary_job_list(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("作业列表有什么用")
        assert "Job List Sheet" in plan.enhanced_query

    def test_expand_glossary_array(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("数组的作用")
        assert "ARRAY" in plan.enhanced_query

    def test_no_expansion_for_unknown_query(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("random unrelated query")
        assert plan.enhanced_query == "random unrelated query"

    # -------------------------------------------------------------------
    # Title match terms
    # -------------------------------------------------------------------

    def test_extract_title_match_terms_job_list(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("Job List Sheet usage")
        assert "job list sheet" in plan.title_match_terms

    def test_extract_title_match_terms_with_glossary(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("作业列表")
        assert "job list sheet" in plan.title_match_terms

    # -------------------------------------------------------------------
    # Filter inference
    # -------------------------------------------------------------------

    def test_infer_filters_igxl(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("ig-xl pattern tool")
        assert plan.inferred_filters is None

    def test_infer_filters_smt7(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("smt7 timing")
        assert plan.inferred_filters == {"platform": "SMT7"}

    def test_infer_filters_v93000(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("v93000 levels")
        assert plan.inferred_filters == {"platform": "V93000"}

    def test_infer_filters_tdc(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("tdc module creation")
        # Legacy compatibility: TDC docs use platform="TDC" in old index,
        # but TDC is logically a doc_family under v93000 ecosystem.
        assert plan.inferred_filters == {"platform": ["SMT7", "V93000", "TDC"]}

    def test_infer_filters_neutral(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("general testing question")
        assert plan.inferred_filters is None

    def test_infer_filters_v93000_ecosystem_no_specific_platform(
        self, planner: RetrievalPlanner
    ) -> None:
        plan = planner.plan("flextest timing")
        assert plan.ecosystem == "v93000"
        assert plan.inferred_filters == {"platform": ["SMT7", "V93000", "TDC"]}

    # -------------------------------------------------------------------
    # TDC logical mapping
    # -------------------------------------------------------------------

    def test_tdc_mapped_to_v93000_ecosystem(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("tdc how to view documents")
        assert plan.ecosystem == "v93000"
        assert plan.doc_family == "tdc"

    # -------------------------------------------------------------------
    # Glossary ecosystem / doc_family backfill
    # -------------------------------------------------------------------

    def test_glossary_backfills_igxl_ecosystem(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("作业列表有什么用")
        assert plan.ecosystem == "igxl"
        assert plan.doc_family == "igxl_help"

    def test_glossary_backfills_tdc_ecosystem(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("TDC 文档怎么查看")
        assert plan.ecosystem == "v93000"
        assert plan.doc_family == "tdc"

    def test_explicit_platform_wins_over_glossary(self, planner: RetrievalPlanner) -> None:
        plan = planner.plan("SMT7 job list")
        assert plan.ecosystem == "v93000"
        assert plan.doc_family != "igxl_help"
        assert "Job List Sheet" not in plan.enhanced_query
        assert "DataTool Job List" not in plan.enhanced_query
