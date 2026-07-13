from __future__ import annotations


def artwork_queue_item_status(status_label: str) -> str:
    return f"Queued {status_label}"


def artwork_queue_submission_message(job_count: int, status_label: str) -> str:
    return f"Queued {job_count} {status_label} job(s)."


def custom_artwork_selected_message(kind: str, title: str) -> str:
    return f"Custom {kind} artwork selected for {title}."


def artwork_cleared_message(kind: str, title: str) -> str:
    return f"Cleared {kind} artwork for {title}."


def artwork_preview_refreshed_message(kind: str, title: str) -> str:
    return f"Refreshed {kind} artwork preview for {title}."


def artwork_editor_opened_message(kind: str, app_name: str) -> str:
    return f"Opened {kind} artwork in {app_name}."
