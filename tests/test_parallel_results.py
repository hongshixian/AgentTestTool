"""Exercise result completeness under worker failure and conflicting output."""

from agent_test_tool.parallel_results import merge_worker_results


def worker(*records):
    return {"session": {"exitstatus": 0, "reported_cases": len(records)}, "cases": list(records)}


def case(nodeid, status="通过"):
    return {"nodeid": nodeid, "status": status, "pytest_status": "passed"}


def merge(*workers):
    return merge_worker_results(
        workers, expected_nodeids=("first", "second"), run_id="test-run",
        case_suite="mother", duration_seconds=3.0,
    )


def test_merge_restores_collection_order_and_four_states():
    result = merge(worker(case("second", "不适用")), worker(case("first")))
    assert [item["nodeid"] for item in result["cases"]] == ["first", "second"]
    assert result["summary"] == {"通过": 1, "不通过": 0, "不适用": 1, "无法判定": 0, "total": 2}
    assert result["session"]["exitstatus"] == 0


def test_worker_crash_preserves_missing_case_in_report():
    result = merge(worker(case("first")))
    assert result["summary"]["total"] == 2
    assert result["cases"][1]["status"] == "不通过"
    assert result["session"]["exitstatus"] == 1


def test_duplicate_result_cannot_overwrite_failure_with_pass():
    result = merge(worker(case("first", "不通过")), worker(case("first"), case("second")))
    assert result["cases"][0]["status"] == "不通过"
    assert any("Duplicate" in error for error in result["session"]["internal_errors"])


def test_unexecuted_and_unexpected_results_fail_closed():
    record = case("first")
    record["pytest_status"] = "not_run"
    result = merge(worker(record, case("second"), case("extra")))
    assert result["summary"]["total"] == 2
    assert result["cases"][0]["status"] == "不通过"
    assert len(result["session"]["internal_errors"]) == 2


def test_crash_preserves_source_identity_and_suite_statistics():
    result = merge_worker_results(
        [], expected_nodeids=["mother[1]"], run_id="run", case_suite="mother",
        duration_seconds=1,
        collected_cases=[{
            "nodeid": "mother[1]", "test_case_id": "TC-5.1a-D1-01",
            "name": "source case", "case_level": "mother",
            "source_case_id": "TC-5.1a-D1-01", "representative_child_id": "child-id",
            "status": "无法判定", "pytest_status": "not_run",
        }],
    )
    record = result["cases"][0]
    assert record["test_case_id"] == "TC-5.1a-D1-01"
    assert record["source_case_id"] == record["test_case_id"]
    assert record["representative_child_id"] == "child-id"
    assert record["status"] == "不通过"
    assert result["summary_by_case_level"]["mother"]["不通过"] == 1
    assert result["summary_by_case_level"]["mother"]["total"] == 1


def test_failed_process_cannot_be_hidden_by_pass_only_payload():
    payload = worker(case("first"), case("second"))
    payload["session"]["exitstatus"] = 1
    result = merge(payload)
    assert result["session"]["exitstatus"] == 1
    assert result["session"]["internal_errors"]


def test_collection_count_mismatch_fails_phase():
    payload = worker(case("first"), case("second"))
    payload["session"]["collected"] = 3
    assert merge(payload)["session"]["exitstatus"] == 1
