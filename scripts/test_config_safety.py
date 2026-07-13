#!/usr/bin/env python3
"""Slice-1 config-safety: profile/language-pack loading is FAIL-CLOSED (bad config → ConfigError → HOLD).
Run: PYTHONPATH=src python3 scripts/test_config_safety.py"""
import json, sys, tempfile
from pathlib import Path
from cc_harness.config.loader import load_profile, load_language, ConfigError, Profile, Lang

def ck(n, c):
    print(f"[{'PASS' if c else 'FAIL'}] {n}"); (c or sys.exit(1))

def raises(fn):
    try:
        fn(); return False
    except ConfigError:
        return True

tmp = Path(tempfile.mkdtemp())

# --- happy path: the shipped A1 profile + bg pack load ---
p = load_profile("profiles/a1.json")
ck("valid a1 profile loads", isinstance(p, Profile) and p.client_key == "a1")
lang = load_language("bg")
ck("valid bg pack loads", isinstance(lang, Lang) and lang.iban_prefix == "BG")
ck("stt_model resolved to a path (not a bare name)", lang.stt_model_dir.endswith("faster-whisper-small") and "/" in lang.stt_model_dir)

# --- profile failures ---
ck("missing profile file → ConfigError", raises(lambda: load_profile(str(tmp/"nope.json"))))
(tmp/"bad.json").write_text("{not json", encoding="utf-8")
ck("unparseable profile → ConfigError", raises(lambda: load_profile(str(tmp/"bad.json"))))
(tmp/"partial.json").write_text(json.dumps({"schema_version":1,"client_key":"x"}), encoding="utf-8")
ck("partial profile (missing keys) → ConfigError", raises(lambda: load_profile(str(tmp/"partial.json"))))
(tmp/"ver.json").write_text(json.dumps({"schema_version":99,"client_key":"x","language":"bg",
    "agent_markers":["a"],"offer_category_id":"o","contract":{}}), encoding="utf-8")
ck("bad schema_version profile → ConfigError", raises(lambda: load_profile(str(tmp/"ver.json"))))
(tmp/"emptymarkers.json").write_text(json.dumps({"schema_version":1,"client_key":"x","language":"bg",
    "agent_markers":[],"offer_category_id":"o","contract":{"contract_key":"k"}}), encoding="utf-8")
ck("empty agent_markers → ConfigError", raises(lambda: load_profile(str(tmp/"emptymarkers.json"))))

# --- non-dict contract + bad recognizers ---
(tmp/"badcontract.json").write_text(json.dumps({"schema_version":1,"client_key":"x","language":"bg",
    "agent_markers":["a"],"offer_category_id":"o","contract":"not-a-dict"}), encoding="utf-8")
ck("non-dict contract → ConfigError", raises(lambda: load_profile(str(tmp/"badcontract.json"))))
(tmp/"badrec.json").write_text(json.dumps({"schema_version":1,"number_words":[],"number_connector":"и",
    "context_lead_ins":[],"ner_labels":[],"stt_model":"m","stt_language":"bg","recognizers":{"egn":True}}), encoding="utf-8")
ck("recognizers missing iban_prefix → ConfigError", raises(lambda: load_language("badrec", languages_dir=str(tmp))))

# --- language-pack failures ---
ck("missing language pack → ConfigError", raises(lambda: load_language("zz", languages_dir=str(tmp))))
(tmp/"partial_lang.json").write_text(json.dumps({"schema_version":1,"number_words":[]}), encoding="utf-8")
ck("partial language pack → ConfigError", raises(lambda: load_language("partial_lang", languages_dir=str(tmp))))
(tmp/"verlang.json").write_text(json.dumps({"schema_version":99,"number_words":[],"number_connector":"и",
    "context_lead_ins":[],"ner_labels":[],"stt_model":"m","stt_language":"bg",
    "recognizers":{"egn":True,"iban_prefix":"BG"}}), encoding="utf-8")
ck("bad schema_version pack → ConfigError", raises(lambda: load_language("verlang", languages_dir=str(tmp))))

print("\nALL CONFIG-SAFETY TESTS PASS")
