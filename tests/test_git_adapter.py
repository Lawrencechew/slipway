from app.git_adapter import MockGitAdapter


def test_mock_git_operations():
    g = MockGitAdapter()
    res = g.create_branch(repo="owner/repo", base="main", branch="feature/orders")
    assert res.get("ok")
    c = g.commit(repo="owner/repo", branch="feature/orders", files={"a.txt": "x"}, message="add")
    assert c.get("ok") and "commit" in c
    pr = g.create_pr(repo="owner/repo", head="feature/orders", base="main", title="feat", body="")
    assert pr.get("ok") and "pr" in pr
    assert len(g.ops) == 3
