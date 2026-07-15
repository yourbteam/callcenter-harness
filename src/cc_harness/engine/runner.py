"""Workflow runner with phase-type dispatch.

Forked/minimized from `up_harness/engine/runner.py`. The dispatch is the same hardcoded `if/elif` on
`phase.type` (plan §0.2); later milestones add `audio_ingest`, `audio_redaction`, `transcription`,
`prosody`, `call_path_classify`, and reuse the phase-ledger evaluator. M1 supports only `noop`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from cc_harness.audio.ingest import classify_conversation, split_channels
from cc_harness.engine.workflow import WorkflowDefinition, WorkflowPhase, load_workflow
from cc_harness.state.store import PhaseState, WorkflowRun, WorkflowStateStore

# Non-running states that terminate a run without being a failure.
TERMINAL_STATUSES = {"skipped", "blocked"}


def _stt_prompt(lang: Any, profile: Any) -> str | None:
    """Concatenate locale (language pack) + client/brand (profile) STT priming PROSE into initial_prompt.

    Fed to faster-whisper's initial_prompt to improve fidelity on low-quality telephony audio. MUST be
    natural prose (a plausible transcript sentence) — a bare keyword list makes Whisper echo the terms back
    as output (verified: term lists caused prompt-echo + a >5x slowdown). Returns None when neither config
    supplies prose (no behaviour change). The prose comes only from config — no literals here — so the
    engine stays hollow.
    """
    parts = [str(getattr(lang, "stt_prompt", "") or "").strip(),
             str(getattr(profile, "stt_prompt", "") or "").strip()]
    joined = " ".join(p for p in parts if p)
    return joined or None


class WorkflowRunner:
    def __init__(self, store: WorkflowStateStore | None = None, *,
                 default_max_attempts: int = 1, retry_backoff_seconds: float = 0.0):
        self.store = store or WorkflowStateStore()
        # Per-phase retry: a phase whose handler RAISES is re-dispatched up to `max_attempts` times
        # (resolved per phase from config.max_attempts, else this default). Default 1 = no retry
        # (behaviour-preserving). Heavy I/O phases (STT/ffmpeg/parselmouth) opt in via workflow config.
        self.default_max_attempts = default_max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds

    def start(self, workflow_name: str, inputs: dict[str, Any] | None = None) -> WorkflowRun:
        workflow = load_workflow(workflow_name)
        run = WorkflowRun.create(workflow.name, context={"inputs": inputs or {}})
        self.store.save(run)
        # Load the per-client profile + language pack when supplied (fail-closed → HOLD on bad config).
        # Phases that need it (redaction/transcription/classify/prosody/phase_ledger) HOLD if it's absent;
        # noop/ingest do not require it. (Slice 1: config-driven, per-client JSON.)
        profile_path = (inputs or {}).get("profile")
        if profile_path:
            from cc_harness.config.loader import ConfigError, load_language, load_profile
            try:
                profile = load_profile(str(profile_path))
                lang = load_language(profile.language)
            except ConfigError as exc:
                run.status = "blocked"
                run.context["config"] = {"held": True, "reason": f"config error: {exc}"}
                self.store.save(run)
                return run
            # Attach as runtime attributes (NOT run.context) — the store JSON-serializes context and
            # these dataclasses/frozensets aren't serializable. Transient per-run config, not state.
            run.profile = profile  # type: ignore[attr-defined]
            run.lang = lang        # type: ignore[attr-defined]
        try:
            self._run_workflow(workflow, run)
        except Exception as exc:  # noqa: BLE001 - surface any phase failure on the run
            run.status = "failed"
            run.context["error"] = str(exc)
        self.store.save(run)
        return run

    def _run_workflow(self, workflow: WorkflowDefinition, run: WorkflowRun) -> None:
        # Honor the declared depends_on graph (topological, stable) rather than raw list order, so a
        # workflow can't be silently mis-ordered by editing the JSON. Already-topological workflows are
        # unchanged; a cycle/unknown-dep/duplicate-id raises here (fail-closed) before any phase runs.
        for phase in workflow.execution_order():
            phase_state = PhaseState(phase_id=phase.id, status="running")
            run.phases[phase.id] = phase_state
            self.store.save(run)
            # Per-phase retry on a RAISED exception (a HOLD/skip sets run.status without raising and is
            # never retried). Attempts are recorded on the ledger. Default max_attempts=1 → no retry.
            max_attempts = max(1, int(phase.config.get("max_attempts", self.default_max_attempts)))
            while True:
                phase_state.attempts += 1
                try:
                    self._dispatch_phase(run, phase, phase_state)
                    phase_state.error = None  # clear a prior transient error on a successful attempt
                    break
                except Exception as exc:  # noqa: BLE001
                    if phase_state.attempts < max_attempts:
                        phase_state.error = str(exc)
                        phase_state.status = "running"
                        self.store.save(run)
                        if self.retry_backoff_seconds:
                            time.sleep(self.retry_backoff_seconds)
                        continue
                    phase_state.status = "failed"
                    phase_state.error = str(exc)
                    run.status = "failed"
                    self.store.save(run)
                    raise
            # A phase may terminate the run early without failing (e.g. non-conversation / review HOLD).
            if run.status in TERMINAL_STATUSES:
                phase_state.status = run.status
                self.store.save(run)
                return
            phase_state.status = "completed"
            self.store.save(run)
        run.status = "completed"

    def _dispatch_phase(self, run: WorkflowRun, phase: WorkflowPhase, phase_state: PhaseState) -> None:
        """Hardcoded phase-type dispatch (plan §0.2). Raising here triggers the retry loop in
        _run_workflow; a review HOLD is signalled by setting run.status (no raise)."""
        if phase.type == "noop":
            self._run_noop_phase(run, phase, phase_state)
        elif phase.type == "audio_ingest":
            self._run_audio_ingest_phase(run, phase, phase_state)
        elif phase.type == "audio_redaction":
            self._run_audio_redaction_phase(run, phase, phase_state)
        elif phase.type == "transcription":
            self._run_transcription_phase(run, phase, phase_state)
        elif phase.type == "prosody":
            self._run_prosody_phase(run, phase, phase_state)
        elif phase.type == "call_path_classify":
            self._run_call_path_classify_phase(run, phase, phase_state)
        elif phase.type == "phase_ledger":
            self._run_phase_ledger_phase(run, phase, phase_state)
        else:
            raise ValueError(f"Unsupported phase type: {phase.type}")

    def _run_noop_phase(self, run: WorkflowRun, phase: WorkflowPhase, phase_state: PhaseState) -> None:
        phase_state.output = f"noop: {phase.id}"

    def _run_audio_ingest_phase(self, run: WorkflowRun, phase: WorkflowPhase, phase_state: PhaseState) -> None:
        inputs = run.context.get("inputs") or {}
        recording = inputs.get("recording_path")
        if not recording:
            raise ValueError("audio_ingest requires inputs.recording_path")
        cfg = phase.config.get("audio_ingest") or {}
        min_seconds = float(cfg.get("min_seconds", 8.0))
        is_conversation, reason, info = classify_conversation(recording, min_seconds=min_seconds)
        ingest: dict[str, Any] = {"recording_path": recording, **info, "is_conversation": is_conversation, "reason": reason}
        if not is_conversation:
            # FR-1.2: skip/flag — do not fabricate a downstream evaluation.
            ingest["skipped"] = True
            run.context["ingest"] = ingest
            run.status = "skipped"
            phase_state.output = f"non_conversation: {reason}"
            return
        out_dir = Path.home() / ".callcenter-harness" / "runs" / run.run_id / "ingest"
        channels = split_channels(recording, str(out_dir))
        ingest["channels_split"] = channels
        run.context["ingest"] = ingest
        phase_state.output = json.dumps({"is_conversation": True, **info, "channels": channels})

    def _run_audio_redaction_phase(self, run: WorkflowRun, phase: WorkflowPhase, phase_state: PhaseState) -> None:
        # Heavy deps imported lazily so M1/M2 (no ML libs) are unaffected.
        from cc_harness.audio import ner as ner_mod
        from cc_harness.audio import redact, stt

        split = (run.context.get("ingest") or {}).get("channels_split") or {}
        if not split:
            raise ValueError("audio_redaction requires ingest channels_split (run audio_ingest first)")
        cfg = phase.config.get("audio_redaction") or {}
        require_ner = bool(cfg.get("require_ner", True))
        min_conf = float(cfg.get("min_mean_word_probability", 0.30))
        pad = float(cfg.get("pad_seconds", 0.25))

        def hold(reason: str, extra: dict[str, Any] | None = None) -> None:
            run.status = "blocked"
            run.context["redaction"] = {"held": True, "reason": reason, **(extra or {})}
            phase_state.output = f"held_for_review: {reason}"

        # Profile + language pack are required for redaction (per-client markers + locale vocab).
        profile = getattr(run, "profile", None)
        lang = getattr(run, "lang", None)
        if profile is None or lang is None:
            return hold("no client profile / language pack (pass inputs.profile)")
        model_dir = cfg.get("stt_model_dir") or lang.stt_model_dir
        # NOTE: redaction STT is intentionally UNPRIMED. Its transcript is ephemeral (only to LOCATE PII and
        # pick the agent channel) and its mean-word-probability drives a fail-closed PII-safety gate; domain
        # priming doesn't help PII location and must not perturb that gate. Priming is applied only to the
        # eval transcript in the transcription phase.

        # Fail-closed: NER required but not vendored → HOLD, don't under-detect (NFR-6/FR-2.3).
        ner_hook = None
        if require_ner:
            if not ner_mod.models_present():
                return hold("NER models not vendored (fail-closed)")
            ner_hook = lambda t: ner_mod.ner_spans(t, lang.ner_labels)  # noqa: E731 - labels from language pack

        out_base = Path.home() / ".callcenter-harness" / "runs" / run.run_id / "redact"
        out_base.mkdir(parents=True, exist_ok=True)
        channels = [(k, v) for k, v in split.items() if k in ("left", "right", "mono")]

        # Phase 1: transcribe every raw channel (ephemeral, air-gapped) to locate PII and to determine
        # the agent vs customer role (for the §7 masking bound).
        channel_data: dict[str, tuple[str, list[dict[str, Any]], str, list[int]]] = {}
        for chan, path in channels:
            words, info = stt.transcribe_words(path, language=lang.stt_language, model_dir=model_dir)
            # Fail-closed: a missing confidence signal HOLDS (default 0.0), never passes (FR-2.3).
            if info.get("mean_word_probability", 0.0) < min_conf:
                return hold("low STT confidence", {"channel": chan, "mean_word_probability": info.get("mean_word_probability")})
            text, char_to_word = redact.build_text_and_map(words)
            channel_data[chan] = (path, words, text, char_to_word)

        # §7 masking bound: the agent channel is masked with a BOUNDED detector set (no broad context
        # over-masking) so agent script delivery stays assessable for eval dims 2-3; the customer
        # channel gets the full recall-biased union.
        agent_channel = redact.pick_agent_channel({c: d[2] for c, d in channel_data.items()}, profile.agent_markers)

        redaction_map: list[dict[str, Any]] = []
        masked: dict[str, str] = {}
        # The §7 agent-bound (skip broad context masking to keep the agent's script assessable) is only
        # valid when a SEPARATE customer channel gets the full recall union. On a single/mono channel both
        # speakers share it → force full-recall context masking there, else customer PII (names/addresses
        # after lead-in cues that NER can miss) leaks on mono recordings.
        single_channel = len(channel_data) < 2
        for chan, (path, words, text, char_to_word) in channel_data.items():
            include_context = single_channel or chan != agent_channel  # agent channel bounded only if a customer channel exists
            try:
                spans = redact.detect_spans(
                    text, number_words=lang.number_words, connector=lang.number_connector,
                    lead_ins=lang.context_lead_ins, iban_prefix=lang.iban_prefix, egn=lang.egn,
                    ner_hook=ner_hook, include_context=include_context)
                ranges = redact.spans_to_time_ranges(spans, words, char_to_word, pad=pad)
                masked_path = str(out_base / f"{chan}.masked.wav")
                redact.mask_audio(path, masked_path, ranges)  # raises (→ HOLD) if ffmpeg fails
            except Exception as exc:  # noqa: BLE001 - a broken detector/mask must HOLD, not silently pass
                return hold(f"detection/mask error: {exc}", {"channel": chan})
            masked[chan] = masked_path
            redaction_map.extend({**r, "channel": chan} for r in ranges)
            # raw transcript (`words`, `text`) is in-memory only and is dropped after this loop (§0.6).

        try:
            if "left" in masked and "right" in masked:
                compliant = str(out_base / "compliant.wav")
                redact.combine_channels(masked["left"], masked["right"], compliant)
            else:
                compliant = masked.get("mono", "")
        except Exception as exc:  # noqa: BLE001 - a failed recombine must HOLD, not emit a bad recording
            return hold(f"recombine error: {exc}")
        # Fail-closed: never report a completed redaction without an actual compliant recording on disk.
        if not compliant or not Path(compliant).is_file():
            return hold("no compliant recording produced")
        run.context["redaction"] = {
            "held": False,
            "compliant_recording": compliant,
            "masked_channels": masked,  # per-channel masked (compliant) audio paths for S3/S3'
            "agent_channel": agent_channel,  # role determined from raw transcripts (§7 masking bound)
            "redaction_map": redaction_map,  # no PII values — timestamps + category only (FR-2.4)
            "masked_spans": len(redaction_map),
        }
        phase_state.output = json.dumps({
            "held": False,
            "compliant_recording": compliant,
            "masked_spans": len(redaction_map),
            "categories": sorted({r["category"] for r in redaction_map}),
        })

    def _run_transcription_phase(self, run: WorkflowRun, phase: WorkflowPhase, phase_state: PhaseState) -> None:
        # S3: transcribe the COMPLIANT (masked) audio → eval transcript. Masked spans = silence, so the
        # transcript is PII-free by construction (plan §0.6, §4.1).
        from cc_harness.audio import stt

        masked = (run.context.get("redaction") or {}).get("masked_channels") or {}
        if not masked:
            raise ValueError("transcription requires redaction masked_channels (run audio_redaction first)")
        lang = getattr(run, "lang", None)
        if lang is None:
            run.status = "blocked"
            run.context["transcription"] = {"held": True, "reason": "no language pack (pass inputs.profile)"}
            phase_state.output = "held_for_review: no language pack"
            return
        profile = getattr(run, "profile", None)
        model_dir = (phase.config.get("transcription") or {}).get("stt_model_dir") or lang.stt_model_dir
        prompt = _stt_prompt(lang, profile)  # prose brand+telco priming for the EVAL transcript (config-sourced)
        channels_out: dict[str, Any] = {}
        text_parts: list[str] = []
        for chan, path in masked.items():
            words, info = stt.transcribe_words(path, language=lang.stt_language, model_dir=model_dir,
                                               initial_prompt=prompt)
            text = "".join(w.get("word", "") for w in words).strip()
            channels_out[chan] = {"text": text, "words": words, "duration": info.get("duration")}
            text_parts.append(f"## CHANNEL {chan}\n{text}")
        # Fail-closed: an empty eval transcript (masking left no speech, or STT produced nothing) must
        # HOLD — never hand S4 an empty subscribed output (its composer raises on empty).
        if sum(len(c.get("words") or []) for c in channels_out.values()) == 0:
            run.status = "blocked"
            run.context["transcription"] = {"channels": channels_out, "held": True,
                                            "reason": "empty eval transcript (compliant audio produced no speech)"}
            phase_state.output = "held_for_review: empty eval transcript"
            return
        run.context["transcription"] = {"channels": channels_out}
        phase_state.output = "\n\n".join(text_parts)  # PII-free; subscribed by S4

    def _run_prosody_phase(self, run: WorkflowRun, phase: WorkflowPhase, phase_state: PhaseState) -> None:
        # S3': per-turn prosody feature summary (text) over the compliant audio (requirements FR-3'.2).
        from cc_harness.audio import prosody

        masked = (run.context.get("redaction") or {}).get("masked_channels") or {}
        transcript_channels = (run.context.get("transcription") or {}).get("channels") or {}
        if not masked or not transcript_channels:
            raise ValueError("prosody requires masked_channels + transcription (run those first)")
        redaction_map = (run.context.get("redaction") or {}).get("redaction_map") or []
        lines: list[str] = []
        for chan, path in masked.items():
            words = transcript_channels.get(chan, {}).get("words") or []
            masked_ranges = [r for r in redaction_map if r.get("channel") == chan]  # T2: exclude silenced PII
            lines.extend(prosody.channel_summary(path, words, speaker=chan, masked_ranges=masked_ranges))
        # Fail-closed: never hand S4 an empty prosody output (its composer raises on empty).
        if not lines:
            run.status = "blocked"
            run.context["prosody"] = {"held": True, "reason": "empty prosody summary (no turns)"}
            phase_state.output = "held_for_review: empty prosody summary"
            return
        run.context["prosody"] = {"summary_lines": lines}
        phase_state.output = "\n".join(lines)  # text feature summary; subscribed by S4

    def _run_call_path_classify_phase(self, run: WorkflowRun, phase: WorkflowPhase, phase_state: PhaseState) -> None:
        # Identify the agent vs customer channel (agent = most script-keyword hits) and select the
        # per-branch contract, then WRITE the contract path to context (the §0.7 override the evaluator
        # reads). Also relabels channels agent/customer (FR-3.2, the M4 review #7 fix).
        from cc_harness.phase_ledger import evaluator

        cfg = phase.config.get("call_path_classify") or {}
        profile = getattr(run, "profile", None)
        if profile is None:
            run.status = "blocked"
            run.context["classify"] = {"held": True, "reason": "no client profile (pass inputs.profile)"}
            phase_state.output = "held_for_review: no client profile"
            return
        contract = evaluator.validate_contract(profile.contract)  # absorbed contract dict from the profile
        # Channel-ID keywords stay on the contract's categories_detail for now (re-homing to the profile
        # is a later slice); works unchanged for the A1 tenant.
        keywords = [k.lower() for d in contract["categories_detail"] for k in d.get("keywords", [])]

        channels = (run.context.get("transcription") or {}).get("channels") or {}
        if not channels:
            raise ValueError("call_path_classify requires transcription channels")

        def score(text: str) -> int:
            low = text.lower()
            return sum(low.count(kw) for kw in keywords)

        ranked = sorted(channels.items(), key=lambda kv: score(kv[1].get("text", "")), reverse=True)
        top_score = score(ranked[0][1].get("text", ""))
        # Fail-closed: if no channel shows script keywords, we cannot tell agent from customer — HOLD
        # rather than mislabel and score the wrong transcript (M5 review #4).
        if top_score == 0:
            run.status = "blocked"
            run.context["classify"] = {"held": True, "reason": "cannot identify agent channel (no script keywords in any channel)"}
            phase_state.output = "held_for_review: agent channel unidentifiable"
            return
        agent_channel = ranked[0][0]
        customer_channel = ranked[1][0] if len(ranked) > 1 else None
        classify = {
            "call_path": str(cfg.get("call_path") or profile.call_path),
            "agent_channel": agent_channel,
            "customer_channel": customer_channel,
        }
        run.context["classify"] = classify
        run.context["evaluation_contract"] = contract  # §0.7 override: the contract DICT (not a path)
        phase_state.output = json.dumps(classify)

    def _run_phase_ledger_phase(self, run: WorkflowRun, phase: WorkflowPhase, phase_state: PhaseState) -> None:
        # W3 evaluation. Contract path comes from the classify context override (§0.7), else phase config.
        from cc_harness.phase_ledger import evaluator

        cfg = phase.config.get("phase_ledger") or {}
        profile = getattr(run, "profile", None)
        if profile is None:
            run.status = "blocked"
            run.context["evaluation"] = {"held": True, "reason": "no client profile (pass inputs.profile)"}
            phase_state.output = "held_for_review: no client profile"
            return
        contract = evaluator.validate_contract(run.context.get("evaluation_contract") or profile.contract)
        offer_category_id = profile.offer_category_id

        # Score the AGENT channel transcript for script adherence (the agent recites the script).
        classify = run.context.get("classify") or {}
        channels = (run.context.get("transcription") or {}).get("channels") or {}
        agent_channel = classify.get("agent_channel")
        source_text = (channels.get(agent_channel, {}) or {}).get("text", "") if agent_channel else ""
        if not source_text:
            raise ValueError("phase_ledger found no agent transcript to score")
        # ClientFiles gap checks need word timestamps + duration (agent) and the customer channel (G3).
        agent_words = (channels.get(agent_channel, {}) or {}).get("words") or []
        duration = (channels.get(agent_channel, {}) or {}).get("duration")
        customer_channel = classify.get("customer_channel")
        customer_text = (channels.get(customer_channel, {}) or {}).get("text", "") if customer_channel else ""

        prosody_lines = (run.context.get("prosody") or {}).get("summary_lines") or []
        inputs = run.context.get("inputs") or {}
        execution_mode = str(cfg.get("execution_mode") or inputs.get("execution_mode") or "deterministic")

        # The generic RUBRIC-INTERPRETER over profile.rubric → per-criterion checklist + two-tier severity
        # (the M3 reframe). DETERMINISTIC = agent-side DET/DET-MAP checks (Slice 2). COMMAND additionally
        # calls the offline judge ONCE and feeds its verdict + the customer channel, so the CMD checks
        # (deal/path/objection-match) resolve (Slice 3). Prosody/intonation (M2) preserved in both.
        from cc_harness.phase_ledger.rubric import run_rubric

        redaction_map = (run.context.get("redaction") or {}).get("redaction_map") or []
        mandated = list(contract.get("required_phrasings") or []) + list(contract.get("ask_for_decision_phrases") or [])
        ctx: dict[str, Any] = {"source_text": source_text, "agent_words": agent_words,
                               "redaction_map": redaction_map, "mandated_regions": mandated,
                               "duration": duration, "channel": agent_channel}

        if execution_mode == "command":
            from cc_harness.phase_ledger.executor import CommandRoleExecutor
            # customer_text feeds the judge; customer_channel lets slot_present resolve the CUSTOMER role
            # symbolically (G6 courier-capture). Customer word-timestamps aren't needed — the courier
            # anchor phrase is spoken by the AGENT, and the captured slot comes from the redaction map.
            ctx.update({"customer_text": customer_text, "customer_channel": customer_channel})
            # Call the judge ONCE — only when a customer channel exists; on mono there is none, so the CMD
            # checks stay indeterminate (→ review_needed), never a silent no_deal (M3 §14 R-b / plan D8).
            if customer_channel:
                cmd_checks = [c for c in profile.rubric
                              if c.get("primitive") in ("judge_check", "deal_detect", "path_select") or c.get("question")]
                try:
                    executor = CommandRoleExecutor.from_env()  # fail-closed if CC_HARNESS_AGENT_COMMAND unset
                    ctx["judge"] = evaluator.judge_call(cmd_checks, source_text, "\n".join(prosody_lines),
                                                        executor, customer_text=customer_text)
                except Exception as exc:  # noqa: BLE001 - unconfigured/failed judge must HOLD, not fake a score
                    run.status = "blocked"
                    run.context["evaluation"] = {"held": True, "reason": f"command-mode judge: {exc}"}
                    phase_state.output = f"held_for_review: command-mode judge: {exc}"
                    return

        rubric_out = run_rubric(profile.rubric, ctx)
        _pt = contract.get("prosody_thresholds") or {}  # optional; else evaluator defaults (T3: client-calibrated)
        intonation = evaluator.evaluate_prosody(
            prosody_lines, speaker=str(agent_channel),
            **{k: _pt[k] for k in ("min_energy_db", "min_pace_wps", "max_pace_wps", "min_pitch_std_hz") if k in _pt})
        self._emit_checklist(run, phase_state, contract, str(agent_channel), execution_mode, rubric_out, intonation)

    def _emit_checklist(self, run: WorkflowRun, phase_state: PhaseState, contract: dict[str, Any],
                        agent_channel: str, mode: str, rubric_out: dict[str, Any],
                        intonation: dict[str, Any]) -> None:
        """Write the per-criterion checklist evaluation (shared by deterministic + command modes)."""
        run.context["evaluation"] = {
            "mode": mode,
            "contract_key": contract["contract_key"],
            "checklist": rubric_out["checklist"],
            "violations": rubric_out["violations"],
            "advisories": rubric_out["advisories"],
            "review_needed": rubric_out["review_needed"],
            "intonation": intonation,
        }
        cl = rubric_out["checklist"]
        met = sum(1 for r in cl if r["status"] == "met")
        phase_state.output = (
            f"# Checklist — {contract['contract_key']} ({mode}, agent {agent_channel})\n"
            + f"{met}/{len(cl)} met | {len(rubric_out['violations'])} violations | "
            + f"{len(rubric_out['advisories'])} advisories | {len(rubric_out['review_needed'])} need review\n"
            + "".join(f"- [{r['status']}] {r['id']} ({r['tier']})\n" for r in cl)
            + f"\n## Delivery (agent {agent_channel})\n"
            + f"- mean pace: {intonation['mean_pace_wps']} wps; mean energy: {intonation['mean_energy_db']} dB\n"
            + f"- flags: {', '.join(intonation['flags']) or 'none'}"
        )
