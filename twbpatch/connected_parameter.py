from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from lxml import etree as ET

from .connected import get_display_name, _matches, _validate_get_args
from .context import UNSET, ConnectedModel, WorkbookContext, _UnsetType, xml_equal
from .errors import DetachedModelError, ResourceInUseError, UnsupportedFeatureError
from .references import field_references


_DATATYPES = {"string", "integer", "real", "boolean", "date", "datetime"}
_DOMAIN_TYPES = {"any", "list", "range"}


def _clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('""', '"')
    if len(value) >= 2 and value[0] == value[-1] == "#":
        return value[1:-1]
    return value


def _parameter_id(name: str) -> str:
    inner = name[1:-1] if name.startswith("[") and name.endswith("]") else name
    return f"[{inner}]"


def _serialize_value(datatype: str, value: Any) -> tuple[str, str]:
    if value is None:
        raise ValueError("value cannot be None")
    if datatype == "string":
        public = str(value)
        return f'"{public.replace(chr(34), chr(34) * 2)}"', public
    if datatype == "integer":
        if isinstance(value, bool):
            raise TypeError("integer value must not be bool")
        if isinstance(value, float) and not value.is_integer():
            raise ValueError(f"invalid integer value: {value}")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid integer value: {value}") from error
        return str(parsed), str(parsed)
    if datatype == "real":
        if isinstance(value, bool):
            raise TypeError("real value must not be bool")
        try:
            parsed = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid real value: {value}") from error
        if not math.isfinite(parsed):
            raise ValueError("real value must be finite")
        public = str(parsed)
        return public, public
    if datatype == "boolean":
        if isinstance(value, bool):
            public = "true" if value else "false"
        elif isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            public = value.strip().lower()
        else:
            raise ValueError(f"invalid boolean value: {value}")
        return public, public
    if datatype == "date":
        try:
            parsed = value.date() if isinstance(value, datetime) else value
            if not isinstance(parsed, date):
                parsed = date.fromisoformat(str(value).strip("#"))
        except ValueError as error:
            raise ValueError(f"invalid date value: {value}") from error
        public = parsed.isoformat()
        return f"#{public}#", public
    if datatype == "datetime":
        try:
            parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).strip("#"))
        except ValueError as error:
            raise ValueError(f"invalid datetime value: {value}") from error
        public = parsed.isoformat(sep=" ")
        return f"#{public}#", public
    raise ValueError(f"unsupported datatype: {datatype}")


def _comparison_value(datatype: str, value: Any) -> Any:
    raw, public = _serialize_value(datatype, value)
    if datatype == "integer":
        return int(public)
    if datatype == "real":
        return float(public)
    if datatype == "date":
        return date.fromisoformat(public)
    if datatype == "datetime":
        return datetime.fromisoformat(public)
    return public


def _allowable_values(column_el: ET._Element) -> list[dict[str, str | None]]:
    return [
        {
            "value": _clean_value(element.get("value")),
            "alias": element.get("alias"),
        }
        for element in column_el.xpath(
            "./*[local-name()='members']/*[local-name()='member']"
        )
    ]


def _direct_child(parent: ET._Element, local_name: str) -> ET._Element | None:
    return next((child for child in parent if ET.QName(child).localname == local_name), None)


