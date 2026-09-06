"""Export the OpenAPI (Swagger) document without starting the server.

    uv run python -m src.export_openapi                       # docs/openapi.json + docs/openapi.yaml
    uv run python -m src.export_openapi --format yaml
    uv run python -m src.export_openapi --server https://api.example.com --out-dir .

The document is whatever the running app serves at /openapi.json — generated from the
route signatures, so it cannot drift from the code. Regenerate after touching a route.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

from src.app.utils import color
from src.main import app


def build_spec(servers: list[str] | None = None) -> dict:
    """The same document FastAPI serves at /openapi.json.

    `servers` is injected here rather than on the app: the deployed base URL is a property
    of the handed-off file, not of the process generating it.
    """
    spec = app.openapi()
    if servers:
        spec["servers"] = [{"url": url} for url in servers]
    return spec


def dump(spec: dict, path: Path) -> None:
    if path.suffix == ".json":
        text = json.dumps(spec, indent=2, ensure_ascii=False) + "\n"
    else:
        text = yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=100)
    path.write_text(text, encoding="utf-8")
    color.ok(f"{path}  ({len(text.encode()) / 1024:.1f} KiB)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="export-openapi", description="Write the OpenAPI (Swagger) schema to disk"
    )
    parser.add_argument("--format", choices=("json", "yaml", "both"), default="both")
    parser.add_argument("--out-dir", type=Path, default=Path("docs"))
    parser.add_argument("--server", action="append", metavar="URL",
                        help="base URL to advertise in the document; repeatable")
    args = parser.parse_args(argv)

    spec = build_spec(args.server)
    schemas = spec.get("components", {}).get("schemas", {})

    color.title(f"{spec['info']['title']} {spec['info']['version']} — OpenAPI {spec['openapi']}")
    color.info(f"{len(spec['paths'])} paths, {len(schemas)} schemas")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for fmt in ("json", "yaml") if args.format == "both" else (args.format,):
        dump(spec, args.out_dir / f"openapi.{fmt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
