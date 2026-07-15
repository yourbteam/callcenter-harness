#!/usr/bin/env python3
"""STT prose-prompt wiring: config parses stt_prompt (natural prose, NOT a keyword list — bare lists make
Whisper echo terms back), the runner concatenates locale+brand prose, and transcribe_words forwards it as
initial_prompt. Fast — no real model.
Run: PYTHONPATH=src python3 scripts/test_stt_prompt.py"""
import sys, tempfile, types
from pathlib import Path
from cc_harness.config.loader import load_profile, load_language
from cc_harness.engine.runner import _stt_prompt

def ck(n, c):
    print(f"[{'PASS' if c else 'FAIL'}] {n}"); (c or sys.exit(1))

# --- config parses stt_prompt from the shipped packs (prose, not lists) ---
lang = load_language("bg")
prof = load_profile("profiles/a1.json")
ck("bg pack exposes stt_prompt prose", isinstance(lang.stt_prompt, str) and "отстъпка" in lang.stt_prompt)
ck("a1 profile exposes stt_prompt prose", isinstance(prof.stt_prompt, str) and "Моят А1" in prof.stt_prompt)
ck("bg stt_prompt is prose, not a bare list", " " in lang.stt_prompt.strip() and len(lang.stt_prompt.split()) > 6)

# --- _stt_prompt: concatenates locale + brand prose, None when empty ---
class P:
    def __init__(self, v): self.stt_prompt = v
ck("_stt_prompt concatenates locale+brand", _stt_prompt(P("Locale sentence."), P("Brand sentence.")) == "Locale sentence. Brand sentence.")
ck("_stt_prompt None when both empty", _stt_prompt(P(""), P("")) is None)
ck("_stt_prompt None when attrs absent", _stt_prompt(object(), object()) is None)
ck("_stt_prompt uses one side when other empty", _stt_prompt(P("only locale"), P("")) == "only locale")
real = _stt_prompt(lang, prof)
ck("real bg+a1 prompt is one prose string", isinstance(real, str) and "Моят А1" in real and "отстъпка" in real)

# --- transcribe_words forwards initial_prompt to faster-whisper (fake model, no weights) ---
captured = {}
fake = types.ModuleType("faster_whisper")
class FakeModel:
    def __init__(self, *a, **k): pass
    def transcribe(self, audio, **kw):
        captured.update(kw)
        return [], types.SimpleNamespace(language="bg", language_probability=1.0, duration=1.0)
fake.WhisperModel = FakeModel
sys.modules["faster_whisper"] = fake

from cc_harness.audio import stt
md = Path(tempfile.mkdtemp())
stt.transcribe_words("x.wav", language="bg", model_dir=str(md), initial_prompt="prose here")
ck("initial_prompt forwarded", captured.get("initial_prompt") == "prose here")
captured.clear()
stt.transcribe_words("x.wav", language="bg", model_dir=str(md))  # default
ck("initial_prompt defaults to None", captured.get("initial_prompt") is None)
captured.clear()
stt.transcribe_words("x.wav", language="bg", model_dir=str(md), initial_prompt="")
ck("empty prompt coerced to None (no-op)", captured.get("initial_prompt") is None)

# --- M2: non-string stt_prompt is fail-closed (a list would feed a bracketed keyword prompt -> echo bug) ---
import json as _json
from cc_harness.config.loader import ConfigError
def _raises_configerror(fn):
    try:
        fn(); return False
    except ConfigError:
        return True
_prof = _json.loads(Path("profiles/a1.json").read_text(encoding="utf-8")); _prof["stt_prompt"] = ["a", "b"]
(md / "badprompt_profile.json").write_text(_json.dumps(_prof, ensure_ascii=False), encoding="utf-8")
ck("profile stt_prompt as a LIST -> ConfigError", _raises_configerror(lambda: load_profile(str(md / "badprompt_profile.json"))))
_langd = _json.loads(Path("languages/bg.json").read_text(encoding="utf-8")); _langd["stt_prompt"] = 123
(md / "bg.json").write_text(_json.dumps(_langd, ensure_ascii=False), encoding="utf-8")
ck("language stt_prompt as a NUMBER -> ConfigError", _raises_configerror(lambda: load_language("bg", languages_dir=str(md))))

