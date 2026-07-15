"""Human-readable scorecard: a generic report-model builder + text renderer over the evaluation.

All human labels/prose are supplied from config (profile `scorecard_presentation` + language `status_labels`)
so the engine stays hollow (no client/locale literals in `src/`). See
docs/research/scorecard-human-structure-research.md and docs/implementation-plans/scorecard-human-render-plan.md.
"""
from cc_harness.report.model import build_report_model
from cc_harness.report.render_text import render_text

__all__ = ["build_report_model", "render_text"]