class TwbParameter(ConnectedModel):
    def __init__(self, context: WorkbookContext, parameter_id: str):
        super().__init__(context)
        self._id = parameter_id

    def _resolve_element(self) -> ET._Element:
        self._ensure_attached()
        hits = self._context.tree.getroot().xpath(
            "/workbook/datasources/datasource[@name='Parameters']/column[@name=$id]",
            id=self._id,
        )
        if not hits:
            self._detach()
            raise DetachedModelError(f"parameter is detached: {self._id}")
        return hits[0]

    @property
    def id(self) -> str:
        self._resolve_element()
        return self._id

    @property
    def name(self) -> str:
        return get_display_name(self._resolve_element())

    @property
    def datatype(self) -> str | None:
        return self._resolve_element().get("datatype")

    @property
    def value(self) -> str | None:
        return _clean_value(self._resolve_element().get("value"))

    @property
    def value_display(self) -> str | None:
        element = self._resolve_element()
        value = self.value
        if element.get("alias"):
            return element.get("alias")
        for item in [*self.aliases, *self.allowable_values]:
            if item["value"] == value and item["alias"] is not None:
                return item["alias"]
        return value

    @property
    def domain_type(self) -> str | None:
        return self._resolve_element().get("param-domain-type")

    @property
    def allowable_values(self) -> list[dict[str, str | None]]:
        return _allowable_values(self._resolve_element())

    @property
    def aliases(self) -> list[dict[str, str | None]]:
        return [
            {"value": _clean_value(alias.get("key")), "alias": alias.get("value")}
            for alias in self._resolve_element().xpath(
                "./*[local-name()='aliases']/*[local-name()='alias']"
            )
        ]

    @property
    def default_value_field(self) -> str | None:
        return self._resolve_element().get("default-value-field")

    @property
    def min_value(self) -> str | None:
        ranges = self._resolve_element().xpath("./*[local-name()='range']")
        return _clean_value(ranges[0].get("min")) if ranges else None

    @property
    def max_value(self) -> str | None:
        ranges = self._resolve_element().xpath("./*[local-name()='range']")
        return _clean_value(ranges[0].get("max")) if ranges else None

    @property
    def step_size(self) -> str | None:
        ranges = self._resolve_element().xpath("./*[local-name()='range']")
        return _clean_value(ranges[0].get("granularity")) if ranges else None

    @property
    def hidden(self) -> bool:
        return (self._resolve_element().get("hidden") or "false").lower() == "true"

    def update(
        self,
        *,
        value: Any | _UnsetType = UNSET,
        allow_hidden: bool = False,
    ) -> TwbParameter:
        if not isinstance(allow_hidden, bool):
            raise TypeError("allow_hidden must be bool")
        parameter_el = self._resolve_element()
        if value is UNSET:
            return self
        if self.hidden and not allow_hidden:
            raise ValueError("hidden parameter update requires allow_hidden=True")
        if value is None:
            raise ValueError("value cannot be None")

        datatype = self.datatype or "string"
        serialized, clean_value = _serialize_value(datatype, value)
        allowable = [item["value"] for item in self.allowable_values]
        if self.domain_type == "list" and allowable and clean_value not in allowable:
            raise ValueError(f"value is not allowed: {clean_value}")

        if self.domain_type == "range":
            minimum = self.min_value
            maximum = self.max_value
            if minimum is not None and _comparison_value(datatype, clean_value) < _comparison_value(datatype, minimum):
                raise ValueError(f"value is below parameter minimum: {clean_value}")
            if maximum is not None and _comparison_value(datatype, clean_value) > _comparison_value(datatype, maximum):
                raise ValueError(f"value is above parameter maximum: {clean_value}")

        updated = copy.deepcopy(parameter_el)
        updated.set("value", serialized)
        calculations = updated.xpath("./*[local-name()='calculation']")
        if calculations:
            calculations[0].set("formula", serialized)
        if not xml_equal(parameter_el, updated):
            parent = parameter_el.getparent()
            if parent is None:
                raise DetachedModelError(f"parameter is detached: {self._id}")
            parent.replace(parameter_el, updated)
            self._context.mark_dirty()
        return self

    def delete(self) -> None:
        parameter_el = self._resolve_element()
        references = field_references(self._context.tree, "Parameters", self._id)
        if references:
            raise ResourceInUseError("Parameter", self._id, references)
        parent = parameter_el.getparent()
        if parent is None:
            raise DetachedModelError(f"parameter is detached: {self._id}")
        parent.remove(parameter_el)
        self._context.mark_dirty()
        self._detach()


