ROLE_NAMES = {"product", "backend", "frontend", "app", "ui", "testing", "algorithm", "ops"}


def ensure_valid_presale_response(data: dict) -> None:
    required = {"modules", "module_assignments", "clarifications", "next_action"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Presale response missing keys: {sorted(missing)}")
    if data["next_action"] not in {"clarify", "done"}:
        raise ValueError(f"Invalid next_action: {data['next_action']}")


def ensure_assignments_cover_modules(modules: list[str], assignments: dict) -> None:
    for module_name in modules:
        if module_name not in assignments:
            raise ValueError(f"Module assignment missing: {module_name}")
        roles = assignments[module_name]
        if not isinstance(roles, list) or not roles:
            raise ValueError(f"Module assignment must be a non-empty role list: {module_name}")
        ensure_valid_agent_names(roles, ROLE_NAMES)


def ensure_no_duplicate_agents(agents: list[str]) -> None:
    if len(set(agents)) != len(agents):
        raise ValueError(f"Duplicate active agents detected: {agents}")


def ensure_valid_agent_names(agents: list[str], valid_agents) -> None:
    invalid = [agent for agent in agents if agent not in valid_agents]
    if invalid:
        raise ValueError(f"Invalid agent names: {invalid}")


def ensure_estimations_cover_modules(modules: list[str], estimations: list[dict], role_name: str) -> None:
    estimation_map = {item["module"]: item for item in estimations}
    for module_name in modules:
        if module_name not in estimation_map:
            raise ValueError(f"{role_name} estimation missing module: {module_name}")
        hours = estimation_map[module_name].get("hours")
        if not isinstance(hours, (int, float)) or hours < 0:
            raise ValueError(f"{role_name} returned invalid hours for {module_name}: {hours}")


def normalize_estimations(
    modules: list[str], estimations: list[dict], role_name: str, assigned_modules: list[str]
) -> list[dict]:
    estimation_map = {item["module"]: item for item in estimations if "module" in item}
    normalized = []
    missing_assigned = [module_name for module_name in assigned_modules if module_name not in estimation_map]
    if missing_assigned:
        raise ValueError(f"{role_name} estimation missing assigned modules: {missing_assigned}")

    for module_name in modules:
        item = estimation_map.get(module_name)
        if item is None:
            item = {
                "module": module_name,
                "hours": 0,
                "reason": f"Not assigned to {role_name}. Filled by harness.",
            }
        normalized.append(item)
    return normalized
