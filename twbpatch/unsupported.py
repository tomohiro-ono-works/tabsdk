from __future__ import annotations

from lxml import etree as ET
from .models import TwbUnsupportedFeature


def unsupported_features_from_tree(tree: ET._ElementTree) -> list[TwbUnsupportedFeature]:
    root = tree.getroot()
    result: list[TwbUnsupportedFeature] = []
    checks = [
        ('.//*[local-name()="connection" and @class="federated"]', "relationship", "warning", "relationship/federated connection may be unsupported"),
        ('.//*[local-name()="connection" and @class="hyper"]', "hyper_extract", "warning", "hyper extract is preserved but not edited"),
        ('.//*[local-name()="relation" and @type="text"]', "custom_sql", "warning", "custom sql is read-only"),
        ('.//*[local-name()="relation" and @type="join"]', "join", "warning", "join editing is unsupported"),
        ('.//*[local-name()="relation" and @type="union"]', "union", "warning", "union editing is unsupported"),
    ]
    for xpath, feature, severity, message in checks:
        if root.xpath(xpath):
            result.append(TwbUnsupportedFeature(feature=feature, severity=severity, message=message))
    return result