def create_parameter(
    context: WorkbookContext,
    *,
    name: str,
    value: Any,
    datatype: str = "string",
    domain_type: str = "any",
    allowable_values: Sequence[Any] | Mapping[Any, str] | None = None,
    min_value: Any | None = None,
    max_value: Any | None = None,
    step_size: Any | None = None,
    hidden: bool = False,
) -> TwbParameter:
    if not isinstance(name, str):
        raise TypeError("name must be a string")
    name = name.strip()
    if not name:
        raise ValueError("name must not be empty")
    if not isinstance(datatype, str):
        raise TypeError("datatype must be a string")
    datatype = datatype.lower()
    if datatype not in _DATATYPES:
        raise ValueError(f"unsupported datatype: {datatype}")
    if not isinstance(domain_type, str):
        raise TypeError("domain_type must be a string")
    domain_type = domain_type.lower()
    if domain_type not in _DOMAIN_TYPES:
        raise ValueError(f"unsupported domain type: {domain_type}")
    if not isinstance(hidden, bool):
        raise TypeError("hidden must be bool")

    serialized_value, public_value = _serialize_value(datatype, value)
    members: list[tuple[str, str, str | None]] = []
    range_values: tuple[str, str, str | None] | None = None

    if domain_type == "any":
        if allowable_values is not None or min_value is not None or max_value is not None or step_size is not None:
            raise ValueError("any domain does not accept allowable or range values")
    elif domain_type == "list":
        if allowable_values is None:
            raise ValueError("list domain requires allowable_values")
        if min_value is not None or max_value is not None or step_size is not None:
            raise ValueError("list domain does not accept range values")
        if isinstance(allowable_values, Mapping):
            source_members = [(item, str(alias)) for item, alias in allowable_values.items()]
        elif isinstance(allowable_values, Sequence) and not isinstance(allowable_values, (str, bytes)):
            source_members = [(item, None) for item in allowable_values]
        else:
            raise TypeError("allowable_values must be a sequence or mapping")
        if not source_members:
            raise ValueError("allowable_values must not be empty")
        seen_values: set[str] = set()
        for member_value, alias in source_members:
            serialized_member, public_member = _serialize_value(datatype, member_value)
            if public_member in seen_values:
                raise ValueError(f"allowable value is duplicated: {public_member}")
            seen_values.add(public_member)
            members.append((serialized_member, public_member, alias))
        if public_value not in seen_values:
            raise ValueError(f"current value is not in allowable_values: {public_value}")
    else:
        if allowable_values is not None:
            raise ValueError("range domain does not accept allowable_values")
        if datatype not in {"integer", "real", "date", "datetime"}:
            raise ValueError(f"range domain is not supported for datatype: {datatype}")
        if min_value is None or max_value is None:
            raise ValueError("range domain requires min_value and max_value")
        serialized_min, public_min = _serialize_value(datatype, min_value)
        serialized_max, public_max = _serialize_value(datatype, max_value)
        comparable_min = _comparison_value(datatype, public_min)
        comparable_max = _comparison_value(datatype, public_max)
        comparable_value = _comparison_value(datatype, public_value)
        if comparable_min > comparable_max:
            raise ValueError("min_value must not exceed max_value")
        if comparable_value < comparable_min or comparable_value > comparable_max:
            raise ValueError("current value must be within the parameter range")
        serialized_step: str | None = None
        if step_size is not None:
            if datatype not in {"integer", "real"}:
                raise UnsupportedFeatureError("date and datetime range steps are not supported")
            serialized_step, public_step = _serialize_value(datatype, step_size)
            if _comparison_value(datatype, public_step) <= 0:
                raise ValueError("step_size must be positive")
        range_values = serialized_min, serialized_max, serialized_step

    parameter_id = _parameter_id(name)
    root = context.tree.getroot()
    if ET.QName(root).namespace is not None:
        raise UnsupportedFeatureError("namespaced workbook XML is not supported")
    existing_parameters = root.xpath(
        "/workbook/datasources/datasource[@name='Parameters']/column[@name]"
    )
    if any(
        column.get("name") == parameter_id or get_display_name(column) == name
        for column in existing_parameters
    ):
        raise ValueError(f"parameter already exists: {name}")

    updated_root = copy.deepcopy(root)
    datasources_el = _direct_child(updated_root, "datasources")
    if datasources_el is None:
        datasources_el = ET.Element("datasources")
        worksheets_el = _direct_child(updated_root, "worksheets")
        if worksheets_el is None:
            updated_root.append(datasources_el)
        else:
            updated_root.insert(updated_root.index(worksheets_el), datasources_el)
    parameter_sources = datasources_el.xpath("./datasource[@name='Parameters']")
    if len(parameter_sources) > 1:
        raise UnsupportedFeatureError("workbook has multiple Parameters datasources")
    if parameter_sources:
        parameters_el = parameter_sources[0]
    else:
        datasource_attrs = {
            "name": "Parameters",
            "caption": "Parameters",
            "hasconnection": "false",
            "inline": "true",
        }
        if updated_root.get("version"):
            datasource_attrs["version"] = str(updated_root.get("version"))
        parameters_el = ET.SubElement(datasources_el, "datasource", attrib=datasource_attrs)

    column_attrs = {
        "name": parameter_id,
        "caption": name,
        "datatype": datatype,
        "param-domain-type": domain_type,
        "role": "measure",
        "type": "nominal" if datatype in {"string", "boolean"} else "quantitative",
        "value": serialized_value,
    }
    if hidden:
        column_attrs["hidden"] = "true"
    column_el = ET.SubElement(parameters_el, "column", attrib=column_attrs)
    ET.SubElement(
        column_el,
        "calculation",
        attrib={"class": "tableau", "formula": serialized_value},
    )
    if members:
        members_el = ET.SubElement(column_el, "members")
        for serialized_member, _, alias in members:
            member_attrs = {"value": serialized_member}
            if alias is not None:
                member_attrs["alias"] = alias
            ET.SubElement(members_el, "member", attrib=member_attrs)
    if range_values is not None:
        serialized_min, serialized_max, serialized_step = range_values
        range_attrs = {"min": serialized_min, "max": serialized_max}
        if serialized_step is not None:
            range_attrs["granularity"] = serialized_step
        ET.SubElement(column_el, "range", attrib=range_attrs)

    context.tree._setroot(updated_root)
    context.mark_dirty()
    return TwbParameter(context, parameter_id)


def get_parameters(
    context: WorkbookContext,
    *,
    id: str | None = None,
    name: str | None = None,
    include_hidden: bool = False,
) -> list[TwbParameter]:
    _validate_get_args(id, name)
    if not isinstance(include_hidden, bool):
        raise TypeError("include_hidden must be bool")
    result: list[TwbParameter] = []
    columns = context.tree.getroot().xpath(
        "/workbook/datasources/datasource[@name='Parameters']/column[@name]"
    )
    for column_el in columns:
        hidden = (column_el.get("hidden") or "false").lower() == "true"
        if hidden and not include_hidden:
            continue
        parameter_id = str(column_el.get("name"))
        parameter_name = get_display_name(column_el)
        if _matches(model_id=parameter_id, model_name=parameter_name, id=id, name=name):
            result.append(TwbParameter(context, parameter_id))
    return result
