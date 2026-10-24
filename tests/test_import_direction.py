"""Import-direction test: walks src/knx_agent with ast and checks the layer rules."""

import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "knx_agent"
LAYERS = {"domain", "application", "adapters", "sdk", "cli", "agent_layer", "contracts"}
# Allowed knx_agent sub-package imports per layer (besides itself).
ALLOWED = {
    "contracts": set(),
    "domain": {"contracts"},  # story 05: selectors raise KnxAgentError, views build contract models (003 layer model)
    "application": {"domain", "contracts"},
    "sdk": {"application", "domain", "contracts"},
    "cli": {"sdk", "contracts"},
    "adapters": {"sdk", "contracts"},
    "agent_layer": {"sdk", "contracts"},
}


def _imported_layers(path: Path, package_parts: list[str]) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package_parts[: len(package_parts) - node.level + 1]
                names = [".".join(base + ([node.module] if node.module else []))]
                if not node.module:
                    names = [".".join(base + [a.name]) for a in node.names]
            else:
                names = [node.module or ""]
                if node.module == "knx_agent":
                    names += [f"knx_agent.{a.name}" for a in node.names]
        else:
            continue
        for name in names:
            parts = name.split(".")
            if parts[0] == "knx_agent" and len(parts) > 1 and parts[1] in LAYERS:
                found.add(parts[1])
    return found


def _top_level_imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_domain_and_contracts_are_pure():
    """Story 04: no I/O, archive or XML libraries in domain (graph model, derivation, diff) or contracts."""
    forbidden = {"os", "io", "zipfile", "pathlib", "shutil", "subprocess", "socket", "hashlib", "yaml", "xml", "lxml", "logging"}
    allowed_third_party = {"pydantic"}
    for layer in ("domain", "contracts"):
        for path in sorted((SRC / layer).glob("*.py")):
            imports = _top_level_imports(path)
            assert not imports & forbidden, f"{path.relative_to(SRC)} imports {imports & forbidden}"
            assert not imports & {"xknxproject"}, path
            extra = {name for name in imports if name not in sys.stdlib_module_names and name not in allowed_third_party | {"knx_agent"}}
            assert not extra, f"{path.relative_to(SRC)} imports unexpected third-party modules {extra}"


def test_contracts_import_nothing_from_knx_agent():
    for path in sorted((SRC / "contracts").glob("*.py")):
        assert "knx_agent" not in _top_level_imports(path), path


def test_no_module_under_src_imports_xknxproject_or_lxml():
    for path in sorted(SRC.rglob("*.py")):
        assert not _top_level_imports(path) & {"xknxproject", "lxml"}, path


def test_layer_import_direction():
    violations = []
    files = sorted(SRC.rglob("*.py"))
    assert files
    for path in files:
        rel = path.relative_to(SRC.parent).with_suffix("")
        parts = list(rel.parts)
        package_parts = parts[:-1]
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if len(parts) < 2:
            continue
        layer = parts[1]
        for imported in _imported_layers(path, package_parts):
            if imported != layer and imported not in ALLOWED[layer]:
                violations.append(f"{path.relative_to(SRC)}: {layer} imports {imported}")
    assert not violations, violations
