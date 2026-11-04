from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from seal_stroke_split import SplitConfig, split_character_image
from seal_stroke_split.pipeline import save_result_artifacts


def _default_input_dir() -> Path:
    return ROOT / "data"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run seal-script stroke splitting experiments.")
    parser.add_argument("--input-dir", type=Path, default=_default_input_dir())
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "experiment")
    parser.add_argument("--threshold", type=int, default=0)
    parser.add_argument("--padding", type=int, default=3)
    parser.add_argument("--min-component-area", type=int, default=8)
    parser.add_argument("--direction-window", type=int, default=4)
    parser.add_argument("--split-angle-deg", type=float, default=55.0)
    parser.add_argument("--min-segment-points", type=int, default=5)
    parser.add_argument("--bridge-collapse-len", type=int, default=0)
    parser.add_argument("--short-segment-force-merge", type=int, default=3)
    parser.add_argument("--merge-angle-deg", type=float, default=28.0)
    parser.add_argument("--through-angle-deg", type=float, default=32.0)
    parser.add_argument("--max-endpoint-gap", type=float, default=2.5)
    parser.add_argument("--tiny-segment-points", type=int, default=8)
    parser.add_argument("--tiny-merge-distance", type=float, default=1.5)
    parser.add_argument("--min-region-area", type=int, default=10)
    parser.add_argument("--overlap-margin", type=float, default=1.35)
    return parser.parse_args()


def _collect_samples(input_dir: Path) -> list[tuple[str, Path]]:
    """收集待处理图片。

    返回 [(display_name, image_path), ...]：
      - 若 input_dir 下有子文件夹：每个子文件夹当一个字，
        display_name = "子文件夹名/文件名.png"
      - 否则：input_dir 直接放图片，
        display_name = "文件名.png"
    """
    samples: list[tuple[str, Path]] = []
    if not input_dir.exists():
        return samples

    has_subdirs = any(p.is_dir() for p in input_dir.iterdir())
    if has_subdirs:
        for sub in sorted(p for p in input_dir.iterdir() if p.is_dir()):
            for img in sorted(sub.glob("*.png")):
                samples.append((f"{sub.name}/{img.name}", img))
    else:
        for img in sorted(input_dir.glob("*.png")):
            samples.append((img.name, img))
    return samples


def _sample_output_dir(output_dir: Path, display_name: str) -> Path:
    """根据 display_name 决定单个样本的输出子目录，避免同名覆盖。

    "子文件夹名/文件名.png" -> output_dir / "子文件夹名" / "文件名"
    "文件名.png"            -> output_dir / "文件名"
    """
    rel = Path(display_name).with_suffix("")
    return output_dir / rel


def main() -> None:
    args = parse_args()
    config = SplitConfig(
        threshold=args.threshold,
        padding=args.padding,
        min_component_area=args.min_component_area,
        direction_window=args.direction_window,
        split_angle_deg=args.split_angle_deg,
        min_segment_points=args.min_segment_points,
        bridge_collapse_len=args.bridge_collapse_len,
        short_segment_force_merge=args.short_segment_force_merge,
        merge_angle_deg=args.merge_angle_deg,
        through_angle_deg=args.through_angle_deg,
        max_endpoint_gap=args.max_endpoint_gap,
        tiny_segment_points=args.tiny_segment_points,
        tiny_merge_distance=args.tiny_merge_distance,
        min_region_area=args.min_region_area,
        overlap_margin=args.overlap_margin,
    )
    input_dir = args.input_dir
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    samples = _collect_samples(input_dir)
    if not samples:
        print(f"no png found under: {input_dir}")
        return

    rows: list[str] = []
    records: list[dict] = []

    for display_name, image_path in samples:
        result = split_character_image(str(image_path), config)
        sample_dir = _sample_output_dir(output_dir, display_name)
        save_result_artifacts(result, sample_dir)
        rows.append(
            f"{display_name}\t{result.debug['segment_count']}\t"
            f"{result.debug['overlap_pixel_count']}\t{result.debug['segment_lengths']}"
        )
        records.append(
            {
                "image": display_name,
                "segment_count": result.debug["segment_count"],
                "overlap_pixel_count": result.debug["overlap_pixel_count"],
                "segment_lengths": result.debug["segment_lengths"],
            }
        )
        print(f"processed: {display_name} -> {sample_dir}")

    summary_path = output_dir / "summary.tsv"
    summary_path.write_text(
        "image\tsegment_count\toverlap_pixel_count\tsegment_lengths\n" + "\n".join(rows),
        encoding="utf-8",
    )
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "config": config.to_dict(),
                "results": records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"done: {summary_path}")


if __name__ == "__main__":
    main()