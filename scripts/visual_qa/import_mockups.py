from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
VECTOR_EXTS = {".svg"}


def safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)


def normalize_feature_name(name: str) -> str:
    stem = Path(name).stem
    for suffix in ("_mockup", "-mockup", "_preview", "-preview"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return safe_name(stem)


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def find_files(root: Path, exts: set[str]) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in exts]


def is_preview(path: Path) -> bool:
    return "preview" in path.stem.lower()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, help="Assets zip path")
    parser.add_argument("--project", required=True, help="Project root")
    parser.add_argument("--mockup-set", default=None, help="Destination mockup set. Defaults to project folder name.")
    parser.add_argument("--feature-prefix", default=None, help="Visual config id prefix. Defaults to --mockup-set.")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    project_root = Path(args.project).resolve()
    zip_path = Path(args.zip).resolve()

    if not project_root.exists():
        raise FileNotFoundError(f"Project not found: {project_root}")

    if not zip_path.exists():
        raise FileNotFoundError(f"Zip not found: {zip_path}")

    mockup_set = args.mockup_set or project_root.name
    feature_prefix = args.feature_prefix if args.feature_prefix is not None else mockup_set

    import_root = project_root / "assets" / "mockups" / mockup_set
    svg_root = import_root / "svg"
    import_root.mkdir(parents=True, exist_ok=True)
    svg_root.mkdir(parents=True, exist_ok=True)

    tmp = project_root / ".visual_qa_import_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    copied_png: list[dict] = []
    config_mockups: list[dict] = []
    copied_svg: list[str] = []

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(tmp)

        image_files = [p for p in find_files(tmp, IMAGE_EXTS) if not is_preview(p)]
        svg_files = find_files(tmp, VECTOR_EXTS)
        preview_files = [p for p in find_files(tmp, IMAGE_EXTS) if is_preview(p)]

        for src in image_files:
            dest = import_root / src.name
            feature_name = normalize_feature_name(src.name)

            if dest.exists() and not args.overwrite:
                print(f"EXISTS mockup: {dest}")
            else:
                shutil.copyfile(src, dest)
                copied_png.append({"feature": feature_name, "mockup": str(dest.relative_to(project_root)).replace("\\", "/")})
                print(f"MOCKUP {src.name} -> {dest}")

            # Always register for config, even if the asset already existed.
            config_mockups.append({"feature": feature_name, "mockup": str(dest.relative_to(project_root)).replace("\\", "/")})

        for src in svg_files:
            dest = svg_root / src.name
            if dest.exists() and not args.overwrite:
                print(f"EXISTS svg: {dest}")
                continue
            shutil.copyfile(src, dest)
            copied_svg.append(str(dest.relative_to(project_root)).replace("\\", "/"))
            print(f"SVG {src.name} -> {dest}")

        for src in preview_files:
            dest = import_root / src.name
            if dest.exists() and not args.overwrite:
                print(f"EXISTS preview: {dest}")
                continue
            shutil.copyfile(src, dest)
            print(f"PREVIEW {src.name} -> {dest}")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    visual_config_path = project_root / "visual_diff_config.json"
    visual_config = load_json(visual_config_path, [])
    existing_ids = {entry.get("id") for entry in visual_config if isinstance(entry, dict)}

    added_config = 0

    for item in config_mockups:
        feature = item["feature"]
        entry_id = f"{feature_prefix}.{feature}" if feature_prefix else feature

        if entry_id in existing_ids:
            print(f"CONFIG existing id, not duplicated: {entry_id}")
            continue

        visual_config.append({
            "op": "visual_diff",
            "id": entry_id,
            "name": feature.replace("_", " ").title(),
            "test": {"img": f"visual-checks/current/{entry_id}.png", "viewport": [0, 0, 1440, 900]},
            "ref": {"img": item["mockup"], "viewport": [0, 0, 1440, 900]},
            "out": {"diff": f"visual-checks/diffs/{entry_id}.diff.png"},
            "threshold": {"mean": 8.0, "max_changed_ratio": 0.12},
        })
        existing_ids.add(entry_id)
        added_config += 1
        print(f"CONFIG added: {entry_id}")

    write_json(visual_config_path, visual_config)

    acceptance_path = project_root / "visual_acceptance_spec.json"
    acceptance = load_json(acceptance_path, {"version": 1, "project": project_root.name, "features": {}})
    features = acceptance.setdefault("features", {})

    added_features = 0

    for item in config_mockups:
        feature = item["feature"]
        entry_id = f"{feature_prefix}.{feature}" if feature_prefix else feature

        if entry_id in features:
            print(f"ACCEPTANCE existing feature, not duplicated: {entry_id}")
            continue

        features[entry_id] = {
            "reference_mockup": item["mockup"],
            "visual_pass_means": [
                "The screenshot viewport matches the reference mockup viewport.",
                "Primary layout geometry matches.",
                "Spacing, alignment, and component proportions match.",
                "Colors and contrast match approved mockup intent.",
                "Important states shown in the mockup are reproduced.",
                "The visual diff passes thresholds and the diff image has no meaningful regressions."
            ],
            "required_tests": [
                "Functional test for the UI state represented by this mockup.",
                "Screenshot capture for this feature id.",
                "Visual diff entry in visual_diff_config.json.",
                "Regression run of the full visual_diff_config.json."
            ]
        }
        added_features += 1
        print(f"ACCEPTANCE added feature: {entry_id}")

    write_json(acceptance_path, acceptance)

    print(json.dumps({
        "mockups_copied": len(copied_png),
        "mockups_seen_for_config": len(config_mockups),
        "config_entries_added": added_config,
        "acceptance_features_added": added_features,
        "svgs_copied": len(copied_svg),
        "visual_diff_config": str(visual_config_path),
        "visual_acceptance_spec": str(acceptance_path)
    }, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

