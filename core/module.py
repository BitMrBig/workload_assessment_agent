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