# --- M3: phase-level wiring — transcription is PRIMED, redaction is UNPRIMED (the crux of the fix) ---
import dataclasses
from cc_harness.engine.runner import WorkflowRunner
from cc_harness.state.store import WorkflowRun, PhaseState
from cc_harness.engine.workflow import WorkflowPhase

real_lang = load_language("bg"); real_prof = load_profile("profiles/a1.json")
expected_prompt = _stt_prompt(real_lang, real_prof)

calls = []  # each recorded transcribe_words call's kwargs
def _recorder(path, language="bg", model_dir=None, initial_prompt=None):
    calls.append({"initial_prompt": initial_prompt})
    return ([{"word": "здравейте", "start": 0.0, "end": 0.5, "probability": 0.9, "seg_start": 0.0, "seg_end": 0.5}],
            {"duration": 1.0, "mean_word_probability": 0.9, "word_count": 1})
stt.transcribe_words = _recorder  # patch the module the runner imported

runner = WorkflowRunner()

# (a) transcription phase forwards the config prose as initial_prompt
run = WorkflowRun(run_id="t1", workflow_name="callcenter-qa")
run.context["redaction"] = {"masked_channels": {"left": "/tmp/x.wav"}}
run.lang = real_lang; run.profile = real_prof
calls.clear()
runner._run_transcription_phase(run, WorkflowPhase(id="transcribe-1", name="T", type="transcription"), PhaseState(phase_id="transcribe-1"))
ck("transcription phase PRIMES with config prose", len(calls) == 1 and calls[0]["initial_prompt"] == expected_prompt)

# (b) transcription phase passes None when config supplies no prose (no behaviour change)
run2 = WorkflowRun(run_id="t2", workflow_name="callcenter-qa")
run2.context["redaction"] = {"masked_channels": {"left": "/tmp/x.wav"}}
run2.lang = dataclasses.replace(real_lang, stt_prompt=""); run2.profile = dataclasses.replace(real_prof, stt_prompt="")
calls.clear()
runner._run_transcription_phase(run2, WorkflowPhase(id="transcribe-1", name="T", type="transcription"), PhaseState(phase_id="transcribe-1"))
ck("transcription phase passes None when no prose configured", len(calls) == 1 and calls[0]["initial_prompt"] is None)

# (c) redaction phase stays UNPRIMED — its ephemeral PII-location transcript must not be biased, and its
#     fail-closed confidence gate must run on the raw model. Recorder raises after recording to short-circuit
#     the heavy masking that follows the STT call.
class _Stop(Exception): pass
def _recorder_stop(path, language="bg", model_dir=None, initial_prompt=None):
    calls.append({"initial_prompt": initial_prompt, "site": "redaction"}); raise _Stop()
stt.transcribe_words = _recorder_stop
run3 = WorkflowRun(run_id="t3", workflow_name="callcenter-qa")
run3.context["ingest"] = {"channels_split": {"left": "/tmp/x.wav"}}
run3.lang = real_lang; run3.profile = real_prof
phase3 = WorkflowPhase(id="redact-1", name="R", type="audio_redaction", config={"audio_redaction": {"require_ner": False}})
calls.clear()
_orig_mkdir = Path.mkdir  # the phase mkdir's a runs/ dir before STT; no-op it so the test has no FS side effect
Path.mkdir = lambda self, *a, **k: None
try:
    runner._run_audio_redaction_phase(run3, phase3, PhaseState(phase_id="redact-1"))
except _Stop:
    pass
finally:
    Path.mkdir = _orig_mkdir
ck("redaction phase calls STT UNPRIMED (no initial_prompt kwarg value)",
   len(calls) == 1 and calls[0].get("initial_prompt") is None)

print("\nALL STT-PROMPT WIRING TESTS PASS")
