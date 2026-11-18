"""只在当前绘图进程中配置中文字体。"""

import os

_CJK_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def configure(matplotlib):
    if os.path.isfile(_CJK_FONT):
        from matplotlib import font_manager
        font_manager.fontManager.addfont(_CJK_FONT)
        matplotlib.rcParams["font.sans-serif"] = ["Noto Sans CJK JP", "DejaVu Sans"]
    else:
        matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
