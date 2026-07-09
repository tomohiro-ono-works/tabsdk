from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BigQuerySource:
    project: str | None = None
    dataset: str | None = None
    table: str | None = None
    server: str | None = None
    custom_sql: str | None = None


@dataclass
class ExcelSource:
    file_path: str | None = None
    sheet: str | None = None
    custom_sql: str | None = None


@dataclass
class CsvSource:
    file_path: str | None = None
    custom_sql: str | None = None


@dataclass
class UnknownSource:
    raw_type: str | None = None
    custom_sql: str | None = None


@dataclass
class TwbColumn:
    name: str
    id: str | None = None
    caption: str | None = None
    datatype: str | None = None
    role: str | None = None
    discrete: bool | None = None
    hidden: bool = False
    formula: str | None = None
    raw_formula: str | None = None
    referenced_columns: list[str] = field(default_factory=list)
    format: list[dict[str, str]] = field(default_factory=list)
    folder: str | None = None

    @property
    def is_calculated(self) -> bool:
        return self.raw_formula is not None or self.formula is not None


@dataclass
class TwbFolder:
    name: str
    id: str | None = None
    role: str | None = None
    items: list[str] = field(default_factory=list)


@dataclass
class TwbParameter:
    name: str
    id: str | None = None
    caption: str | None = None
    datatype: str | None = None
    value: str | None = None
    value_display: str | None = None
    domain_type: str | None = None
    allowable_values: list[dict[str, str | None]] = field(default_factory=list)
    aliases: list[dict[str, str | None]] = field(default_factory=list)
    default_value_field: str | None = None
    hidden: bool = False


@dataclass
class TwbDatasource:
    name: str | None
    caption: str | None
    source_type: str
    source: BigQuerySource | ExcelSource | CsvSource | UnknownSource
    columns: list[TwbColumn]
    folders: list[TwbFolder]
    id: str | None = None


@dataclass
class TwbWorksheet:
    name: str
    id: str | None = None
    caption: str | None = None
    rows: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    filters: list[dict[str, str]] = field(default_factory=list)
    datasource_names: list[str] = field(default_factory=list)
    used_columns: list[str] = field(default_factory=list)


@dataclass
class TwbDashboard:
    name: str
    id: str | None = None
    caption: str | None = None
    worksheets: list[TwbWorksheet] = field(default_factory=list)


@dataclass
class TwbWorksheetField:
    worksheet: str
    type: str
    role: str | None
    caption: str | None
    id: str | None = None
    values: str | None = None


@dataclass
class TwbValidationMessage:
    severity: str
    code: str
    message: str
    datasource: str | None = None
    column: str | None = None


@dataclass
class TwbUnsupportedFeature:
    feature: str
    severity: str
    message: str
    datasource: str | None = None
