from __future__ import annotations

from pathlib import Path

import pytest

from services.pdf_service import extract_pdf
from tools.pdf_tools import read_pdf


def _make_pdf(path: Path, title: str, lines: list[str]) -> Path:
    from reportlab.pdfgen import canvas

    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path))
    c.setTitle(title)
    text = c.beginText(72, 720)
    for line in lines:
        text.textLine(line)
    c.drawText(text)
    c.showPage()
    c.save()
    return path


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    return _make_pdf(
        tmp_path / "sample.pdf",
        title="Sample Report",
        lines=["Hello PDF World", "Second line of content"],
    )


class TestPdfService:
    @pytest.mark.asyncio
    async def test_extract_text_and_metadata(self, sample_pdf: Path):
        result = await extract_pdf(str(sample_pdf))
        assert result.error is None
        assert "Hello PDF World" in result.text
        assert "Second line of content" in result.text
        assert result.truncated is False
        assert result.metadata.get("pages") == 1

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        result = await extract_pdf("/nonexistent/file.pdf")
        assert result.error is not None
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_broken_pdf_returns_error_not_crash(self, tmp_path: Path):
        bad = tmp_path / "broken.pdf"
        bad.write_bytes(b"%PDF-1.4 not a real pdf")
        result = await extract_pdf(str(bad))
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_truncation_flag(self, sample_pdf: Path):
        result = await extract_pdf(str(sample_pdf), max_chars=10)
        assert result.truncated is True
        assert len(result.text) <= 10 + 50
        assert "truncated" in result.text


class TestPdfTool:
    @pytest.mark.asyncio
    async def test_read_pdf_missing_file(self):
        result = await read_pdf(_FakeCtx(), "/nonexistent/file.pdf")
        assert result.success is False
        assert result.error is not None
        assert result.error.category == "resource_not_found"

    @pytest.mark.asyncio
    async def test_read_pdf_returns_style_consistent(self, sample_pdf: Path):
        ctx = _FakeCtx()
        result = await read_pdf(ctx, str(sample_pdf))
        assert result.success is True
        assert result.output.startswith("Read sample.pdf")
        assert "Hello PDF World" in result.data["text"]
        assert result.data["truncated"] is False
        assert "num_pages" in result.data["metadata"] or "pages" in result.data["metadata"]


class _FakeCtx:
    class deps:
        workspace_path = None
