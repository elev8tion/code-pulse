"""Tests for UnifiedDiffParser."""
import pytest
from codepulse.git.parser import UnifiedDiffParser

SAMPLE_DIFF = """\
diff --git a/src/main.py b/src/main.py
index 1234567..abcdefg 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,5 @@
 def hello():
-    pass
+    print("hello")
+    return True
+
diff --git a/tests/test_main.py b/tests/test_main.py
new file mode 100644
index 0000000..1111111
--- /dev/null
+++ b/tests/test_main.py
@@ -0,0 +1,5 @@
+import pytest
+from src.main import hello
+
+def test_hello():
+    assert hello() is True
"""


def test_parse_empty():
    parser = UnifiedDiffParser()
    snap = parser.parse("", turn_index=1)
    assert snap.files == []
    assert snap.total_added == 0
    assert snap.total_removed == 0


def test_parse_sample():
    parser = UnifiedDiffParser()
    snap = parser.parse(SAMPLE_DIFF, turn_index=1)
    assert snap.turn_index == 1
    assert len(snap.files) == 2
    paths = {f.path for f in snap.files}
    assert "src/main.py" in paths
    assert "tests/test_main.py" in paths


def test_no_changes():
    parser = UnifiedDiffParser()
    snap = parser.parse("   \n  ", turn_index=5)
    assert snap.files == []
    assert snap.turn_index == 5
