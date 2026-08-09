from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from codelens.diff_parser import ChangedRange, parse_git_diff


def test_parses_added_lines():
    diff = """\
diff --git a/main.py b/main.py
index 1111111..2222222 100644
--- a/main.py
+++ b/main.py
@@ -10,0 +11,2 @@
+new_line()
+another_line()
"""

    result = parse_git_diff(diff)

    assert len(result) == 1
    assert result[0].file_path == "main.py"
    assert result[0].ranges == (ChangedRange(11, 12),)
    assert result[0].is_deleted is False


def test_parses_modified_lines():
    diff = """\
diff --git a/main.py b/main.py
index 1111111..2222222 100644
--- a/main.py
+++ b/main.py
@@ -10,3 +10,3 @@
-old()
-old2()
-old3()
+new()
+new2()
+new3()
"""

    result = parse_git_diff(diff)

    assert result[0].ranges == (ChangedRange(10, 12),)


def test_parses_multiple_hunks():
    diff = """\
diff --git a/main.py b/main.py
index 1111111..2222222 100644
--- a/main.py
+++ b/main.py
@@ -5,1 +5,2 @@
+first()
@@ -20,2 +21,3 @@
+second()
+third()
"""

    result = parse_git_diff(diff)

    assert result[0].ranges == (
        ChangedRange(5, 6),
        ChangedRange(21, 23),
    )


def test_parses_multiple_files():
    diff = """\
diff --git a/a.py b/a.py
index 1111111..2222222 100644
--- a/a.py
+++ b/a.py
@@ -1,0 +2,1 @@
+change()

diff --git a/package/b.py b/package/b.py
index 3333333..4444444 100644
--- a/package/b.py
+++ b/package/b.py
@@ -5,1 +5,1 @@
-old()
+new()
"""

    result = parse_git_diff(diff)

    assert [item.file_path for item in result] == [
        "a.py",
        "package/b.py",
    ]
    assert result[0].ranges == (ChangedRange(2, 2),)
    assert result[1].ranges == (ChangedRange(5, 5),)


def test_deletion_only_has_no_new_file_range():
    diff = """\
diff --git a/main.py b/main.py
deleted file mode 100644
index 1111111..0000000
--- a/main.py
+++ /dev/null
@@ -10,3 +10,0 @@
-old()
-old2()
-old3()
"""

    result = parse_git_diff(diff)

    assert len(result) == 1
    assert result[0].file_path == "main.py"
    assert result[0].ranges == ()
    assert result[0].is_deleted is True


def test_new_file_is_detected():
    diff = """\
diff --git a/new.py b/new.py
new file mode 100644
index 0000000..1111111
--- /dev/null
+++ b/new.py
@@ -0,0 +1,3 @@
+def hello():
+    return "hello"
+
"""

    result = parse_git_diff(diff)

    assert result[0].file_path == "new.py"
    assert result[0].ranges == (ChangedRange(1, 3),)
    assert result[0].is_deleted is False
