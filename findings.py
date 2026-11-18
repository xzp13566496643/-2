"""检测结果和 JSON/Excel 报告。"""

import json
import re
from dataclasses import asdict, dataclass, field

SEV_ERROR = "error"
SEV_INFO = "info"
SEV_WARN = "warning"

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_WARN = "WARN"
STATUS_NOTCHECKED = "NOTCHECKED"
STATUS_NOT_RELEVANT = "NOT_RELEVANT"
VALID_STATUSES = {
    STATUS_PASS, STATUS_FAIL, STATUS_WARN,
    STATUS_NOTCHECKED, STATUS_NOT_RELEVANT,
}
STATUS_LABELS = {
    STATUS_PASS: "符合",
    STATUS_FAIL: "不符合",
    STATUS_WARN: "警告",
    STATUS_NOTCHECKED: "未校验",
    STATUS_NOT_RELEVANT: "不涉及",
}

MODULE_NAMES = {
    "prerequisites": "布置前确认事项",
    "general": "一般要求",
    "experience_table": "体验台布局原则",
    "service_desk": "开机服务台布局原则",
    "accessory_cabinet": "配件柜布局原则",
    "light_box": "灯箱布局原则",
    "picture_frame": "画框布局原则",
    "other_props": "其他道具布局原则",
    "prohibited": "禁止项生成",
}

# 各规则文件内部独立从1开始编号；报告输出时自动换算为总体序号。
# 未实现的规则仍占据它在模块中的位置，但不生成Finding。
MODULE_RULE_COUNTS = {
    "prerequisites": 3,
    "general": 12,
    "experience_table": 12,
    "service_desk": 3,
    "accessory_cabinet": 11,
    "light_box": 7,
    "picture_frame": 2,
    "other_props": 4,
    "prohibited": 3,
}


def global_rule_id(module, local_rule_id):
    """将模块内序号换算为报告总体序号。"""
    try:
        local = int(str(local_rule_id))
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"模块内规则序号必须为整数：{local_rule_id!r}") from error
    if module not in MODULE_RULE_COUNTS:
        raise ValueError(f"未配置规则数的模块：{module!r}")
    if not 1 <= local <= MODULE_RULE_COUNTS[module]:
        raise ValueError(
            f"模块{module}的规则序号{local}超出"
            f"1–{MODULE_RULE_COUNTS[module]}")
    offset = 0
    for current, count in MODULE_RULE_COUNTS.items():
        if current == module:
            break
        offset += count
    return str(offset + local)


@dataclass
class Finding:
    rule_id: str
    module: str
    title: str
    status: str
    severity: str = SEV_INFO
    scheme: int = -1
    detail: str = ""
    suggestion: str = ""
    local_rule_id: str = field(init=False)

    def __post_init__(self):
        self.local_rule_id = str(self.rule_id)
        self.rule_id = global_rule_id(self.module, self.local_rule_id)
        # 兼容当前仍只计算符合/不符合的规则调用；Finding内部和对外接口
        # 一律保存明确状态字符串。后续规则可直接传入其余三种状态。
        if isinstance(self.status, bool):
            self.status = STATUS_PASS if self.status else STATUS_FAIL
        if self.status not in VALID_STATUSES:
            raise ValueError(f"无效结果状态：{self.status!r}")

    @property
    def passed(self):
        return self.status == STATUS_PASS

    @property
    def failed(self):
        return self.status == STATUS_FAIL

    def to_dict(self):
        return asdict(self)


