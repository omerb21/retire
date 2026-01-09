from dataclasses import dataclass

@dataclass
class _OrchestrationResult:
    final_reply: str
    forced_user_prefix: str
    qa_summary_required: bool
    report_open_path: str | None
    current_step: int
    max_steps: int


