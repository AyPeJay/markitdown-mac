from pathlib import Path

import pytest

from mdapp.converter import (
    ConversionOptions,
    UnsupportedFormatError,
    convert_file,
    is_supported,
    resolve_output_path,
)


def test_extension_check_is_case_insensitive():
    assert is_supported(Path("Report.PDF"))
    assert not is_supported(Path("foto.png"))


def test_output_name_gets_counter_instead_of_overwriting(tmp_path):
    source = tmp_path / "rapporto.html"
    source.write_text("<p>x</p>", encoding="utf-8")
    (tmp_path / "rapporto.md").write_text("vecchio", encoding="utf-8")

    output = resolve_output_path(source, ConversionOptions())

    assert output.name == "rapporto (1).md"


def test_overwrite_option_keeps_the_same_name(tmp_path):
    source = tmp_path / "rapporto.html"
    source.write_text("<p>x</p>", encoding="utf-8")
    (tmp_path / "rapporto.md").write_text("vecchio", encoding="utf-8")

    output = resolve_output_path(source, ConversionOptions(overwrite=True))

    assert output.name == "rapporto.md"


def test_html_is_converted_to_markdown(tmp_path):
    source = tmp_path / "pagina.html"
    source.write_text(
        "<html><body><h1>Titolo</h1><p>Ciao <b>mondo</b></p></body></html>",
        encoding="utf-8",
    )

    result = convert_file(source, ConversionOptions())

    assert result.output == tmp_path / "pagina.md"
    text = result.output.read_text(encoding="utf-8")
    assert "# Titolo" in text
    assert "**mondo**" in text


def test_csv_is_written_to_custom_output_dir(tmp_path):
    source = tmp_path / "dati.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    out_dir = tmp_path / "markdown"

    result = convert_file(source, ConversionOptions(output_dir=out_dir))

    assert result.output.parent == out_dir
    assert result.output.exists()
    assert "| a | b |" in result.markdown


def test_unsupported_extension_is_rejected(tmp_path):
    source = tmp_path / "foto.png"
    source.write_bytes(b"not really a png")

    with pytest.raises(UnsupportedFormatError):
        convert_file(source, ConversionOptions())


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        convert_file(tmp_path / "non_esiste.pdf", ConversionOptions())
