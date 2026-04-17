from pathlib import Path
from typing import Union

ROLE_LABELS = {
    "product": "产品",
    "ui": "UI",
    "backend": "后端",
    "frontend": "前端",
    "app": "APP",
    "testing": "测试",
    "algorithm": "算法",
    "ops": "运维",
}


def _to_person_days(hours: Union[int, float]) -> float:
    return round(hours / 8, 1)


def _format_reason_summary(reason_summary: str) -> str:
    if not reason_summary:
        return ""
    parts = []
    for item in reason_summary.split(" | "):
        if ": " in item:
            role, reason = item.split(": ", 1)
            parts.append(f"{ROLE_LABELS.get(role, role)}: {reason}")
        else:
            parts.append(item)
    return " | ".join(parts)


def _build_row_map(rows: list[dict]) -> dict:
    return {row["module"]: row for row in rows}


def _summarize_tree_node(node: dict, row_map: dict, level: int = 1) -> tuple[list[dict], int, int]:
    children = node.get("children", [])
    if not children:
        row = row_map[node["name"]]
        current = {
            "level": level,
            "module": node["name"],
            "description": node.get("description", "").strip(),
            "base_total": row["base_total"],
            "total": row["total"],
            "is_leaf": True,
        }
        return [current], row["base_total"], row["total"]

    child_rows = []
    base_total = 0
    total = 0
    for child in children:
        rows_for_child, child_base_total, child_total = _summarize_tree_node(child, row_map, level + 1)
        child_rows.extend(rows_for_child)
        base_total += child_base_total
        total += child_total

    current = {
        "level": level,
        "module": node["name"],
        "description": node.get("description", "").strip(),
        "base_total": base_total,
        "total": total,
        "is_leaf": False,
    }
    return [current] + child_rows, base_total, total


def _build_summary_rows(module_tree: list[dict], rows: list[dict]) -> list[dict]:
    row_map = _build_row_map(rows)
    summary_rows = []
    for node in module_tree:
        node_rows, _, _ = _summarize_tree_node(node, row_map, level=1)
        summary_rows.extend(node_rows)
    return summary_rows


def _append_sheet(sheet, rows: list[dict]) -> None:
    if not rows:
        return
    headers = list(rows[0].keys())
    sheet.append(headers)
    for row in rows:
        sheet.append([row.get(header, "") for header in headers])


def _build_display_summary_rows(summary_rows: list[dict]) -> list[dict]:
    result = []
    for row in summary_rows:
        result.append(
            {
                "层级": row["level"],
                "模块": row["module"],
                "功能描述": row.get("description", ""),
                "原始人天": _to_person_days(row["base_total"]),
                "建议人天": _to_person_days(row["total"]),
            }
        )
    return result


def _build_display_detail_rows(rows: list[dict]) -> list[dict]:
    result = []
    for row in rows:
        display_row = {"模块": row["module"], "功能描述": row.get("description", "")}
        for role, label in ROLE_LABELS.items():
            display_row[label] = _to_person_days(row.get(role, 0))
        display_row["原始人天"] = _to_person_days(row["base_total"])
        display_row["冗余比例"] = row["buffer_ratio"]
        display_row["建议人天"] = _to_person_days(row["total"])
        display_row["评估依据"] = _format_reason_summary(row["reason_summary"])
        result.append(display_row)
    return result


def save_excel(module_tree: list[dict], rows: list[dict], path: Path) -> None:
    try:
        from openpyxl import Workbook
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing dependency: openpyxl") from exc

    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "汇总"
    detail_sheet = workbook.create_sheet("明细")

    if not rows:
        workbook.save(path)
        return

    summary_rows = _build_summary_rows(module_tree, rows)
    _append_sheet(summary_sheet, _build_display_summary_rows(summary_rows))
    _append_sheet(detail_sheet, _build_display_detail_rows(rows))

    workbook.save(path)
