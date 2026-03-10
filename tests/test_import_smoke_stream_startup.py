def test_import_app_main_smoke() -> None:
    import app.main  # noqa: F401


def test_import_stream_entrypoint_smoke() -> None:
    from app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop_main import (  # noqa: E501,F401
        run_pension_chat_stream,
    )
