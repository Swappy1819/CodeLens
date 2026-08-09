from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from codelens.review import ReviewFinding, ReviewResult
from codelens.review_workflow import ReviewWorkflow


class FakeGraphQueries:
    class Impact:
        subject = None
        callers = ()
        callees = ()
        subclasses = ()

    def impact(self, symbol_id):
        return self.Impact()

class FakeProvider:
    def __init__(self):
        self.requests = []

    def review(self, request):
        self.requests.append(request)
        return ReviewResult(
            findings=(
                ReviewFinding(
                    severity="high",
                    title="Potential bug",
                    description="Test finding.",
                    file_path=request.file_path,
                    start_line=request.start_line,
                    end_line=request.end_line or request.start_line,
                ),
            )
        )


def test_review_workflow_connects_change_to_provider(tmp_path: Path) -> None:
    source = tmp_path / "service.py"
    source.write_text(
        """\
def run():
    value = 1
    return value
"""
    )

    diff = """\
diff --git a/service.py b/service.py
index 0000000..1111111 100644
--- a/service.py
+++ b/service.py
@@ -1,3 +1,3 @@
 def run():
-    value = 1
+    value = 2
     return value
"""

    provider = FakeProvider()

    workflow = ReviewWorkflow(
        repository=tmp_path,
        graph_queries=FakeGraphQueries(),
        provider=provider,
    )

    result = workflow.review(diff)

    assert len(provider.requests) == 1
    assert provider.requests[0].symbol_name == "run"
    assert provider.requests[0].file_path == "service.py"
    assert provider.requests[0].source
    assert len(result.findings) == 1
    assert result.findings[0].title == "Potential bug"


def test_review_workflow_returns_empty_result_when_no_symbol_changed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "README.txt"
    source.write_text("documentation")

    diff = """\
diff --git a/README.txt b/README.txt
index 0000000..1111111 100644
--- a/README.txt
+++ b/README.txt
@@ -1 +1 @@
-documentation
+updated documentation
"""

    provider = FakeProvider()

    workflow = ReviewWorkflow(
        repository=tmp_path,
        graph_queries=FakeGraphQueries(),
        provider=provider,
    )

    result = workflow.review(diff)

    assert result.findings == ()
    assert provider.requests == []
