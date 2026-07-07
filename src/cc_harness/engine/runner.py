"""Workflow runner with phase-type dispatch.

Forked/minimized from `up_harness/engine/runner.py`. The dispatch is the same hardcoded `if/elif` on
`phase.type` (plan §0.2); later milestones add `audio_ingest`, `audio_redaction`, `transcription`,
`prosody`, `call_path_classify`, and reuse the phase-ledger evaluator. M1 supports only `noop`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cc_harness.audio.ingest import classify_conversation, split_channels
from cc_harness.engine.workflow import WorkflowDefinition, WorkflowPhase, load_workflow
from cc_harness.state.store import PhaseState, WorkflowRun, WorkflowStateStore

# Non-running states that terminate a run without being a failure.
TERMINAL_STATUSES = {"skipped", "blocked"}


class WorkflowRunner:
    def __init__(self, store: WorkflowStateStore | None = None):
        self.store = store or WorkflowStateStore()

    def start(self, workflow_name: str, inputs: dict[str, Any] | None = None) -> WorkflowRun:
        workflow = load_workflow(workflow_name)
        run = WorkflowRun.create(workflow.name, context={"inputs": inputs or {}})
        self.store.save(run)
        try:
            self._run_workflow(workflow, run)
        except Exception as exc:  # noqa: BLE001 - surface any phase failure on the run
            run.status = "failed"
            run.context["error"] = str(exc)
        self.store.save(run)
        return run

    def _run_workflow(self, workflow: WorkflowDefinition, run: WorkflowRun) -> None:
        for phase in workflow.phases:
            phase_state = PhaseState(phase_id=phase.id, status="running")
            run.phases[phase.id] = phase_state
            self.store.save(run)
            try:
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
                # A phase may terminate the run early without failing (e.g. non-conversation).
                if run.status in TERMINAL_STATUSES:
                    phase_state.status = run.status
                    self.store.save(run)
                    return
                phase_state.status = "completed"
            except Exception as exc:  # noqa: BLE001
                phase_state.status = "failed"
                phase_state.error = str(exc)
                run.status = "failed"
                self.store.save(run)
                raise
            self.store.save(run)
        run.status = "completed"

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
        model_dir = cfg.get("stt_model_dir")

        def hold(reason: str, extra: dict[str, Any] | None = None) -> None:
            run.status = "blocked"
            run.context["redaction"] = {"held": True, "reason": reason, **(extra or {})}
            phase_state.output = f"held_for_review: {reason}"

        # Fail-closed: NER required but not vendored → HOLD, don't under-detect (NFR-6/FR-2.3).
        ner_hook = None
        if require_ner:
            if not ner_mod.models_present():
                return hold("NER models not vendored (fail-closed)")
            ner_hook = ner_mod.ner_spans

        out_base = Path.home() / ".callcenter-harness" / "runs" / run.run_id / "redact"
        out_base.mkdir(parents=True, exist_ok=True)
        channels = [(k, v) for k, v in split.items() if k in ("left", "right", "mono")]

        # Phase 1: transcribe every raw channel (ephemeral, air-gapped) to locate PII and to determine
        # the agent vs customer role (for the §7 masking bound).
        channel_data: dict[str, tuple[str, list[dict[str, Any]], str, list[int]]] = {}
        for chan, path in channels:
            words, info = stt.transcribe_words(path, model_dir=model_dir) if model_dir else stt.transcribe_words(path)
            # Fail-closed: a missing confidence signal HOLDS (default 0.0), never passes (FR-2.3).
            if info.get("mean_word_probability", 0.0) < min_conf:
                return hold("low STT confidence", {"channel": chan, "mean_word_probability": info.get("mean_word_probability")})
            text, char_to_word = redact.build_text_and_map(words)
            channel_data[chan] = (path, words, text, char_to_word)

        # §7 masking bound: the agent channel is masked with a BOUNDED detector set (no broad context
        # over-masking) so agent script delivery stays assessable for eval dims 2-3; the customer
        # channel gets the full recall-biased union.
        agent_channel = redact.pick_agent_channel({c: d[2] for c, d in channel_data.items()})

        redaction_map: list[dict[str, Any]] = []
        masked: dict[str, str] = {}
        for chan, (path, words, text, char_to_word) in channel_data.items():
            include_context = chan != agent_channel  # agent channel: bounded
            try:
                spans = redact.detect_spans(text, ner_hook=ner_hook, include_context=include_context)
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
        model_dir = (phase.config.get("transcription") or {}).get("stt_model_dir")
        channels_out: dict[str, Any] = {}
        text_parts: list[str] = []
        for chan, path in masked.items():
            words, info = stt.transcribe_words(path, model_dir=model_dir) if model_dir else stt.transcribe_words(path)
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
        lines: list[str] = []
        for chan, path in masked.items():
            words = transcript_channels.get(chan, {}).get("words") or []
            lines.extend(prosody.channel_summary(path, words, speaker=chan))
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
        contract_path = str(cfg.get("contract_path") or "contracts/callcenter-newplan-esign.json")
        contract = evaluator.load_contract(contract_path)
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
            "call_path": str(cfg.get("call_path") or "newplan_esign"),
            "agent_channel": agent_channel,
            "customer_channel": customer_channel,
            "contract_path": contract_path,
        }
        run.context["classify"] = classify
        run.context["evaluation_contract_path"] = contract_path  # §0.7 context override
        phase_state.output = json.dumps(classify)

    def _run_phase_ledger_phase(self, run: WorkflowRun, phase: WorkflowPhase, phase_state: PhaseState) -> None:
        # W3 evaluation. Contract path comes from the classify context override (§0.7), else phase config.
        from cc_harness.phase_ledger import evaluator

        cfg = phase.config.get("phase_ledger") or {}
        contract_path = run.context.get("evaluation_contract_path") or cfg.get("contract_path")
        if not contract_path:
            raise ValueError("phase_ledger requires a contract path (from classify override or config)")
        contract = evaluator.load_contract(str(contract_path))

        # Score the AGENT channel transcript for script adherence (the agent recites the script).
        classify = run.context.get("classify") or {}
        channels = (run.context.get("transcription") or {}).get("channels") or {}
        agent_channel = classify.get("agent_channel")
        source_text = (channels.get(agent_channel, {}) or {}).get("text", "") if agent_channel else ""
        if not source_text:
            raise ValueError("phase_ledger found no agent transcript to score")

        result = evaluator.evaluate(contract, source_text)
        # Intonation/delivery proxy over the agent's prosody summary (resolves M5 review #9 — prosody
        # is now consumed). Nuanced scoring is deferred to command-backed model roles.
        prosody_lines = (run.context.get("prosody") or {}).get("summary_lines") or []
        intonation = evaluator.evaluate_prosody(prosody_lines, speaker=str(agent_channel))
        run.context["evaluation"] = {
            "contract_key": result.ledger["contract_key"],
            "manager_summary": result.ledger["manager_summary"],
            "findings": result.ledger["findings"],
            "intonation": intonation,
        }
        phase_state.output = (
            result.output_text
            + f"\n\n## Delivery (agent {agent_channel})\n"
            + f"- mean pace: {intonation['mean_pace_wps']} wps; mean energy: {intonation['mean_energy_db']} dB\n"
            + f"- flags: {', '.join(intonation['flags']) or 'none'}"
        )
