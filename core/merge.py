def merge_results(
    modules: list[str], assignments: dict, results: dict, roles: list[str], effort_buffer_ratio: float
) -> list[dict]:
    rows = []
    for module_name in modules:
        row = {"module": module_name}
        total = 0
        reasons = []
        for role in roles:
            estimations = results.get(role, {}).get("estimations", [])
            estimation = next((item for item in estimations if item["module"] == module_name), None)
            hours = estimation["hours"] if estimation else 0
            reason = estimation["reason"] if estimation else ""
            row[role] = hours
            if reason:
                reasons.append(f"{role}: {reason}")
            total += hours
        buffered_total = int(round(total * (1 + effort_buffer_ratio)))
        row["base_total"] = total
        row["buffer_ratio"] = effort_buffer_ratio
        row["total"] = buffered_total
        row["reason_summary"] = " | ".join(reasons)
        rows.append(row)
    return rows
