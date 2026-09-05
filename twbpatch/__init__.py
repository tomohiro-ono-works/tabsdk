"""twbpatch の公開名前空間。

同名クラスが `models.py`（旧 dataclass）と `connected*.py`（接続型モデル）の
両方にある 8 クラスは、**接続型モデルのほうを公開する**（A-1・2026-09-05 決定）。
旧 dataclass は `twbpatch.models` から引き続き import できる。

    from twbpatch import TwbWorksheet          # 接続型モデル（新）
    from twbpatch.models import TwbWorksheet   # dataclass（旧）

`TwbWorkbook.list_*()` は移行期のあいだ旧 dataclass を返し続ける（仕様 §11）。
"""

from .workbook import TwbWorkbook
from .export import write_dicts_csv

# 接続型モデル（新 API）
from .connected import (
    TwbDatasource,
    TwbField,
    TwbFolder,
    TwbRelation,
    TwbRelationship,
)
from .connected_parameter import TwbParameter
from .connected_worksheet import (
    TwbPane,
    TwbReferenceLine,
    TwbWorksheet,
    TwbWorksheetField,
    TwbWorksheetFilter,
)
from .connected_dashboard import (
    TwbDashboard,
    TwbDashboardAction,
    TwbDashboardContainer,
    TwbDashboardZone,
    TwbFilterControl,
)
from .draw import (
    draw_bar,
    draw_card,
    draw_colored_yoy_sheet,
    draw_crosstab,
    draw_quadrant,
    draw_sheet,
    draw_yoy,
)
# 接続型モデルがまだ無いもの（A-2 の対象）と、値オブジェクト
from .models import (
    BigQuerySource,
    ExcelSource,
    CsvSource,
    UnknownSource,
    TwbColumn,
    TwbValidationMessage,
    TwbUnsupportedFeature,
)
from .errors import (
    TwbPatchError,
    NotFoundError,
    AmbiguousCaptionError,
    AmbiguousFormulaReferenceError,
    ValidationError,
    UnsupportedFeatureError,
    SaveError,
    DetachedModelError,
    ResourceInUseError,
    ResourceReference,
)

__all__ = [
    "TwbWorkbook",
    "write_dicts_csv",
    "draw_bar",
    "draw_card",
    "draw_colored_yoy_sheet",
    "draw_crosstab",
    "draw_quadrant",
    "draw_sheet",
    "draw_yoy",
    "BigQuerySource",
    "ExcelSource",
    "CsvSource",
    "UnknownSource",
    "TwbColumn",
    "TwbField",
    "TwbPane",
    "TwbDashboardContainer",
    "TwbDatasource",
    "TwbFolder",
    "TwbParameter",
    "TwbRelation",
    "TwbRelationship",
    "TwbDashboard",
    "TwbDashboardAction",
    "TwbDashboardZone",
    "TwbWorksheet",
    "TwbWorksheetField",
    "TwbReferenceLine",
    "TwbWorksheetFilter",
    "TwbFilterControl",
    "TwbValidationMessage",
    "TwbUnsupportedFeature",
    "TwbPatchError",
    "NotFoundError",
    "AmbiguousCaptionError",
    "AmbiguousFormulaReferenceError",
    "ValidationError",
    "UnsupportedFeatureError",
    "SaveError",
    "DetachedModelError",
    "ResourceInUseError",
    "ResourceReference",
]
