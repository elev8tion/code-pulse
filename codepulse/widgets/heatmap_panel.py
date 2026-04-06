"""HeatMapPanel — directory tree with color-intensity bars."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static, Tree
from textual.widgets.tree import TreeNode

from codepulse.heatmap.models import HeatMapEntry, HeatMapState
from codepulse.utils.colors import intensity_bar, intensity_to_color


class HeatMapPanel(Widget):
    DEFAULT_CSS = """
    HeatMapPanel {
        border: solid $accent-darken-2;
        height: 100%;
    }
    HeatMapPanel > #heatmap-header {
        background: $accent-darken-3;
        height: 1;
        padding: 0 1;
        color: $accent;
    }
    HeatMapPanel > Tree {
        height: 1fr;
        padding: 0 1;
        background: transparent;
    }
    """

    heatmap_state: reactive[HeatMapState | None] = reactive(None, layout=True)

    def compose(self) -> ComposeResult:
        yield Static("  Heat Map", id="heatmap-header")
        yield Tree("Project", id="heatmap-tree")

    def on_mount(self) -> None:
        self._tree = self.query_one("#heatmap-tree", Tree)
        self._tree.root.expand()

    def watch_heatmap_state(self, state: HeatMapState | None) -> None:
        if state is not None:
            self._build_tree(state)

    def _build_tree(self, state: HeatMapState) -> None:
        tree = self._tree
        tree.clear()
        tree.root.label = Text.from_markup("[bold]Project[/]")

        if not state.entries:
            tree.root.add_leaf(Text("No changes yet", style="dim"))
            tree.root.expand()
            return

        # Group entries by directory
        by_dir: dict[str, list[HeatMapEntry]] = defaultdict(list)
        for entry in state.entries.values():
            dir_path = str(Path(entry.path).parent)
            by_dir[dir_path].append(entry)

        # Sort dirs: root-level first, then by depth
        sorted_dirs = sorted(by_dir.keys(), key=lambda d: (d.count("/"), d))

        dir_nodes: dict[str, TreeNode] = {}

        for dir_path in sorted_dirs:
            entries = sorted(by_dir[dir_path], key=lambda e: e.lines_changed, reverse=True)

            if dir_path == ".":
                parent_node = tree.root
            else:
                # Build or find parent node
                parts = dir_path.split("/")
                current = tree.root
                accumulated = ""
                for part in parts:
                    accumulated = f"{accumulated}/{part}" if accumulated else part
                    if accumulated not in dir_nodes:
                        dir_label = self._dir_label(accumulated, entries, by_dir)
                        node = current.add(dir_label, expand=True)
                        dir_nodes[accumulated] = node
                    current = dir_nodes[accumulated]
                parent_node = current

            for entry in entries:
                fname = Path(entry.path).name
                leaf_label = self._file_label(fname, entry)
                parent_node.add_leaf(leaf_label)

        tree.root.expand()

    def _file_label(self, fname: str, entry: HeatMapEntry) -> Text:
        text = Text()
        bar = intensity_bar(entry.intensity, width=8)
        color = intensity_to_color(entry.intensity)
        text.append(f"{bar} ", style=color)
        text.append(fname, style="white")
        text.append(f"  {entry.lines_changed}L", style="dim")
        return text

    def _dir_label(self, dir_path: str, entries: list, by_dir: dict) -> Text:
        dir_name = dir_path.split("/")[-1]
        # Aggregate intensity for directory
        all_entries = by_dir.get(dir_path, [])
        if all_entries:
            avg_intensity = sum(e.intensity for e in all_entries) / len(all_entries)
        else:
            avg_intensity = 0.0
        color = intensity_to_color(avg_intensity)
        text = Text()
        text.append(f"[{dir_name}/]", style=f"bold {color}")
        return text
