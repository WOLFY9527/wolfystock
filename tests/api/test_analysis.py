from src.services.task_queue import AnalysisTaskQueue


def test_progress_status_updates_include_meaningful_data_stages():
    execution = None
    for stage, detail in [
        ("detecting_market", "Detecting market"),
        ("loading_quote", "Loading quote"),
        ("loading_fundamentals", "Loading fundamentals"),
        ("loading_news", "Loading news"),
        ("analyzing_signals", "Running AI analysis"),
    ]:
        execution = AnalysisTaskQueue._merge_execution_stage(
            execution,
            stage_key=stage,
            detail=detail,
        )

    steps = {step["key"]: step for step in execution["steps"]}

    assert steps["data_fetch"]["status"] == "ok"
    assert steps["data_fetch"]["detail"] == "Loading news"
    assert steps["ai_analysis"]["status"] == "partial"
    assert steps["ai_analysis"]["detail"] == "Running AI analysis"
