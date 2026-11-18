# 荣耀 5.0 门店道具布局检测器

本项目用于读取荣耀 5.0 门店布局 JSON，解析门店边界、墙体、房间、入口、
柱体及多套道具方案，并按照布局规则自动检查每套方案。检测结果可导出为
JSON、Excel 以及带尺寸标注和不符合项摘要的平面图。

当前规则按以下 9 个模块组织：

1. 布置前确认事项
2. 一般要求
3. 体验台布局原则
4. 开机服务台布局原则
5. 配件柜布局原则
6. 灯箱布局原则
7. 画框布局原则
8. 其他道具布局原则
9. 禁止项

检测状态包括：`符合`、`不符合`、`警告`、`未校验`和`不涉及`。尚未实现的
规则不会以占位结果写入报告。

## 环境要求

- Python 3.10 或更高版本
- 依赖见 `requirements.txt`

推荐创建独立虚拟环境：

```bash
cd /path/to/honor_layout_check
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

项目当前也可直接复用既有 Python 3.12 环境：

```bash
/home/xuzhanpeng/conda/huawei4_py312/bin/python -m pip install -r requirements.txt
```

## 输入说明

输入文件为服务端生成的门店布局 JSON，可以包含多套布局方案。当前版本只
执行体验店规则：

- `brandType` 为空时识别为体验店；
- `brandType` 非空时识别为授权店，当前版本会停止并提示暂不支持。

JSON 中出现型号库未定义的道具时，程序会在终端及报告元数据中列出未知型号。

## 运行方法

在项目目录下执行。未指定 `--all` 或 `--scheme` 时，只检测第一套方案。

检测第一套方案：

```bash
python main.py /path/to/server_layout_result.json
```

检测 JSON 中全部方案：

```bash
python main.py /path/to/server_layout_result.json --all
```

检测指定方案，方案编号从 `0` 开始：

```bash
python main.py /path/to/server_layout_result.json --scheme 0
```

指定输出目录：

```bash
python main.py /path/to/server_layout_result.json --all \
  --out-dir /path/to/check_output
```

不生成平面图，只输出 JSON 和 Excel：

```bash
python main.py /path/to/server_layout_result.json --all --no-images
```

使用当前既有环境的完整示例：

```bash
cd /home/xuzhanpeng/ws1/honor_layout_check
/home/xuzhanpeng/conda/huawei4_py312/bin/python main.py \
  /home/xuzhanpeng/ws1/荣耀布局.json --all
```

## 输出文件

默认在输入 JSON 同级目录创建 `<输入文件名>_check/`：

```text
check_report.json               # 结构化检测结果及统计
check_report.xlsx               # 汇总表和各方案明细表
check_report_scheme_1.png       # 方案1检测平面图
check_report_scheme_2.png       # 方案2检测平面图
...
```

图片右侧只显示每条不符合规则的简短原因；完整规则详情和测量数据保留在
JSON 与 Excel 中。

## 退出码

- `0`：检测完成，未发现“不符合”项；
- `1`：检测和报告生成成功，但存在“不符合”项；
- `2`：输入文件、方案编号或门店类型等参数错误。

因此退出码 `1` 不表示程序崩溃，应结合生成的报告查看具体问题。

## 代码结构

```text
main.py                 命令行入口与报告导出
layout_data.py          JSON 解析和统一数据模型
model_specs.py          荣耀 5.0 道具型号、分类和规格
geometry_utils.py       通用几何计算工具
annotation_utils.py     平面图尺寸标注计算
renderer.py             检测平面图渲染
findings.py             检测状态以及 JSON/Excel 报告
rules/                  各规则模块
```
