# -*- mode: python ; coding: utf-8 -*-
# Build dalla radice del progetto:
#   pyinstaller --noconfirm --clean packaging/MarkItDown.spec

import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from mdapp import __version__  # noqa: E402


def optional(func, *args):
    """Alcuni pacchetti possono non avere dati o metadati: non far fallire la build."""
    try:
        return func(*args)
    except Exception:  # noqa: BLE001
        return []


# magika (dipendenza obbligatoria di markitdown) include modelli ONNX come dati:
# senza questi, la conversione fallisce nel bundle con un errore di file mancante.
datas = []
for package in ("markitdown", "magika", "pdfminer"):
    datas += optional(collect_data_files, package)
    datas += optional(copy_metadata, package)

hiddenimports = collect_submodules("markitdown") + optional(collect_submodules, "magika")

a = Analysis(
    [os.path.join(ROOT, "launch.py")],
    pathex=[os.path.join(ROOT, "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MarkItDown",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # app con finestra, senza terminale
    disable_windowed_traceback=False,
    argv_emulation=False,  # i file da Dock/Finder arrivano dall'evento FileOpen (vedi gui.py)
    target_arch=None,      # None = architettura nativa della macchina di build
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MarkItDown",
)

ICON_PATH = os.path.join(ROOT, "packaging", "AppIcon.icns")

app = BUNDLE(
    coll,
    name="MarkItDown.app",
    icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
    bundle_identifier="local.markitdown.mac",  # sostituire con un identificatore proprio
    info_plist={
        "CFBundleName": "MarkItDown",
        "CFBundleDisplayName": "MarkItDown",
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSHumanReadableCopyright": "MarkItDown è distribuito sotto licenza MIT (Microsoft).",
        # Permette di trascinare file sull'icona nel Dock e di scegliere "Apri con MarkItDown"
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Documento convertibile",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": [
                    "com.adobe.pdf",
                    "org.openxmlformats.wordprocessingml.document",
                    "org.openxmlformats.presentationml.presentation",
                    "org.openxmlformats.spreadsheetml.sheet",
                    "com.microsoft.excel.xls",
                    "public.html",
                    "public.comma-separated-values-text",
                    "public.json",
                    "public.xml",
                    "org.idpf.epub-container",
                    "public.zip-archive",
                ],
            }
        ],
    },
)
