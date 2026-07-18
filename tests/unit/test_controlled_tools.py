from __future__ import annotations

import pytest

from pliris.tools.registry import (
    ControlledToolRegistry,
    ToolExecutionError,
)


def test_registry_lists_only_allowlisted_tools() -> None:
    names = [tool["name"] for tool in ControlledToolRegistry().list_tools()]

    assert names == [
        "percentage_change",
        "weighted_score",
    ]


def test_percentage_change_returns_structured_result() -> None:
    result = ControlledToolRegistry().execute(
        tool_name="percentage_change",
        arguments={
            "old_value": "80",
            "new_value": "100",
        },
    )

    assert result.to_dict() == {
        "tool_name": "percentage_change",
        "output": {
            "old_value": 80.0,
            "new_value": 100.0,
            "absolute_change": 20.0,
            "percentage_change": 25.0,
        },
    }


def test_percentage_change_handles_negative_baseline() -> None:
    result = ControlledToolRegistry().execute(
        tool_name="percentage_change",
        arguments={
            "old_value": "-50",
            "new_value": "-25",
        },
    )

    assert result.output["absolute_change"] == 25.0
    assert result.output["percentage_change"] == 50.0


def test_percentage_change_rejects_zero_baseline() -> None:
    with pytest.raises(
        ToolExecutionError,
        match="old_value of zero",
    ):
        ControlledToolRegistry().execute(
            tool_name="percentage_change",
            arguments={
                "old_value": 0,
                "new_value": 5,
            },
        )


def test_weighted_score_returns_weighted_average() -> None:
    result = ControlledToolRegistry().execute(
        tool_name="weighted_score",
        arguments={
            "items": [
                {"score": 8, "weight": 3},
                {"score": 5, "weight": 1},
            ],
        },
    )

    assert result.to_dict() == {
        "tool_name": "weighted_score",
        "output": {
            "weighted_score": 7.25,
            "total_weight": 4.0,
            "item_count": 2,
        },
    }


def test_registry_rejects_unknown_tool() -> None:
    with pytest.raises(
        ToolExecutionError,
        match="not allowlisted",
    ):
        ControlledToolRegistry().execute(
            tool_name="run_shell_command",
            arguments={"command": "whoami"},
        )


def test_registry_rejects_blank_tool_name() -> None:
    with pytest.raises(
        ToolExecutionError,
        match="must not be blank",
    ):
        ControlledToolRegistry().execute(
            tool_name="   ",
            arguments={},
        )


def test_registry_rejects_extra_arguments() -> None:
    with pytest.raises(
        ToolExecutionError,
        match="invalid arguments",
    ):
        ControlledToolRegistry().execute(
            tool_name="percentage_change",
            arguments={
                "old_value": 10,
                "new_value": 12,
                "command": "unexpected",
            },
        )


def test_registry_rejects_invalid_weight() -> None:
    with pytest.raises(
        ToolExecutionError,
        match="invalid arguments",
    ):
        ControlledToolRegistry().execute(
            tool_name="weighted_score",
            arguments={
                "items": [
                    {"score": 10, "weight": 0},
                ],
            },
        )


def test_registry_rejects_excessive_item_count() -> None:
    with pytest.raises(
        ToolExecutionError,
        match="invalid arguments",
    ):
        ControlledToolRegistry().execute(
            tool_name="weighted_score",
            arguments={
                "items": [{"score": 1, "weight": 1} for _ in range(101)],
            },
        )
