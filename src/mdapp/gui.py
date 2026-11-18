"""Interfaccia grafica (PySide6) per convertire documenti in Markdown con MarkItDown."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QEvent, QSettings, Qt, QThread, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
    QFileOpenEvent,
    QFontDatabase,
    QGuiApplication,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from mdapp import __version__
from mdapp.converter import (
    SUPPORTED_EXTENSIONS,
    ConversionOptions,
    ConversionResult,
    convert_file,
    create_converter,
    is_supported,
)

STATUS_WAITING = "In attesa"
STATUS_RUNNING = "In conversione…"
STATUS_DONE = "Convertito"
STATUS_ERROR = "Errore"

FILE_FILTER = "Documenti supportati (" + " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS)) + ")"


@dataclass
class Preferences:
    output_dir: Path | None = None
    overwrite: bool = False
    enable_plugins: bool = False
    auto_convert: bool = True

    def to_options(self) -> ConversionOptions:
        return ConversionOptions(
            output_dir=self.output_dir,
            overwrite=self.overwrite,
            enable_plugins=self.enable_plugins,
        )

    @classmethod
    def load(cls) -> "Preferences":
        s = QSettings()
        raw_dir = s.value("output_dir", "", type=str)
        return cls(
            output_dir=Path(raw_dir) if raw_dir else None,
            overwrite=s.value("overwrite", False, type=bool),
            enable_plugins=s.value("enable_plugins", False, type=bool),
            auto_convert=s.value("auto_convert", True, type=bool),
        )

    def save(self) -> None:
        s = QSettings()
        s.setValue("output_dir", str(self.output_dir) if self.output_dir else "")
        s.setValue("overwrite", self.overwrite)
        s.setValue("enable_plugins", self.enable_plugins)
        s.setValue("auto_convert", self.auto_convert)


@dataclass
class FileItem:
    path: Path
    status: str = STATUS_WAITING
    result: ConversionResult | None = None
    error: str = ""


class ConversionWorker(QThread):
    """Converte i file in un thread separato, così l'interfaccia non si blocca."""

    file_done = Signal(int, object)
    file_failed = Signal(int, str)

    def __init__(self, jobs: list[tuple[int, Path]], options: ConversionOptions, parent=None):
        super().__init__(parent)
        self._jobs = jobs
        self._options = options
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        try:
            converter = create_converter(self._options.enable_plugins)
        except Exception as exc:  # noqa: BLE001 - mostriamo l'errore all'utente
            for index, _ in self._jobs:
                self.file_failed.emit(index, f"Impossibile avviare MarkItDown: {exc}")
            return

        for index, path in self._jobs:
            if self._stop_requested:
                break
            try:
                result = convert_file(path, self._options, converter)
            except Exception as exc:  # noqa: BLE001
                self.file_failed.emit(index, f"{type(exc).__name__}: {exc}")
            else:
                self.file_done.emit(index, result)


