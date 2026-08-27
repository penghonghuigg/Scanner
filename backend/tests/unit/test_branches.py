import pytest

from app.auth.branches import BRANCH_NAMES, UnknownBranchError, branch_name


def test_branch_names_match_the_five_approved_branches() -> None:
    assert BRANCH_NAMES == {
        "TIANDA": "田大分局",
        "XIEBA": "谢八分局",
        "PANJI": "潘集分局",
        "SHOUXIAN": "寿县局",
        "FENGTAI": "凤台县局",
    }


def test_branch_name_handles_admin_and_rejects_unknown_codes() -> None:
    assert branch_name(None) is None
    assert branch_name("FENGTAI") == "凤台县局"
    with pytest.raises(UnknownBranchError):
        branch_name("UNKNOWN")
