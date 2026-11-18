# MarkItDown per macOS

App macOS con interfaccia minimale che usa [MarkItDown](https://github.com/microsoft/markitdown) (Microsoft) per convertire documenti in Markdown.

## Cosa fa

- Accetta **PDF, DOCX, PPTX, XLSX, XLS, HTML, CSV, JSON, XML, EPUB, ZIP**
- Drag & drop sulla finestra, sull'icona nel Dock, oppure "Aggiungi file…" (⌘O)
- Vista del Markdown grezzo e anteprima renderizzata
- Copia negli appunti (⇧⌘C), salvataggio con nome (⌘S), "Mostra nel Finder"
- Conversione in un thread separato: l'interfaccia resta reattiva

### Impostazioni (⌘,)

| Impostazione | Default | Cosa fa |
|---|---|---|
| Destinazione | Accanto al file originale | Oppure una cartella fissa |
| Sovrascrivi | No | Se no, aggiunge “ (1)”, “ (2)”… ai nomi esistenti |
| Converti subito | Sì | Avvia la conversione appena aggiungi i file |
| Plugin di terze parti | No | Plugin di MarkItDown: eseguono codice esterno, attivali solo se ti fidi |

Le impostazioni sono salvate con `QSettings` (in `~/Library/Preferences`).

## Struttura

```
launch.py                  punto d'ingresso (sviluppo e bundle)
src/mdapp/converter.py     logica di conversione, senza Qt
src/mdapp/gui.py           interfaccia PySide6
tests/test_converter.py    test della logica di conversione
packaging/MarkItDown.spec  configurazione PyInstaller (bundle .app)
scripts/make_dmg.sh        crea il .dmg
.github/workflows/         build automatica su runner macOS
```

## Sviluppo su Mac

Richiede Python 3.10 o superiore (consigliato 3.12).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest -q          # test della conversione
python launch.py             # avvia l'app dal codice
```

## Creare il DMG

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean packaging/MarkItDown.spec
bash scripts/make_dmg.sh     # produce dist/MarkItDown-1.0.0-arm64.dmg
```

Il `.dmg` contiene l'app e un link ad `Applications` per l'installazione con trascinamento.

### Build automatica con GitHub Actions (consigliata se non hai un Mac dedicato)

Il workflow `.github/workflows/build-macos.yml` esegue test, build e creazione del DMG su un runner macOS a ogni push su `main` e può essere lanciato a mano (tab *Actions* → *build-macos* → *Run workflow*). Il DMG si scarica dagli *Artifacts* della run.

## Installazione su un altro Mac

L'app non è firmata con un certificato Apple Developer, quindi macOS la blocca al primo avvio:

1. Apri il `.dmg` e trascina **MarkItDown** in **Applicazioni**.
2. Al primo avvio, se macOS dice che l'app “non può essere aperta”: vai in **Impostazioni di Sistema → Privacy e sicurezza**, scorri fino al messaggio su MarkItDown e clicca **Apri comunque**.
3. In alternativa, da Terminale: `xattr -dr com.apple.quarantine /Applications/MarkItDown.app`

Per distribuire l'app ad altre persone senza questi passaggi serve firmarla con un *Developer ID* (programma Apple Developer a pagamento) e notarizzarla con `xcrun notarytool`. Non è incluso in questa versione.

## Compatibilità

- Il workflow produce un build **arm64** (Apple Silicon, M1 e successivi), con macOS 11 o superiore.
- Per Mac Intel, esegui `packaging/MarkItDown.spec` e `scripts/make_dmg.sh` direttamente su un Mac Intel.

## Limiti noti

- Immagini e audio non sono nell'elenco: MarkItDown le converte solo con un modello LLM o servizi Azure, che questa app non configura.
- La versione di MarkItDown è fissata a `0.1.7` in `requirements.txt`: aggiornala solo dopo aver rifatto i test.
- Il bundle usa un identificatore placeholder (`local.markitdown.mac`) nello spec: cambialo se distribuisci l'app.

## Stato delle verifiche

- Logica di conversione (`converter.py`): testata con `pytest` su HTML, CSV, gestione dei nomi e formati non supportati.
- Interfaccia PySide6 e build PyInstaller: scritte ma **non eseguite**, perché richiedono macOS. Al primo build, verifica che l'app si apra, che il drag & drop funzioni e che la conversione di un PDF sia completa nel bundle. Se la conversione PDF fallisce nel bundle, controlla i dati di `pdfminer` e `magika` nello spec.
