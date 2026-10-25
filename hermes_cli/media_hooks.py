"""CLI implementations of the store's media hooks."""

from typing import Any

from gateway import session_ingress_media
from tools import tool_result_storage


class CliMediaHooks:
    def admission_media_references(self, payload: Any) -> list:
        return session_ingress_media.admission_media_references(payload)

    def hosted_document_references(self, request_id: str, payload: Any) -> list:
        return session_ingress_media.hosted_document_references(request_id, payload)

    def release_unheld_media(self, db: Any, references: list) -> Any:
        return session_ingress_media.release_unheld_media(db, references)

    def spillover_sql_filter(self) -> str:
        return tool_result_storage.SPILLOVER_SQL_FILTER

    def spillover_names_in_text(self, content: Any, api_content: Any) -> list:
        return tool_result_storage.spillover_names_in_text(content, api_content)

    def referenced_spillover_names(self, spill_dir: Any) -> Any:
        return tool_result_storage.referenced_spillover_names(spill_dir)


media_hooks = CliMediaHooks()
