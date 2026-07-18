from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ToolExecutionError(RuntimeError):
    """Raised when a controlled tool cannot be executed safely."""


class PercentageChangeInput(BaseModel):
    """Input contract for percentage-change calculations."""

    model_config = ConfigDict(extra="forbid")

    old_value: Decimal
    new_value: Decimal


class WeightedScoreItem(BaseModel):
    """One weighted scoring item."""

    model_config = ConfigDict(extra="forbid")

    score: Decimal = Field(ge=0)
    weight: Decimal = Field(gt=0)


class WeightedScoreInput(BaseModel):
    """Input contract for weighted-score calculations."""

    model_config = ConfigDict(extra="forbid")

    items: list[WeightedScoreItem] = Field(min_length=1, max_length=100)


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Structured result returned by every controlled tool."""

    tool_name: str
    output: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "output": self.output,
        }


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Allowlisted deterministic function-tool definition."""

    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[BaseModel], dict[str, Any]]

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
        }


def _decimal_to_float(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.000001")))


def _percentage_change(payload: BaseModel) -> dict[str, Any]:
    data = PercentageChangeInput.model_validate(payload)

    if data.old_value == 0:
        raise ToolExecutionError("percentage_change cannot use an old_value of zero")

    delta = data.new_value - data.old_value
    percentage = (delta / abs(data.old_value)) * Decimal("100")

    return {
        "old_value": _decimal_to_float(data.old_value),
        "new_value": _decimal_to_float(data.new_value),
        "absolute_change": _decimal_to_float(delta),
        "percentage_change": _decimal_to_float(percentage),
    }


def _weighted_score(payload: BaseModel) -> dict[str, Any]:
    data = WeightedScoreInput.model_validate(payload)

    total_weight = sum(
        (item.weight for item in data.items),
        start=Decimal("0"),
    )
    weighted_total = sum(
        (item.score * item.weight for item in data.items),
        start=Decimal("0"),
    )
    result = weighted_total / total_weight

    return {
        "weighted_score": _decimal_to_float(result),
        "total_weight": _decimal_to_float(total_weight),
        "item_count": len(data.items),
    }


_TOOL_DEFINITIONS: Final[tuple[ToolDefinition, ...]] = (
    ToolDefinition(
        name="percentage_change",
        description=(
            "Calculate absolute and percentage change between two non-zero baseline values."
        ),
        input_model=PercentageChangeInput,
        handler=_percentage_change,
    ),
    ToolDefinition(
        name="weighted_score",
        description=("Calculate a weighted average score from positive weights."),
        input_model=WeightedScoreInput,
        handler=_weighted_score,
    ),
)


class ControlledToolRegistry:
    """Explicit allowlist for deterministic, side-effect-free tools."""

    def __init__(
        self,
        definitions: tuple[ToolDefinition, ...] = _TOOL_DEFINITIONS,
    ) -> None:
        self._definitions: Mapping[str, ToolDefinition] = {
            definition.name: definition for definition in definitions
        }

        if len(self._definitions) != len(definitions):
            raise ValueError("tool names must be unique")

    def list_tools(self) -> list[dict[str, Any]]:
        return [self._definitions[name].schema() for name in sorted(self._definitions)]

    def execute(
        self,
        *,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> ToolResult:
        normalized_name = tool_name.strip()
        if not normalized_name:
            raise ToolExecutionError("tool_name must not be blank")

        definition = self._definitions.get(normalized_name)
        if definition is None:
            raise ToolExecutionError(f"tool is not allowlisted: {normalized_name}")

        try:
            payload = definition.input_model.model_validate(dict(arguments))
            output = definition.handler(payload)
        except ValidationError as exc:
            raise ToolExecutionError(f"invalid arguments for {normalized_name}") from exc
        except (InvalidOperation, ZeroDivisionError) as exc:
            raise ToolExecutionError(f"unable to execute {normalized_name}") from exc

        return ToolResult(
            tool_name=normalized_name,
            output=output,
        )
