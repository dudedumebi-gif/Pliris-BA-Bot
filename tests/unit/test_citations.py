"""Unit tests for citation formatting."""

from pliris.generation.citations import CitationFormatter


def test_extract_citations():
    """Test citation extraction from response."""
    formatter = CitationFormatter()

    response = "According to [Document 1], the revenue was $100M. [Document 2] shows growth."
    context = [
        {"source": "Report A", "title": "Financial Report", "text": "Revenue was $100M"},
        {"source": "Report B", "title": "Growth Report", "text": "Growth was 15%"},
    ]

    citations = formatter.extract_citations(response, context)

    assert len(citations) == 2
    assert citations[0]["title"] == "Financial Report"
    assert citations[1]["title"] == "Growth Report"


def test_format_citation():
    """Test citation formatting."""
    formatter = CitationFormatter()

    citation = {"title": "Annual Report 2024", "source": "Finance Dept", "page": 5}

    formatted = formatter.format_citation(citation, 1)

    assert "[1]" in formatted
    assert "Annual Report 2024" in formatted
    assert "Finance Dept" in formatted


def test_build_bibliography():
    """Test bibliography building."""
    formatter = CitationFormatter()

    citations = [
        {"title": "Report A", "source": "Source A", "page": 1},
        {"title": "Report B", "source": "Source B", "page": 2},
    ]

    bibliography = formatter.build_bibliography(citations)

    assert "## References" in bibliography
    assert "Report A" in bibliography
    assert "Report B" in bibliography
