from __future__ import annotations

from dataclasses import asdict
from lxml import etree as ET
from .parser import ParsedWorkbook, open_workbook_file
from .writer import save_twb, save_twbx
from .models import TwbDatasource, TwbColumn, TwbDashboard, TwbWorksheet, TwbWorksheetField, TwbParameter, TwbValidationMessage, TwbUnsupportedFeature, BigQuerySource, ExcelSource, CsvSource, UnknownSource
from .datasource import list_datasources_from_tree, resolve_datasource_el, update_source_el
from .column import list_columns_from_datasource, resolve_column_el, rename_column_el, reset_column_caption_el, update_column_el
from .calculation import create_calculated_field_el, update_formula_el
from .parameter import list_parameters_from_tree
from .folder import move_column_to_folder_el, remove_column_from_folder_el
from .validator import validate_tree
from .unsupported import unsupported_features_from_tree
from .dashboard import list_dashboards_from_tree, get_dashboard_from_tree
from .dashboard_field import list_dashboard_fields_from_tree
from .worksheet import list_worksheets_from_tree, get_worksheet_from_tree
from .errors import SaveError, ValidationError


class TwbWorkbook:
    def __init__(self, parsed: ParsedWorkbook):
        self._parsed = parsed
        self.tree = parsed.tree

    @classmethod
    def open(cls, path: str) -> "TwbWorkbook":
        return cls(open_workbook_file(path))

    def save(self, path: str, *, validate: bool = True, overwrite: bool = False) -> None:
        if validate:
            errors = [m for m in self.validate() if m.severity == "error"]
            if errors:
                raise ValidationError(f"validation failed: {errors[0].code}: {errors[0].message}")
        if path.lower().endswith(".twbx"):
            if not self._parsed.is_twbx or not self._parsed.extract_dir or not self._parsed.twb_inner_path:
                raise SaveError(".twbx 保存には .twbx から開いたワークブックが必要です。")
            save_twbx(
                self.tree,
                path,
                extract_dir=self._parsed.extract_dir,
                twb_inner_path=self._parsed.twb_inner_path,
                overwrite=overwrite,
            )
        else:
            save_twb(self.tree, path, overwrite=overwrite)

    def export_json(self) -> dict:
        return {"datasources": [asdict(ds) for ds in self.list_datasources()]}

    def validate(self) -> list[TwbValidationMessage]:
        return validate_tree(self.tree)

    def unsupported_features(self) -> list[TwbUnsupportedFeature]:
        return unsupported_features_from_tree(self.tree)


    def list_dashboards(self) -> list[TwbDashboard]:
        return list_dashboards_from_tree(self.tree)

    def get_dashboard(self, dashboard: str, *, by: str = "auto") -> TwbDashboard:
        return get_dashboard_from_tree(self.tree, dashboard, by=by)

    def list_dashboard_fields(
        self,
        dashboard: str | None = None,
        *,
        by: str = "auto",
        max_filter_value_chars: int = 40,
    ) -> list[TwbWorksheetField]:
        return list_dashboard_fields_from_tree(
            self.tree,
            dashboard,
            by=by,
            max_filter_value_chars=max_filter_value_chars,
        )

    def list_worksheets(self) -> list[TwbWorksheet]:
        return list_worksheets_from_tree(self.tree)

    def get_worksheet(self, worksheet: str, *, by: str = "auto") -> TwbWorksheet:
        return get_worksheet_from_tree(self.tree, worksheet, by=by)

    def list_datasources(self) -> list[TwbDatasource]:
        return list_datasources_from_tree(self.tree)

    def get_datasource(self, datasource: str, *, by: str = "auto") -> TwbDatasource:
        ds_el = resolve_datasource_el(self.tree, datasource, by=by, include_parameters=False)
        for ds in self.list_datasources():
            if ds.id == ds_el.get("name"):
                return ds
        raise RuntimeError("resolved datasource could not be materialized")

    def list_parameters(self, *, include_hidden: bool = False) -> list[TwbParameter]:
        return list_parameters_from_tree(self.tree, include_hidden=include_hidden)

    def _materialize_column_from_el(self, datasource_el: ET._Element, column_el: ET._Element) -> TwbColumn:
        column_name = column_el.get("name")
        for col in list_columns_from_datasource(datasource_el):
            if col.name == column_name:
                return col
        raise RuntimeError("resolved column could not be materialized")

    def update_source(
        self,
        datasource: str,
        source: BigQuerySource | ExcelSource | CsvSource | UnknownSource,
    ) -> None:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto")
        update_source_el(ds_el, source)

    def list_columns(self, datasource: str) -> list[TwbColumn]:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto")
        return list_columns_from_datasource(ds_el)

    def get_column(self, datasource: str, column: str, *, by: str = "auto") -> TwbColumn:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto")
        col_el = resolve_column_el(ds_el, column, by=by)
        return self._materialize_column_from_el(ds_el, col_el)

    def rename_field(self, datasource: str, field: str, caption: str, *, by: str = "auto") -> TwbColumn:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto", include_parameters=False)
        col_el = rename_column_el(ds_el, field, caption, by=by)
        return self._materialize_column_from_el(ds_el, col_el)

    def reset_field_caption(self, datasource: str, field: str, *, by: str = "auto") -> TwbColumn:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto", include_parameters=False)
        col_el = reset_column_caption_el(ds_el, field, by=by)
        return self._materialize_column_from_el(ds_el, col_el)

    def update_column(
        self,
        datasource: str,
        column: str,
        *,
        by: str = "auto",
        caption: str | None = None,
        role: str | None = None,
        discrete: bool | None = None,
        hidden: bool | None = None,
        folder: str | None = None,
    ) -> None:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto")
        col_el = resolve_column_el(ds_el, column, by=by)
        update_column_el(col_el, caption=caption, role=role, discrete=discrete, hidden=hidden)
        if folder is not None:
            move_column_to_folder_el(ds_el, col_el.get("name") or column, folder, by="name")

    def update_formula(
        self,
        datasource: str,
        column: str,
        formula: str,
        *,
        by: str = "auto",
        formula_ref: str = "auto",
        strict: bool = False,
        ref_map: dict[str, str] | None = None,
    ) -> None:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto")
        update_formula_el(ds_el, column, formula, by=by, formula_ref=formula_ref, strict=strict, ref_map=ref_map)

    def create_calculated_field(
        self,
        datasource: str,
        caption: str,
        formula: str,
        *,
        datatype: str = "real",
        role: str = "measure",
        discrete: bool | None = False,
        folder: str | None = None,
        hidden: bool = False,
        formula_ref: str = "auto",
        strict: bool = False,
        ref_map: dict[str, str] | None = None,
    ) -> TwbColumn:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto", include_parameters=False)
        created = create_calculated_field_el(
            ds_el,
            name=None,
            caption=caption,
            formula=formula,
            datatype=datatype,
            role=role,
            discrete=discrete,
            hidden=hidden,
            formula_ref=formula_ref,
            strict=strict,
            ref_map=ref_map,
        )
        if folder is not None:
            move_column_to_folder_el(ds_el, created.name, folder, by="name", role="measures" if role == "measure" else None)
        created_el = resolve_column_el(ds_el, created.name, by="name")
        return self._materialize_column_from_el(ds_el, created_el)

    def move_field_to_folder(
        self,
        datasource: str,
        field: str,
        folder: str,
        *,
        by: str = "auto",
        role: str | None = None,
        create_if_missing: bool = True,
    ) -> TwbColumn:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto", include_parameters=False)
        col_el = resolve_column_el(ds_el, field, by=by)
        move_column_to_folder_el(
            ds_el,
            col_el.get("name") or field,
            folder,
            by="name",
            role=role,
            create_if_missing=create_if_missing,
        )
        return self._materialize_column_from_el(ds_el, col_el)

    def remove_field_from_folder(self, datasource: str, field: str, *, by: str = "auto") -> TwbColumn:
        ds_el = resolve_datasource_el(self.tree, datasource, by="auto", include_parameters=False)
        col_el = resolve_column_el(ds_el, field, by=by)
        remove_column_from_folder_el(ds_el, col_el.get("name") or field, by="name")
        return self._materialize_column_from_el(ds_el, col_el)

    def move_column_to_folder(
        self,
        datasource: str,
        column: str,
        folder: str,
        *,
        by: str = "auto",
        role: str | None = None,
        create_if_missing: bool = True,
    ) -> TwbColumn:
        return self.move_field_to_folder(
            datasource,
            column,
            folder,
            by=by,
            role=role,
            create_if_missing=create_if_missing,
        )
