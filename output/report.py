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


def _format_workload(hours: Union[int, float], workload_unit: str) -> str:
    if workload_unit == "hour":
        return f"{int(hours) if float(hours).is_integer() else round(hours, 1)}小时"
    return f"{_to_person_days(hours)}人天"


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


def _summarize_tree_node(node: dict, row_map: dict) -> dict:
    children = node.get("children", [])
    if not children:
        row = row_map[node["name"]]
        return {
            "name": node["name"],
            "description": node.get("description", "").strip(),
            "base_total": row["base_total"],
            "total": row["total"],
            "children": [],
            "is_leaf": True,
        }

    summarized_children = [_summarize_tree_node(child, row_map) for child in children]
    return {
        "name": node["name"],
        "description": node.get("description", "").strip(),
        "base_total": sum(child["base_total"] for child in summarized_children),
        "total": sum(child["total"] for child in summarized_children),
        "children": summarized_children,
        "is_leaf": False,
    }


def _append_module_outline(lines: list[str], nodes: list[dict], workload_unit: str, level: int = 0) -> None:
    indent = "  " * level
    for node in nodes:
        lines.append(
            f"{indent}- {node['name']}: 原始 {_format_workload(node['base_total'], workload_unit)}, 建议 {_format_workload(node['total'], workload_unit)}"
        )
        if node.get("description"):
            lines.append(f"{indent}  描述: {node['description']}")
        if node["children"]:
            _append_module_outline(lines, node["children"], workload_unit, level + 1)


def build_report(
    requirement_text: str,
    module_tree: list[dict],
    modules: list[str],
    module_details: list[dict],
    assignments: dict,
    rows: list[dict],
    active_agents: list[str],
    clarification_history: list[dict],
    clarification_summary: str,
    project_background_summary: str,
    effort_buffer_ratio: float,
    workload_unit: str,
) -> str:
    row_map = _build_row_map(rows)
    summarized_tree = [_summarize_tree_node(node, row_map) for node in module_tree]
    base_total_hours = int(sum(row["base_total"] for row in rows))
    total_hours = int(sum(row["total"] for row in rows))
    lines = [
        "# 工作量评估报告",
        "",
        "## 原始需求",
        requirement_text,
        "",
        "## 参与岗位",
        ", ".join(ROLE_LABELS.get(agent, agent) for agent in active_agents) if active_agents else "无",
    ]

    if project_background_summary:
        lines.extend(["", "## 项目背景摘要", project_background_summary])

    if clarification_summary:
        lines.extend(["", "## 澄清摘要", clarification_summary])

    lines.extend(["", "## 模块层级"])
    _append_module_outline(lines, summarized_tree, workload_unit)

    lines.extend(["", "## 模块说明"])
    for item in module_details:
        lines.append(f"- {item['name']}: {item.get('description', '').strip() or '无描述'}")

    if clarification_history:
        lines.extend(["", "## 澄清记录"])
        for item in clarification_history:
            lines.append(f"- Round {item['round']}")
            for answer in item["answers"]:
                lines.append(f"  - Q: {answer['question']}")
                lines.append(f"  - A: {answer['answer']}")

    lines.extend(
        [
            "",
            "## 工作量汇总",
            f"- 原始总工作量: {_format_workload(base_total_hours, workload_unit)}",
            f"- 冗余比例: {round(effort_buffer_ratio * 100, 2)}%",
            f"- 建议总工作量: {_format_workload(total_hours, workload_unit)}",
            "",
            "## 最细模块明细",
        ]
    )
    for row in rows:
        lines.append(
            f"- {row['module']}: 原始 {_format_workload(row['base_total'], workload_unit)}, 建议 {_format_workload(row['total'], workload_unit)}"
        )
        lines.append(f"  - 描述: {row.get('description', '').strip() or '无描述'}")
        if row["reason_summary"]:
            lines.append(f"  - {_format_reason_summary(row['reason_summary'])}")

    return "\n".join(lines) + "\n"
