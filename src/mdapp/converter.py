"""Logica di conversione, senza dipendenze da Qt: si testa anche da sola."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from markitdown import MarkItDown

# Formati che l'app accetta. Immagini e audio sono esclusi: richiedono
# un client LLM o servizi esterni che questa app non configura.
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pdf",
        ".docx",
        ".pptx",
        ".xlsx",
        ".xls",
        ".html",
        ".htm",
        ".csv",
        ".json",
        ".xml",
        ".epub",
        ".zip",
    }
)


@dataclass(frozen=True)
class ConversionOptions:
    output_dir: Path | None = None  # None = stessa cartella del file sorgente
    overwrite: bool = False         # False = aggiunge " (1)", " (2"... invece di sovrascrivere
    enable_plugins: bool = False    # Plugin di terze parti: disattivati di default


@dataclass(frozen=True)
class ConversionResult:
    source: Path
    output: Path
    markdown: str


class UnsupportedFormatError(ValueError):
    """Il file ha un'estensione che l'app non gestisce."""


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def create_converter(enable_plugins: bool = False) -> MarkItDown:
    return MarkItDown(enable_plugins=enable_plugins)


def resolve_output_path(source: Path, options: ConversionOptions) -> Path:
    """Restituisce il percorso del .md senza sovrascrivere file esistenti (se non richiesto)."""
    folder = options.output_dir or source.parent
    candidate = folder / f"{source.stem}.md"
    if options.overwrite:
        return candidate

    counter = 1
    while candidate.exists():
        candidate = folder / f"{source.stem} ({counter}).md"
        counter += 1
    return candidate


def convert_file(
    source: Path | str,
    options: ConversionOptions,
    converter: MarkItDown | None = None,
) -> ConversionResult:
    """Converte un file in Markdown e lo salva su disco.

    Passare un `converter` già creato evita di ricaricare i modelli
    per ogni file quando se ne convertono molti.
    """
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"File non trovato: {source}")
    if not is_supported(source):
        suffix = source.suffix or "senza estensione"
        raise UnsupportedFormatError(f"Formato non supportato: {suffix}")

    engine = converter or create_converter(options.enable_plugins)
    markdown = engine.convert(str(source)).markdown or ""

    output = resolve_output_path(source, options)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")

    return ConversionResult(source=source, output=output, markdown=markdown)
