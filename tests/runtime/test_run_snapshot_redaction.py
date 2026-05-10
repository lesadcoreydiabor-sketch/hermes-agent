from hermes_cli.run_inspector import (
    ActiveToolSnapshot,
    PRIVACY_FLAGS,
    RunSnapshot,
    classify_snapshot_privacy,
    summarize_tool_arguments,
)


SECRET = "OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz123456"
RAW_PROMPT = "please summarize this confidential acquisition plan"
FILE_BODY = "customer contract body with private pricing terms"
RAW_LOG = "Traceback line with ghp_abcdefghijklmnopqrstuvwxyz123456"


def _render(value):
    return str(value)


def test_string_tool_args_are_summarized_without_raw_prompt_or_secret():
    summary = summarize_tool_arguments(f"{RAW_PROMPT}\n{SECRET}")
    rendered = _render(summary)

    assert summary == {
        "type": "string",
        "char_count": len(f"{RAW_PROMPT}\n{SECRET}"),
        "privacy": "redacted",
    }
    assert RAW_PROMPT not in rendered
    assert "abcdefghijklmnopqrstuvwxyz" not in rendered
    assert "OPENAI_API_KEY" not in rendered


def test_dict_tool_args_omit_nested_values_file_bodies_logs_and_secrets():
    summary = summarize_tool_arguments({
        "prompt": RAW_PROMPT,
        "file_body": FILE_BODY,
        "logs": RAW_LOG,
        "nested": {
            "token": "ghp_abcdefghijklmnopqrstuvwxyz123456",
            "content": "private nested content",
        },
    })
    rendered = _render(summary)

    assert summary == {
        "type": "object",
        "key_count": 4,
        "keys": ["file_body", "logs", "nested", "prompt"],
        "truncated": False,
        "privacy": "redacted",
        "value_types": {
            "file_body": "string",
            "logs": "string",
            "nested": "object",
            "prompt": "string",
        },
    }
    assert RAW_PROMPT not in rendered
    assert FILE_BODY not in rendered
    assert RAW_LOG not in rendered
    assert "abcdefghijklmnopqrstuvwxyz" not in rendered
    assert "private nested content" not in rendered


def test_non_dict_tool_args_are_summarized_by_shape_only():
    summary = summarize_tool_arguments([
        RAW_PROMPT,
        {"secret": SECRET},
        42,
        None,
    ])
    rendered = _render(summary)

    assert summary == {
        "type": "array",
        "item_count": 4,
        "privacy": "redacted",
        "item_types": ["integer", "null", "object", "string"],
    }
    assert RAW_PROMPT not in rendered
    assert "abcdefghijklmnopqrstuvwxyz" not in rendered


def test_large_tool_arg_objects_are_truncated_without_values():
    args = {f"key_{idx:02d}": f"value-{idx}-{SECRET}" for idx in range(25)}
    summary = summarize_tool_arguments(args)
    rendered = _render(summary)

    assert summary["type"] == "object"
    assert summary["key_count"] == 25
    assert summary["keys"] == [f"key_{idx:02d}" for idx in range(20)]
    assert summary["truncated"] is True
    assert len(summary["value_types"]) == 20
    assert "value-0" not in rendered
    assert "abcdefghijklmnopqrstuvwxyz" not in rendered


def test_active_tool_snapshot_summarizes_raw_arguments():
    payload = ActiveToolSnapshot.from_mapping({
        "name": "shell",
        "call_id": "call-1",
        "duration_ms": 50,
        "arguments": {
            "command": f"echo {SECRET}",
            "prompt": RAW_PROMPT,
        },
    }).to_dict()
    rendered = _render(payload)

    assert payload["args_summary"] == {
        "type": "object",
        "key_count": 2,
        "keys": ["command", "prompt"],
        "truncated": False,
        "privacy": "redacted",
        "value_types": {
            "command": "string",
            "prompt": "string",
        },
    }
    assert "arguments" not in payload
    assert RAW_PROMPT not in rendered
    assert "abcdefghijklmnopqrstuvwxyz" not in rendered


def test_snapshot_privacy_classification_covers_every_exposed_field():
    snapshot = RunSnapshot(
        run_id="run-privacy",
        source="cli",
        status="executing_tool",
        active_tool=ActiveToolSnapshot.from_mapping({
            "name": "shell",
            "args": {"prompt": RAW_PROMPT},
        }),
        privacy_flags=("safe", "redacted", "local_only"),
    )
    payload = snapshot.to_dict()
    classification = classify_snapshot_privacy(snapshot)

    assert sorted(classification.keys()) == sorted(payload.keys())
    assert set(classification.values()) <= PRIVACY_FLAGS
    assert classification["active_tool"] == "redacted"
    assert classification["reason"] == "redacted"
    assert classification["workspace"] == "local_only"
    assert classification["tool_health"] == "safe"
    assert classification["mcp_health"] == "local_only"
