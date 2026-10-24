"""Import-direction test: walks src/knx_agent with ast and checks the layer rules."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "knx_agent"
LAYERS = {"domain", "application", "adapters", "sdk", "cli", "agent_layer", "contracts"}
# Allowed knx_agent sub-package imports per layer (besides itself).
ALLOWED = {
    "contracts": set(),
    "domain": set(),
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
