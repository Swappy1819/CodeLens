from codelens.cli import get_git_diff, main
from pathlib import Path


def test_review_command_returns_success(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["codelens", "review"],
    )

    monkeypatch.setattr(
        "codelens.cli.get_git_diff",
        lambda: "fake diff",
    )

    class FakeClient:
        def verify_connection(self):
            pass

        def close(self):
            pass

    class FakeGraphQueries:
        def __init__(self, client):
            pass

    class FakeProvider:
        pass

    class FakeResult:
        findings = ()

    class FakeWorkflow:
        def __init__(self, repository, graph_queries, provider):
            pass

        def review(self, diff):
            assert diff == "fake diff"
            return FakeResult()

    monkeypatch.setattr(
        "codelens.cli.Neo4jClient",
        FakeClient,
    )
    monkeypatch.setattr(
        "codelens.cli.GraphQueryService",
        FakeGraphQueries,
    )
    monkeypatch.setattr(
        "codelens.cli.GeminiLLMProvider",
        FakeProvider,
    )
    monkeypatch.setattr(
        "codelens.cli.ReviewWorkflow",
        FakeWorkflow,
    )

    assert main() == 0


def test_get_git_diff(monkeypatch):
    class Result:
        stdout = "fake diff"

    def fake_run(*args, **kwargs):
        assert args[0] == ["git", "diff"]
        return Result()

    monkeypatch.setattr(
        "codelens.cli.subprocess.run",
        fake_run,
    )

    assert get_git_diff() == "fake diff"

def test_review_command_prints_findings(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["codelens", "review"],
    )

    monkeypatch.setattr(
        "codelens.cli.get_git_diff",
        lambda: "fake diff",
    )

    class FakeClient:
        def verify_connection(self):
            pass

        def close(self):
            pass

    class FakeGraphQueries:
        def __init__(self, client):
            pass

    class FakeProvider:
        pass

    class FakeWorkflow:
        def __init__(self, repository, graph_queries, provider):
            pass

        def review(self, diff):
            class Finding:
                severity = "high"
                title = "SQL injection"
                description = "User input is passed directly to a query."
                file_path = "service.py"
                start_line = 10
                end_line = 12

            class Result:
                findings = (Finding(),)

            return Result()

    monkeypatch.setattr("codelens.cli.Neo4jClient", FakeClient)
    monkeypatch.setattr("codelens.cli.GraphQueryService", FakeGraphQueries)
    monkeypatch.setattr("codelens.cli.GeminiLLMProvider", FakeProvider)
    monkeypatch.setattr("codelens.cli.ReviewWorkflow", FakeWorkflow)

    assert main() == 0

    output = capsys.readouterr().out

    assert "[HIGH] SQL injection" in output
    assert "service.py:10-12" in output
    assert "User input is passed directly to a query." in output

def test_review_command_with_no_changes(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["codelens", "review"],
    )

    monkeypatch.setattr(
        "codelens.cli.get_git_diff",
        lambda: "",
    )

    class FailClient:
        def __init__(self):
            raise AssertionError("Neo4j should not be created")

    monkeypatch.setattr(
        "codelens.cli.Neo4jClient",
        FailClient,
    )

    assert main() == 0

    output = capsys.readouterr().out

    assert "No changes to review." in output


def test_index_command(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["codelens", "index"],
    )

    calls = []

    def fake_index_repository(repository):
        calls.append(repository)

    monkeypatch.setattr(
        "codelens.cli.index_repository",
        fake_index_repository,
    )

    assert main() == 0

    assert calls == [Path.cwd()]

    output = capsys.readouterr().out

    assert "Repository indexed." in output
# from codelens.cli import main


# def test_review_command_returns_success(monkeypatch):
#     monkeypatch.setattr(
#         "sys.argv",
#         ["codelens", "review"],
#     )

#     assert main() == 0