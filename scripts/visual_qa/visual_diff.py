from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

PASS_MARK = "✅"
FAIL_MARK = "❌"
WARN_MARK = "⚠️"


def color(text: str, c: str) -> str:
    return f"{c}{text}{RESET}"


def load_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("visual diff config must be a JSON array")
    return data


def crop_viewport(img: Image.Image, viewport: list[int] | None) -> Image.Image:
    if viewport is None:
        return img

    if len(viewport) != 4:
        raise ValueError("viewport must be [left, top, right, bottom]")

    left, top, right, bottom = viewport

    if right <= left or bottom <= top:
        raise ValueError(f"invalid viewport: {viewport}")

    if left < 0 or top < 0 or right > img.width or bottom > img.height:
        raise ValueError(f"viewport {viewport} outside image bounds width={img.width}, height={img.height}")

    return img.crop((left, top, right, bottom))


def changed_ratio(diff: Image.Image) -> float:
    gray = diff.convert("L")
    changed = sum(1 for px in gray.getdata() if px != 0)
    total = gray.width * gray.height
    return changed / total if total else 0.0


def mean_diff(diff: Image.Image) -> float:
    stat = ImageStat.Stat(diff)
    return sum(stat.mean) / len(stat.mean)


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def default_report_path(config_path: Path) -> Path:
    return config_path.parent / "visual-checks" / "reports" / f"visual_qa_report_{timestamp_slug()}.md"


def default_diff_path(config_path: Path, name: str) -> Path:
    safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)
    return config_path.parent / "visual-checks" / "diffs" / f"{safe_name}.diff.png"


def resolve_path(config_path: Path, path_value: str) -> Path:
    p = Path(path_value)
    if p.is_absolute():
        return p

    cwd_candidate = Path.cwd() / p
    if cwd_candidate.exists():
        return cwd_candidate

    return config_path.parent / p


def output_path(config_path: Path, path_value: str | None, stable_id: str) -> Path:
    if path_value:
        p = Path(path_value)
        if p.is_absolute():
            return p
        return config_path.parent / p
    return default_diff_path(config_path, stable_id)


def run_visual_diff(item: dict[str, Any], config_path: Path) -> dict[str, Any]:
    name = item.get("name") or item.get("id") or "unnamed_visual_diff"
    stable_id = item.get("id", name)

    result: dict[str, Any] = {
        "id": stable_id,
        "name": name,
        "op": item.get("op"),
        "status": "FAIL",
        "reason": "",
        "mean": None,
        "changed_ratio": None,
        "mean_threshold": None,
        "changed_ratio_threshold": None,
        "test_img": None,
        "ref_img": None,
        "test_viewport": None,
        "ref_viewport": None,
        "diff": None,
    }

    if item.get("op") != "visual_diff":
        result["status"] = "SKIP"
        result["reason"] = f"unsupported op: {item.get('op')}"
        return result

    try:
        test = item["test"]
        ref = item["ref"]
        out = item.get("out", {})
        threshold = item.get("threshold", {})

        test_img_path = resolve_path(config_path, test["img"])
        ref_img_path = resolve_path(config_path, ref["img"])

        result["test_img"] = str(test_img_path)
        result["ref_img"] = str(ref_img_path)
        result["test_viewport"] = test.get("viewport")
        result["ref_viewport"] = ref.get("viewport")

        if not test_img_path.exists():
            result["reason"] = f"missing test image: {test_img_path}"
            return result

        if not ref_img_path.exists():
            result["reason"] = f"missing reference image: {ref_img_path}"
            return result

        test_img = Image.open(test_img_path).convert("RGB")
        ref_img = Image.open(ref_img_path).convert("RGB")

        test_crop = crop_viewport(test_img, test.get("viewport"))
        ref_crop = crop_viewport(ref_img, ref.get("viewport"))

        resized = False
        if test_crop.size != ref_crop.size:
            test_crop = test_crop.resize(ref_crop.size)
            resized = True

        diff = ImageChops.difference(ref_crop, test_crop)

        diff_path = output_path(config_path, out.get("diff"), str(stable_id))
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff.save(diff_path)

        score = mean_diff(diff)
        ratio = changed_ratio(diff)

        max_mean = float(threshold.get("mean", 10.0))
        max_ratio = float(threshold.get("max_changed_ratio", 0.15))

        passed = score <= max_mean and ratio <= max_ratio

        result["status"] = "PASS" if passed else "FAIL"
        result["reason"] = "ok" if passed else "threshold exceeded"
        result["mean"] = score
        result["changed_ratio"] = ratio
        result["mean_threshold"] = max_mean
        result["changed_ratio_threshold"] = max_ratio
        result["diff"] = str(diff_path)
        result["resized"] = resized

        return result

    except Exception as exc:
        result["reason"] = f"{type(exc).__name__}: {exc}"
        return result