@dataclass
class Report:
    metadata: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)

    def extend(self, items):
        self.findings.extend(items)

    def summary(self):
        counts = {
            "total": len(self.findings),
            STATUS_PASS: 0,
            STATUS_FAIL: 0,
            STATUS_WARN: 0,
            STATUS_NOTCHECKED: 0,
            STATUS_NOT_RELEVANT: 0,
        }
        for item in self.findings:
            counts[item.status] += 1
        return counts

    def to_dict(self):
        return {
            "metadata": self.metadata,
            "summary": self.summary(),
            "findings": [item.to_dict() for item in self.findings],
        }

    def save_json(self, path):
        with open(path, "w", encoding="utf-8") as stream:
            json.dump(self.to_dict(), stream, ensure_ascii=False, indent=2)

    def save_xlsx(self, path):
        """按原项目格式导出「汇总」及每方案一张「明细」表。"""
        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

        book = openpyxl.Workbook()
        white_bold = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="305496")
        thin = Side(style="thin", color="BFBFBF")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left_wrap = Alignment(horizontal="left", vertical="center", wrap_text=True)
        status_style = {
            STATUS_PASS: (PatternFill("solid", fgColor="C6EFCE"), Font(color="006100")),
            STATUS_FAIL: (PatternFill("solid", fgColor="FFC7CE"), Font(color="9C0006")),
            STATUS_WARN: (PatternFill("solid", fgColor="FFEB9C"), Font(color="9C6500")),
            STATUS_NOTCHECKED: (PatternFill("solid", fgColor="D9D9D9"), Font(color="808080")),
            STATUS_NOT_RELEVANT: (PatternFill("solid", fgColor="E2EFDA"), Font(color="548235")),
        }

        def module_label(slug):
            name = MODULE_NAMES.get(slug)
            return f"{name}\n{slug}" if name else slug

        def sort_key(item):
            text = str(item.rule_id)
            match = re.fullmatch(r"(\d+)(?:\.(\d+))?", text)
            rule = ((0, int(match.group(1)), int(match.group(2) or 0))
                    if match else (1, text, 0))
            return rule, item.scheme, item.module

        def write_header(ws, row, headers):
            for index, text in enumerate(headers, 1):
                cell = ws.cell(row, index, text)
                cell.font = white_bold
                cell.fill = header_fill
                cell.alignment = center
                cell.border = border

        # ---------- Sheet 1: 汇总 ----------
        ws = book.active
        ws.title = "汇总"
        ws["A1"] = "荣耀5.0 门店平面布局校验报告"
        ws["A1"].font = Font(bold=True, size=14)
        ws.merge_cells("A1:D1")
        ws["A1"].alignment = Alignment(horizontal="left", vertical="center")

        ws["A3"] = "总体统计"
        ws["A3"].font = Font(bold=True)
        write_header(ws, 4, ["指标", "数量"])
        summary = self.summary()
        summary_rows = [("总计", summary["total"])] + [
            (STATUS_LABELS[status], summary[status])
            for status in (STATUS_PASS, STATUS_FAIL, STATUS_WARN,
                           STATUS_NOTCHECKED, STATUS_NOT_RELEVANT)
        ]
        for row_index, row in enumerate(summary_rows, 5):
            for column, value in enumerate(row, 1):
                cell = ws.cell(row_index, column, value)
                cell.border = border
                cell.alignment = left_wrap if column == 1 else center

        by_module = {}
        for item in self.findings:
            by_module.setdefault(item.module, []).append(item)
        module_order = list(MODULE_NAMES) + [
            module for module in by_module if module not in MODULE_NAMES
        ]

        row_index = 12
        ws.cell(row_index, 1, "按模块统计").font = Font(bold=True)
        row_index += 1
        module_statuses = (STATUS_PASS, STATUS_FAIL, STATUS_WARN,
                           STATUS_NOTCHECKED, STATUS_NOT_RELEVANT)
        write_header(
            ws, row_index,
            ["模块"] + [STATUS_LABELS[status] for status in module_statuses]
            + ["小计"])
        row_index += 1
        for module in module_order:
            items = by_module.get(module, [])
            if not items:
                continue
            row = [module_label(module)]
            row.extend(sum(item.status == status for item in items)
                       for status in module_statuses)
            row.append(len(items))
            for column, value in enumerate(row, 1):
                cell = ws.cell(row_index, column, value)
                cell.border = border
                cell.alignment = left_wrap if column == 1 else center
            row_index += 1
        ws.column_dimensions["A"].width = 24
        for column in ("B", "C", "D", "E", "F", "G"):
            ws.column_dimensions[column].width = 10

        # ---------- Sheet 2..N: 每方案一张明细表 ----------
        global_items = [item for item in self.findings if item.scheme == -1]
        by_scheme = {}
        for item in self.findings:
            if item.scheme >= 0:
                by_scheme.setdefault(item.scheme, []).append(item)
        if not by_scheme:
            by_scheme[0] = []
        sheet_names = (
            {next(iter(by_scheme)): "明细"}
            if len(by_scheme) == 1
            else {scheme: f"明细-方案{scheme}" for scheme in sorted(by_scheme)}
        )

        headers = ["序号", "模块", "方案", "结果", "规则要点", "详情", "建议"]
        for scheme in sorted(by_scheme):
            detail_ws = book.create_sheet(sheet_names[scheme])
            write_header(detail_ws, 1, headers)
            detail_ws.row_dimensions[1].height = 20
            items = sorted(global_items + by_scheme[scheme], key=sort_key)
            for row_index, item in enumerate(items, 2):
                row = [
                    item.rule_id, module_label(item.module),
                    "全局" if item.scheme < 0 else item.scheme,
                    STATUS_LABELS[item.status],
                    item.title, item.detail, item.suggestion,
                ]
                for column, value in enumerate(row, 1):
                    cell = detail_ws.cell(row_index, column, value)
                    cell.border = border
                    cell.alignment = center if column in (1, 3, 4) else left_wrap
                fill, font = status_style[item.status]
                detail_ws.cell(row_index, 4).fill = fill
                detail_ws.cell(row_index, 4).font = font
            detail_ws.freeze_panes = "A2"
            widths = {"A": 6, "B": 24, "C": 8, "D": 10,
                      "E": 38, "F": 54, "G": 30}
            for column, width in widths.items():
                detail_ws.column_dimensions[column].width = width

        book.save(path)
        return path

    def text(self):
        data = self.summary()
        return (f"共 {data['total']} 条：符合 {data[STATUS_PASS]}，"
                f"不符合 {data[STATUS_FAIL]}，警告 {data[STATUS_WARN]}，"
                f"未校验 {data[STATUS_NOTCHECKED]}，"
                f"不涉及 {data[STATUS_NOT_RELEVANT]}")
