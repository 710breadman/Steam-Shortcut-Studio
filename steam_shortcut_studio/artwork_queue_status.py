from __future__ import annotations


def artwork_queue_item_status(status_label: str) -> str:
    return f"Queued {status_label}"


def artwork_queue_submission_message(job_count: int, status_label: str) -> str:
    return f"Queued {job_count} {status_label} job(s)."
