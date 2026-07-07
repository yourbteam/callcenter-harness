# Call-Center Harness — Installation & Setup

Stand up the identical **air-gapped** call-QA harness on a fresh macOS machine. Provisioning is **online
once** (installs tools + downloads/vendors models); the pipeline then **runs offline** with no network
egress (compliance NFR-7).

> **Note on what lives where:** the *code* comes from this git repo. The *Python venv and model weights*
> live outside the repo under `~/.callcenter-harness/` and are **re-provisioned per machine** by the
> scripts below (they are gitignored, never pushed). PII audio is never committed.

---

## 1. Prerequisites

- **macOS** with **[Homebrew](https://brew.sh)**.
- **git** and **Python 3.11+** (validated on **3.14**). Check: `python3 --version`.
- **~4 GB free disk** for vendored models (STT small ≈ 0.5 GB; NER + GLiNER + base encoder ≈ 2.5 GB;
  optional STT large-v3 ≈ 3 GB).
- A **sample call recording** (`.mp3`/`.wav`, ideally 8 kHz stereo). *Not in the repo* — bring your own.

## 2. Clone

```bash
git clone https://github.com/yourbteam/callcenter-harness.git
cd callcenter-harness
```

## 3. Provision (ONLINE — one time)

Two scripts build the shared venv at `~/.callcenter-harness/venv` and vendor all models.

### 3a. Speech-to-text (ffmpeg + venv + faster-whisper + model)

```bash
# 'small' matches the harness default so the smokes work out of the box.
STT_MODEL=small ./scripts/setup_airgapped_stt.sh provision
```
Pass signal: `provision OK. Model vendored; inference can now run offline.`

*(For production Bulgarian accuracy, also provision the large model:
`STT_MODEL=large-v3 ./scripts/setup_airgapped_stt.sh provision` — then point the harness at it via the
`audio_redaction.stt_model_dir` / `transcription.stt_model_dir` phase config. The default is `small`.)*

### 3b. Redaction + prosody (BG-NER + GLiNER + parselmouth + vendored models)

```bash
./scripts/setup_airgapped_redaction.sh provision
```
This installs `gliner`, `transformers`, `torch`, `praat-parselmouth` into the venv and vendors
`iarfmoose/roberta-small-bulgarian-ner`, `urchade/gliner_multi-v2.1`, and (required)
`microsoft/mdeberta-v3-base` (GLiNER's base encoder — GLiNER phones home for it otherwise). PII detection
is Presidio-*style* (regex + checksum recognizers + the NER union) implemented directly in
`cc_harness/audio/redact.py` — no Presidio package needed.

Verify both NER models load offline:
```bash
./scripts/setup_airgapped_redaction.sh verify   # → VERIFY PASS: BG-NER + GLiNER loaded and ran offline
```

## 4. Verify the install (smokes)

The engine (M1) and ingest (M2) run under system `python3`; redaction/transcription/prosody/eval
(M3–M5) run under the **venv** python (which has the ML stack). Replace `<REC>` with your recording.

```bash
# M1 — engine boots + no-op workflow (no ML deps)
PYTHONPATH=src python3 scripts/cc_smoke.py

# M2 — ingest: non-conversation gate + ffmpeg channel split
PYTHONPATH=src python3 scripts/cc_ingest_smoke.py <REC>

# M3 — air-gapped redaction → compliant recording + redaction map
HF_HUB_OFFLINE=1 HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 \
  PYTHONPATH=src ~/.callcenter-harness/venv/bin/python scripts/cc_redact_smoke.py <REC>

# M4 — full pipeline through transcription + prosody
HF_HUB_OFFLINE=1 HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 \
  PYTHONPATH=src ~/.callcenter-harness/venv/bin/python scripts/cc_pipeline_smoke.py <REC>

# M5 — full pipeline ending in a script-adherence + delivery score
HF_HUB_OFFLINE=1 HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 \
  PYTHONPATH=src ~/.callcenter-harness/venv/bin/python scripts/cc_eval_smoke.py <REC>
```
Each prints `... ALL PASS`. The `HTTPS_PROXY=http://127.0.0.1:9` dead-proxy proves the run needs no
network (NFR-7); drop it to run normally offline via `HF_HUB_OFFLINE=1`.

## 5. Run the harness on a recording

```bash
HF_HUB_OFFLINE=1 PYTHONPATH=src ~/.callcenter-harness/venv/bin/python - <<'PY'
from cc_harness.engine.runner import WorkflowRunner
run = WorkflowRunner().start("callcenter-qa", {"recording_path": "<REC>"})
ev = run.context.get("evaluation", {})
print("status:", run.status)
print("evaluation:", ev.get("manager_summary"))
print("delivery flags:", (ev.get("intonation") or {}).get("flags"))
PY
```
Outputs (compliant recording, redaction map, transcripts) land under `~/.callcenter-harness/runs/<run_id>/`.
The MCP stdio server (`python3 -m cc_harness.server.mcp_stdio`) exposes `workflow.list` / `workflow.start`.

## 6. Air-gap posture (production)

Provisioning needs the network; **running does not**. For a hardened deployment, run the pipeline in a
**network-egress-denied** environment with `HF_HUB_OFFLINE=1` and the vendored models in place — the
smokes' dead-proxy invocation demonstrates the run succeeds with no outbound network.

## 7. Troubleshooting

- **GLiNER "couldn't connect to huggingface.co"** → the base encoder isn't vendored; re-run
  `./scripts/setup_airgapped_redaction.sh provision` (it vendors `microsoft/mdeberta-v3-base`).
- **`STT model not vendored`** → provision the model the harness expects (`small` by default):
  `STT_MODEL=small ./scripts/setup_airgapped_stt.sh provision`.
- **A smoke `held`** (blocked, not failed) → expected fail-closed behavior (low STT confidence,
  non-conversation, or unidentifiable agent channel); try a fuller/clearer recording.

## 8. What's in the repo vs. provisioned

| In git (this repo) | Provisioned locally (`~/.callcenter-harness/`, not in git) |
| --- | --- |
| `src/cc_harness/` engine + audio + eval | Python venv (`venv/`) with the ML stack |
| `scripts/` provisioning + smokes | vendored models (`models/`) |
| `workflows/`, `contracts/`, `docs/` | run outputs (`runs/`, PII) |

Raw client materials (`ClientFiles/`) and PII audio/models are **gitignored** by default.
