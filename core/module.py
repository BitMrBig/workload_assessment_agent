def flatten_modules(tree: list[dict]) -> list[str]:
    result = []

    def dfs(node: dict) -> None:
        children = node.get("children", [])
        if not children:
            result.append(node["name"])
            return
        for child in children:
            dfs(child)

    for node in tree:
        dfs(node)
    return result


def build_leaf_module_details(tree: list[dict]) -> list[dict]:
    result = []

    def dfs(node: dict) -> None:
        children = node.get("children", [])
        if not children:
            result.append(
                {
                    "name": node["name"],
                    "description": node.get("description", "").strip(),
                }
            )
            return
        for child in children:
            dfs(child)

    for node in tree:
        dfs(node)
    return result


def build_leaf_module_detail_map(tree: list[dict]) -> dict:
    return {item["name"]: item for item in build_leaf_module_details(tree)}