class PreferencesDialog(QDialog):
    def __init__(self, prefs: Preferences, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Preferenze")
        self.setMinimumWidth(480)
        self._folder: Path | None = prefs.output_dir

        # Destinazione dei .md
        self.rb_source = QRadioButton("Accanto al file originale")
        self.rb_custom = QRadioButton("In questa cartella:")
        group = QButtonGroup(self)
        group.addButton(self.rb_source)
        group.addButton(self.rb_custom)

        self.folder_edit = QLineEdit(str(self._folder) if self._folder else "")
        self.folder_edit.setReadOnly(True)
        self.btn_browse = QPushButton("Scegli…")
        self.btn_browse.clicked.connect(self._choose_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(self.btn_browse)

        if self._folder:
            self.rb_custom.setChecked(True)
        else:
            self.rb_source.setChecked(True)
        self.rb_custom.toggled.connect(self._sync_folder_controls)
        self._sync_folder_controls()

        self.chk_overwrite = QCheckBox("Sovrascrivi i file .md esistenti (altrimenti aggiunge “ (1)”)")
        self.chk_overwrite.setChecked(prefs.overwrite)

        output_box = QGroupBox("Destinazione dei file .md")
        output_layout = QVBoxLayout(output_box)
        output_layout.addWidget(self.rb_source)
        output_layout.addWidget(self.rb_custom)
        output_layout.addLayout(folder_row)
        output_layout.addWidget(self.chk_overwrite)

        # Comportamento
        self.chk_auto = QCheckBox("Converti subito i file quando vengono aggiunti")
        self.chk_auto.setChecked(prefs.auto_convert)
        self.chk_plugins = QCheckBox("Abilita i plugin di terze parti di MarkItDown")
        self.chk_plugins.setChecked(prefs.enable_plugins)
        plugins_hint = QLabel(
            "I plugin eseguono codice di terze parti con i tuoi permessi. "
            "Attivali solo se ti fidi della fonte."
        )
        plugins_hint.setWordWrap(True)

        behavior_box = QGroupBox("Comportamento")
        behavior_layout = QVBoxLayout(behavior_box)
        behavior_layout.addWidget(self.chk_auto)
        behavior_layout.addWidget(self.chk_plugins)
        behavior_layout.addWidget(plugins_hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._try_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(output_box)
        layout.addWidget(behavior_box)
        layout.addWidget(buttons)

    def _sync_folder_controls(self) -> None:
        enabled = self.rb_custom.isChecked()
        self.folder_edit.setEnabled(enabled)
        self.btn_browse.setEnabled(enabled)

    def _choose_folder(self) -> None:
        start = str(self._folder or Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Cartella di output", start)
        if chosen:
            self._folder = Path(chosen)
            self.folder_edit.setText(chosen)

    def _try_accept(self) -> None:
        if self.rb_custom.isChecked() and self._folder is None:
            QMessageBox.warning(self, "Cartella mancante", "Scegli una cartella di output.")
            return
        self.accept()

    def result_preferences(self) -> Preferences:
        return Preferences(
            output_dir=self._folder if self.rb_custom.isChecked() else None,
            overwrite=self.chk_overwrite.isChecked(),
            enable_plugins=self.chk_plugins.isChecked(),
            auto_convert=self.chk_auto.isChecked(),
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MarkItDown")
        self.resize(1120, 680)
        self.setAcceptDrops(True)

        self.prefs = Preferences.load()
        self.items: list[FileItem] = []
        self.worker: ConversionWorker | None = None

        self._build_ui()
        self._build_menu()
        self._refresh_list()
        self.statusBar().showMessage("Trascina qui i file oppure usa File → Apri (⌘O)")

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        # Colonna sinistra: elenco file
        self.hint = QLabel("Trascina qui i file da convertire\noppure usa “Aggiungi file…”")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setStyleSheet("color: palette(mid); padding: 24px;")

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list.currentRowChanged.connect(self._show_current)

        self.btn_add = QPushButton("Aggiungi file…")
        self.btn_add.clicked.connect(self.open_files)
        self.btn_remove = QPushButton("Rimuovi")
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear = QPushButton("Svuota")
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_convert = QPushButton("Converti")
        self.btn_convert.clicked.connect(self.convert_pending)

        list_buttons = QHBoxLayout()
        for button in (self.btn_add, self.btn_remove, self.btn_clear):
            list_buttons.addWidget(button)
        list_buttons.addStretch(1)
        list_buttons.addWidget(self.btn_convert)

        self.progress = QProgressBar()
        self.progress.setVisible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self.hint)
        left_layout.addWidget(self.file_list, 1)
        left_layout.addLayout(list_buttons)
        left_layout.addWidget(self.progress)

        # Colonna destra: output
        self.tabs = QTabWidget()
        self.raw_view = QPlainTextEdit()
        self.raw_view.setReadOnly(True)
        self.raw_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.raw_view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        self.tabs.addTab(self.raw_view, "Markdown")
        self.tabs.addTab(self.preview, "Anteprima")

        self.btn_copy = QPushButton("Copia Markdown")
        self.btn_copy.clicked.connect(self.copy_current)
        self.btn_save = QPushButton("Salva .md…")
        self.btn_save.clicked.connect(self.save_current)
        self.btn_reveal = QPushButton("Mostra nel Finder")
        self.btn_reveal.clicked.connect(self.reveal_current)

        output_buttons = QHBoxLayout()
        output_buttons.addWidget(self.btn_copy)
        output_buttons.addWidget(self.btn_save)
        output_buttons.addStretch(1)
        output_buttons.addWidget(self.btn_reveal)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.tabs, 1)
        right_layout.addLayout(output_buttons)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([380, 700])

        container = QWidget()
        root = QVBoxLayout(container)
        root.addWidget(splitter)
        self.setCentralWidget(container)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        self._add_action(file_menu, "Apri…", self.open_files, QKeySequence.StandardKey.Open)
        self._add_action(file_menu, "Converti", self.convert_pending, "Ctrl+R")
        file_menu.addSeparator()
        self.act_save = self._add_action(
            file_menu, "Salva Markdown…", self.save_current, QKeySequence.StandardKey.Save
        )
        self.act_copy = self._add_action(file_menu, "Copia Markdown", self.copy_current, "Ctrl+Shift+C")
        file_menu.addSeparator()
        prefs_action = self._add_action(
            file_menu, "Preferenze…", self.open_preferences, QKeySequence.StandardKey.Preferences
        )
        # Su macOS, con questo ruolo la voce finisce nel menu dell'app "MarkItDown".
        prefs_action.setMenuRole(QAction.MenuRole.PreferencesRole)

    def _add_action(self, menu, text, slot, shortcut) -> QAction:
        action = QAction(text, self)
        action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)
        menu.addAction(action)
        self.addAction(action)  # Rende attive le scorciatoie anche senza menu
        return action

    # ------------------------------------------------------- drag and drop
    def dragEnterEvent(self, event) -> None:  # noqa: N802 - firma di Qt
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self.add_files(paths)
        event.acceptProposedAction()

    # ------------------------------------------------------------ gestione
    def _is_running(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def _current_item(self) -> FileItem | None:
        row = self.file_list.currentRow()
        return self.items[row] if 0 <= row < len(self.items) else None

    def open_files(self) -> None:
        if self._is_running():
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Scegli i file da convertire", "", FILE_FILTER)
        if paths:
            self.add_files([Path(p) for p in paths])

    def add_files(self, paths: list[Path]) -> None:
        if self._is_running():
            self.statusBar().showMessage("Attendi la fine della conversione per aggiungere altri file", 5000)
            return

        known = {item.path for item in self.items}
        added: list[Path] = []
        skipped: list[str] = []
        for path in paths:
            if path.is_dir():
                skipped.append(path.name)
            elif path in known:
                continue
            elif not is_supported(path):
                skipped.append(path.name)
            else:
                self.items.append(FileItem(path))
                known.add(path)
                added.append(path)

        if added:
            self._refresh_list(select=len(self.items) - 1)
        if skipped:
            self.statusBar().showMessage(f"Ignorati (formato non supportato): {', '.join(skipped)}", 8000)
        if added and self.prefs.auto_convert:
            self.convert_pending()

    def remove_selected(self) -> None:
        if self._is_running():
            return
        rows = sorted({index.row() for index in self.file_list.selectedIndexes()}, reverse=True)
        for row in rows:
            del self.items[row]
        self._refresh_list()

    def clear_all(self) -> None:
        if self._is_running():
            return
        self.items.clear()
        self._refresh_list()

    # ---------------------------------------------------------- conversione
    def convert_pending(self) -> None:
        if self._is_running():
            return
        jobs = [(i, item.path) for i, item in enumerate(self.items) if item.status != STATUS_DONE]
        if not jobs:
            self.statusBar().showMessage("Nessun file da convertire", 3000)
            return

        for index, _ in jobs:
            self.items[index].status = STATUS_RUNNING
            self.items[index].error = ""
        self._refresh_list()

        self.progress.setRange(0, len(jobs))
        self.progress.setValue(0)
        self.progress.setVisible(True)

        self.worker = ConversionWorker(jobs, self.prefs.to_options(), self)
        self.worker.file_done.connect(self._on_file_done)
        self.worker.file_failed.connect(self._on_file_failed)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()
        self._refresh_controls()

    def _on_file_done(self, index: int, result: ConversionResult) -> None:
        item = self.items[index]
        item.result = result
        item.status = STATUS_DONE
        item.error = ""
        self.progress.setValue(self.progress.value() + 1)
        self._update_row(index)

    def _on_file_failed(self, index: int, message: str) -> None:
        item = self.items[index]
        item.result = None
        item.status = STATUS_ERROR
        item.error = message
        self.progress.setValue(self.progress.value() + 1)
        self._update_row(index)

    def _on_worker_finished(self) -> None:
        done = sum(1 for i in self.items if i.status == STATUS_DONE)
        errors = sum(1 for i in self.items if i.status == STATUS_ERROR)
        self.progress.setVisible(False)
        self.statusBar().showMessage(f"Completato: {done} convertiti, {errors} con errore", 8000)
        self._show_current(self.file_list.currentRow())
        self._refresh_controls()

    # ------------------------------------------------------------ vista
    def _label(self, item: FileItem) -> str:
        return f"{item.path.name}  ·  {item.status}"

    def _update_row(self, index: int) -> None:
        item = self.items[index]
        list_item = self.file_list.item(index)
        if list_item is not None:
            list_item.setText(self._label(item))
            list_item.setToolTip(item.error or str(item.path))
        if index == self.file_list.currentRow():
            self._show_current(index)
        self._refresh_controls()

    def _refresh_list(self, select: int | None = None) -> None:
        row = self.file_list.currentRow() if select is None else select
        self.file_list.blockSignals(True)
        self.file_list.clear()
        for item in self.items:
            list_item = QListWidgetItem(self._label(item))
            list_item.setToolTip(item.error or str(item.path))
            self.file_list.addItem(list_item)
        self.file_list.blockSignals(False)

        if self.items:
            self.file_list.setCurrentRow(min(max(row, 0), len(self.items) - 1))
        self.hint.setVisible(not self.items)
        self.file_list.setVisible(bool(self.items))
        self._show_current(self.file_list.currentRow())

    def _show_current(self, row: int) -> None:
        item = self._current_item()
        if item is None:
            self.raw_view.clear()
            self.preview.clear()
        elif item.result is not None:
            self.raw_view.setPlainText(item.result.markdown)
            self.preview.setMarkdown(item.result.markdown)
        elif item.error:
            self.raw_view.setPlainText(f"Errore durante la conversione:\n\n{item.error}")
            self.preview.clear()
        else:
            self.raw_view.setPlainText("Conversione non ancora eseguita.")
            self.preview.clear()
        self._refresh_controls()

    def _refresh_controls(self) -> None:
        running = self._is_running()
        has_pending = any(i.status != STATUS_DONE for i in self.items)
        current = self._current_item()
        has_result = current is not None and current.result is not None

        for widget in (self.btn_add, self.btn_remove, self.btn_clear):
            widget.setEnabled(not running)
        self.btn_convert.setEnabled(not running and has_pending)

        for widget in (self.btn_copy, self.btn_save, self.btn_reveal):
            widget.setEnabled(has_result)
        self.act_save.setEnabled(has_result)
        self.act_copy.setEnabled(has_result)

    # ----------------------------------------------------- azioni output
    def copy_current(self) -> None:
        item = self._current_item()
        if item is None or item.result is None:
            return
        QGuiApplication.clipboard().setText(item.result.markdown)
        self.statusBar().showMessage("Markdown copiato negli appunti", 3000)

    def save_current(self) -> None:
        item = self._current_item()
        if item is None or item.result is None:
            return
        target, _ = QFileDialog.getSaveFileName(
            self, "Salva Markdown", str(item.result.output), "Markdown (*.md)"
        )
        if not target:
            return
        try:
            Path(target).write_text(item.result.markdown, encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Salvataggio non riuscito", str(exc))
            return
        self.statusBar().showMessage(f"Salvato: {Path(target).name}", 5000)

    def reveal_current(self) -> None:
        item = self._current_item()
        if item is None or item.result is None:
            return
        target = item.result.output
        if sys.platform == "darwin":
            # "open -R" apre il Finder con il file selezionato
            subprocess.run(["open", "-R", str(target)], check=False)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.parent)))

    def open_preferences(self) -> None:
        if self._is_running():
            QMessageBox.information(self, "Conversione in corso", "Attendi la fine della conversione.")
            return
        dialog = PreferencesDialog(self.prefs, self)
        if not dialog.exec():
            return

        old_options = self.prefs.to_options()
        self.prefs = dialog.result_preferences()
        self.prefs.save()

        # Se cambia cartella o plugin, i risultati già ottenuti non valgono più: si riconverte.
        if self.prefs.to_options() != old_options:
            for item in self.items:
                if item.status == STATUS_DONE:
                    item.status = STATUS_WAITING
                    item.result = None
            self._refresh_list()
        if self.prefs.auto_convert:
            self.convert_pending()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._is_running():
            answer = QMessageBox.question(
                self,
                "Conversione in corso",
                "Vuoi uscire? La conversione verrà interrotta dopo il file in lavorazione.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.worker.request_stop()
            self.worker.wait()
        event.accept()


class MarkItDownApplication(QApplication):
    def __init__(self, argv: list[str]):
        super().__init__(argv)
        self.window: MainWindow | None = None

    def event(self, event) -> bool:  # noqa: N802
        # macOS invia così i file trascinati sull'icona nel Dock o "Apri con MarkItDown"
        if event.type() == QEvent.Type.FileOpen and self.window is not None:
            if isinstance(event, QFileOpenEvent):
                self.window.add_files([Path(event.file())])
                return True
        return super().event(event)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv if argv is None else argv)
    app = MarkItDownApplication(args)
    app.setApplicationName("MarkItDown")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("MarkItDown")

    window = MainWindow()
    app.window = window
    window.show()

    # File passati da riga di comando (es. "open -a MarkItDown file.pdf")
    startup = [Path(a) for a in args[1:] if Path(a).is_file()]
    if startup:
        window.add_files(startup)

    return app.exec()
