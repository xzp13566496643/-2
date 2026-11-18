"""荣耀 5.0 门店道具布局检测器入口。"""

import argparse
import os
import sys

import layout_data
from findings import Report, STATUS_FAIL
from rules import CHECKERS


def select_schemes(ctx, all_schemes=False, scheme=None):
    if scheme is not None:
        if scheme < 0 or scheme >= len(ctx.schemes):
            raise ValueError(f"方案编号 {scheme} 越界，共 {len(ctx.schemes)} 套")
        return [ctx.schemes[scheme]]
    return ctx.schemes if all_schemes else ctx.schemes[:1]


def run_checkers(ctx, schemes):
    report = Report(metadata={
        "source": os.path.abspath(ctx.source_path),
        "brand": ctx.brand,
        "brandType": ctx.brand_type,
        "storeType": ctx.store_type,
        "modelLibrary": ctx.model_library,
        "schemeCount": len(ctx.schemes),
        "checkedSchemes": [scheme.index for scheme in schemes],
        "unknownModels": ctx.unknown_models,
    })
    for checker in CHECKERS:
        report.extend(checker.check(ctx, schemes))
    return report


def export_report(ctx, schemes, report, out_dir, render_images=True):
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "check_report.json")
    report.save_json(json_path)
    outputs = [json_path]
    try:
        xlsx_path = os.path.join(out_dir, "check_report.xlsx")
        report.save_xlsx(xlsx_path)
        outputs.append(xlsx_path)
    except ImportError:
        print("(跳过 Excel：未安装 openpyxl)")

    if render_images:
        try:
            import renderer
            for scheme in schemes:
                check_image_path = os.path.join(out_dir, f"check_report_scheme_{scheme.index + 1}.png")
                renderer.render(ctx, scheme, check_image_path, report)
                outputs.append(check_image_path)
        except (ImportError, AttributeError) as exc:
            print(f"(跳过图片：matplotlib 环境不可用：{exc})")
    return outputs


def build_parser():
    parser = argparse.ArgumentParser(description="荣耀 5.0 门店道具布局检测器")
    parser.add_argument("input", help="server_layout_result.json 路径")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="检测 JSON 内全部方案")
    group.add_argument("--scheme", type=int, help="仅检测指定方案（0-based）")
    parser.add_argument("--out-dir", help="输出目录，默认在输入文件旁创建 <文件名>_check")
    parser.add_argument("--no-images", action="store_true", help="不生成布局图")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        ctx = layout_data.load(args.input)
        if ctx.store_type != "experience":
            raise ValueError(
                f"brandType={ctx.brand_type!r}，识别为授权店；当前骨架仅支持体验店")
        schemes = select_schemes(ctx, args.all, args.scheme)
    except (OSError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    stem = os.path.splitext(os.path.basename(args.input))[0]
    out_dir = args.out_dir or os.path.join(os.path.dirname(os.path.abspath(args.input)), stem + "_check")
    report = run_checkers(ctx, schemes)
    outputs = export_report(ctx, schemes, report, out_dir, not args.no_images)

    print(f"品牌={ctx.brand}，型号库={ctx.model_library}，门店类型=体验店")
    print(f"JSON 中共 {len(ctx.schemes)} 套方案，本次处理 {len(schemes)} 套")
    print(report.text())
    if ctx.unknown_models:
        print("未知型号：" + "、".join(ctx.unknown_models))
    print("输出：")
    for path in outputs:
        print(f"  {path}")
    return 1 if report.summary()[STATUS_FAIL] else 0


if __name__ == "__main__":
    raise SystemExit(main())
