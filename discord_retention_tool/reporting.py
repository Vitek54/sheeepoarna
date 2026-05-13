"""Reporting guidance.

Discord's in-app reporting surfaces are for user-driven, contextual reports.
This project intentionally does not automate Report V3 or any mass-reporting
workflow, because that can spam platform trust-and-safety systems and is not
part of the public bot-token moderation API.
"""

from __future__ import annotations


def report_v3_research_note() -> str:
    return (
        "Automated Report V3/mass-reporting is intentionally not implemented. "
        "Use Discord's official in-app reporting flow for individual policy "
        "violations, and keep moderation evidence exports local for human review."
    )