def write_report(report_path: Path, config_path: Path, results: list[dict[str, Any]]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)

    passed = [r for r in results if r["status"] == "PASS"]
    failed = [r for r in results if r["status"] == "FAIL"]
    skipped = [r for r in results if r["status"] == "SKIP"]

    lines = [
        "# Visual QA Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Config: `{config_path}`",
        "",
        "## Summary",
        "",
        f"- {PASS_MARK} Passed: {len(passed)}",
        f"- {FAIL_MARK} Failed: {len(failed)}",
        f"- {WARN_MARK} Skipped: {len(skipped)}",
        "",
        "## Results",
        "",
    ]

    for r in results:
        mark = PASS_MARK if r["status"] == "PASS" else FAIL_MARK if r["status"] == "FAIL" else WARN_MARK
        lines.extend([
            f"### {mark} {r['id']}",
            "",
            f"Name: {r['name']}",
            "",
            f"Status: **{r['status']}**",
            "",
            f"Reason: {r['reason']}",
            "",
            f"Test image: `{r.get('test_img')}`",
            "",
            f"Reference image: `{r.get('ref_img')}`",
            "",
            f"Test viewport: `{r.get('test_viewport')}`",
            "",
            f"Reference viewport: `{r.get('ref_viewport')}`",
            "",
            f"Diff: `{r.get('diff')}`",
            "",
        ])

        if r.get("mean") is not None:
            lines.extend([
                f"Mean diff: `{r['mean']:.2f}` / threshold `{r['mean_threshold']:.2f}`",
                "",
                f"Changed ratio: `{r['changed_ratio']:.4f}` / threshold `{r['changed_ratio_threshold']:.4f}`",
                "",
            ])

        if r.get("resized"):
            lines.extend([f"{WARN_MARK} Test crop was resized to match reference crop.", ""])

    report_path.write_text("\n".join(lines), encoding="utf-8")


def print_console(results: list[dict[str, Any]], report_path: Path) -> None:
    passed = [r for r in results if r["status"] == "PASS"]
    failed = [r for r in results if r["status"] == "FAIL"]
    skipped = [r for r in results if r["status"] == "SKIP"]

    print("")
    print(color("Visual Diff Results", CYAN))
    print("-" * 72)

    for r in results:
        if r["status"] == "PASS":
            mark = color(PASS_MARK, GREEN)
            status = color("PASS", GREEN)
        elif r["status"] == "FAIL":
            mark = color(FAIL_MARK, RED)
            status = color("FAIL", RED)
        else:
            mark = color(WARN_MARK, YELLOW)
            status = color("SKIP", YELLOW)

        metrics = ""
        if r.get("mean") is not None:
            metrics = (
                f" mean={r['mean']:.2f}/{r['mean_threshold']:.2f}"
                f" changed={r['changed_ratio']:.4f}/{r['changed_ratio_threshold']:.4f}"
            )

        print(f"{mark} {status} {r['id']}{metrics}")

        if r["status"] != "PASS":
            print(f"   reason: {r['reason']}")

        if r.get("diff"):
            print(f"   diff: {r['diff']}")

    print("-" * 72)

    summary_status = color("PASS", GREEN) if not failed else color("FAIL", RED)
    print(
        f"Summary: {summary_status} | "
        f"{PASS_MARK} {len(passed)} passed | "
        f"{FAIL_MARK} {len(failed)} failed | "
        f"{WARN_MARK} {len(skipped)} skipped"
    )
    print(f"Report: {report_path}")
    print("")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--report", default=None)
    args = parser.parse_args()

    config_path = Path(args.config)
    items = load_json(config_path)
    results = [run_visual_diff(item, config_path) for item in items]
    report_path = Path(args.report) if args.report else default_report_path(config_path)

    write_report(report_path, config_path, results)
    print_console(results, report_path)

    return 1 if any(r["status"] == "FAIL" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

