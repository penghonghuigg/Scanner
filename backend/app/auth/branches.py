BRANCH_NAMES: dict[str, str] = {
    "TIANDA": "田大分局",
    "XIEBA": "谢八分局",
    "PANJI": "潘集分局",
    "SHOUXIAN": "寿县局",
    "FENGTAI": "凤台县局",
}


class UnknownBranchError(ValueError):
    pass


def branch_name(branch_code: str | None) -> str | None:
    if branch_code is None:
        return None
    try:
        return BRANCH_NAMES[branch_code]
    except KeyError as exc:
        raise UnknownBranchError(f"未知分局代码：{branch_code}") from exc
