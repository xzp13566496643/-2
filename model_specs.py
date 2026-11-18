"""荣耀 5.0 道具规格。

型号及尺寸来自《品牌店铺道具设计规格总表》。尺寸统一由毫米换算为米；
规格表未提供的尺寸记为 ``0.0``，不自行推测。

``MODEL_SPECS`` 保持旧接口：名称 -> (分类, 长, 宽, 高)。
``MODEL_ATTRIBUTES`` 保存层板/挂钩、主题等扩展属性。
"""


MODEL_SPECS = {
    # 体验店靠墙道具
    "5.0-体验店授权牌": ("authorization_sign", 0.3, 0.02, 0.39),
    "授权牌": ("authorization_sign", 0.3, 0.02, 0.39),
    "5.0-阿尔法logo": ("logo", 0.32, 0.24, 0.0),
    "5.0-3.6m灯箱配件柜": ("lightbox_cabinet", 3.6, 0.44, 1.225),
    "5.0-2.4m灯箱配件柜-数字系列-自研音频": (
        "lightbox_cabinet", 2.4, 0.44, 2.7),
    "5.0-2.4m灯箱配件柜-MAGIC系列-自研穿戴": (
        "lightbox_cabinet", 2.4, 0.44, 0.0),
    "5.0-2.4x2.7hx0.44智能家居": ("theme_cabinet", 2.4, 0.44, 2.7),
    "5.0-2.4x2.7hx0.44智慧教育": ("theme_cabinet", 2.4, 0.44, 2.7),
    "5.0-2.4x2.7hx0.44智慧出行": ("theme_cabinet", 2.4, 0.44, 2.7),
    "5.0-2.4x2.7hx0.44智宠陪伴": ("theme_cabinet", 2.4, 0.44, 2.7),
    "5.0-2.4x2.7hx0.44运动健康": ("theme_cabinet", 2.4, 0.44, 2.7),
    "5.0-2.4x2.7hx0.44游戏竞技": ("theme_cabinet", 2.4, 0.44, 2.7),
    "5.0-2.4x2.7hx0.44影音娱乐": ("theme_cabinet", 2.4, 0.44, 2.7),
    "5.0-1.2m影音娱乐（板）": ("theme_cabinet", 1.2, 0.43, 2.098),
    # 原表该型号长度栏为“1”，其余尺寸为空；不把明显异常值当作尺寸。
    "5.0-2.4x2.7hx0.44耀享智能": ("theme_cabinet", 0.0, 0.0, 0.0),
    "5.0-2.4x2.7hx0.44潮玩配件": ("theme_cabinet", 2.4, 0.44, 2.7),
    "5.0-1.2m潮玩配件（挂钩）": ("theme_cabinet", 1.2, 0.44, 2.7),
    "5.0-2.4x2.7hx0.44影像创作": ("imaging_cabinet", 2.4, 0.44, 2.7),
    "5.0-2.4x0.44影像创作": ("imaging_cabinet", 2.4, 0.44, 2.7),
    "5.0-1.2m影像创作": ("imaging_cabinet", 1.2, 0.44, 2.7),
    "5.0-1.2m包柱灯箱-影像创作": ("imaging_cabinet", 1.2, 0.44, 2.7),
    "5.0-2.4m咖啡柜": ("coffee_cabinet", 2.4, 0.44, 2.7),
    "5.0-1.2m咖啡柜": ("coffee_cabinet", 1.2, 0.44, 2.7),
    "5.0-侧边封口板": ("side_end_panel", 0.1, 0.4, 2.8),

    # 通用模型
    "5.0-1.6m体验台": ("experience_table", 1.6, 0.9, 0.9),
    "5.0-2m体验台-M系列体验台": ("experience_table", 2.0, 0.9, 0.9),
    "5.0-2m体验台-V旗舰品体验台": ("experience_table", 2.0, 0.9, 0.9),
    "5.0-2m体验台-平板pc体验台": ("experience_table", 2.0, 0.9, 0.9),
    "5.0-2m体验台-数字系列体验台": ("experience_table", 2.0, 0.9, 0.9),
    "5.0-2.4m体验台-M系列体验台": ("experience_table", 2.4, 0.9, 0.9),
    "5.0-2.4m体验台-V旗舰品体验台": ("experience_table", 2.4, 0.9, 0.9),
    "5.0-2.4m体验台-平板pc体验台": ("experience_table", 2.4, 0.9, 0.9),
    "5.0-2.4m体验台-数字系列体验台": ("experience_table", 2.4, 0.9, 0.9),
    "5.0-3m体验台-M系列体验台": ("experience_table", 3.0, 1.2, 0.9),
    "5.0-3m体验台-V旗舰系列体验台": ("experience_table", 3.0, 1.2, 0.9),
    "5.0-3m体验台-X系列体验台": ("experience_table", 3.0, 1.2, 0.9),
    "5.0-3m体验台-办公场景": ("experience_table", 3.0, 1.2, 0.9),
    "5.0-3m体验台-教育场景": ("experience_table", 3.0, 1.2, 0.9),
    "5.0-3m体验台-平板pc体验台": ("experience_table", 3.0, 1.2, 0.9),
    "5.0-3m体验台-数字系列体验台": ("experience_table", 3.0, 1.2, 0.9),
    "5.0-2.4m综合交机桌": ("service_desk", 2.4, 1.0, 0.9),
    "5.0-3m综合交机桌": ("service_desk", 3.0, 1.2, 0.9),
    "5.0-吧台椅": ("bar_stool", 0.454, 0.373, 0.0),
    "5.0-吧台椅无靠背": ("bar_stool", 0.223, 0.223, 0.0),
    "5.0-挂画": ("picture_frame", 0.6, 0.035, 0.9),
    "5.0-手机支架-花槽-含绿植": ("plant_phone_stand", 0.94, 0.55, 0.0),
    "5.0-组合展柜-绿植柜": ("plant_display_cabinet", 0.6, 0.45, 0.0),
    "5.0-组合展柜-储物展柜": ("combination_display", 0.6, 0.3, 0.0),
    "5.0-组合展柜-高展柜": ("combination_display", 0.3, 0.3, 0.0),
    "5.0-组合展柜-座椅": ("combination_seat", 0.6, 0.45, 0.0),

    # 授权专区
    "5.0-1.2m边柜": ("side_cabinet", 1.2, 0.35, 0.9),
    "5.0-1.2m层板配件柜": ("shelf_cabinet", 1.2, 0.44, 0.9),
    "5.0-1.2m灯箱": ("light_box", 1.195, 0.08, 1.19),
    "5.0-1.2m挂钩配件柜": ("hook_cabinet", 1.2, 0.44, 0.9),
    "5.0-2.4m层板配件柜-带背板": ("shelf_cabinet", 2.4, 0.479, 2.698),
    "5.0-2.4m灯箱": ("light_box", 2.395, 0.08, 1.19),
    "5.0-2.4m灯箱边柜": ("lightbox_side_cabinet", 2.395, 0.08, 1.19),
    "5.0-2.4m影像创作配件柜": ("imaging_cabinet", 2.395, 0.08, 1.19),
    "5.0-3.6m层板配件柜": ("shelf_cabinet", 3.6, 0.43, 1.196),
    "5.0-3.6m灯箱": ("light_box", 3.57, 0.08, 1.19),
    "5.0-3.6m灯箱边柜": ("lightbox_side_cabinet", 3.57, 0.08, 1.19),
    "5.0-3.6m挂钩配件柜-带背板": ("hook_cabinet", 3.6, 0.43, 1.196),
    "5.0-3.6m影像创作配件柜": ("imaging_cabinet", 3.57, 0.08, 1.19),
    "5.0-封闭柜": ("closed_cabinet", 1.2, 0.55, 0.0),
    "5.0-收银台": ("cash_desk", 0.912, 0.757, 0.0),

    # 背景墙灯箱与背景墙灯箱柜为同一道具类别。
    "5.0-L2400灯箱": ("background_lightbox_cabinet", 2.4, 0.1, 1.2),
    "5.0-L3600灯箱": ("background_lightbox_cabinet", 3.6, 0.1, 1.2),
    "5.0-L4800灯箱": ("background_lightbox_cabinet", 4.8, 0.1, 1.2),

    # 当前样例JSON和旧版名称兼容。
    "2400体验台": ("experience_table", 2.4, 0.9, 0.9),
    "3000体验台": ("experience_table", 3.0, 1.2, 0.9),
    "3000服务台": ("service_desk", 3.0, 1.2, 0.9),
    "L1800收银台": ("cash_desk", 1.8, 0.6, 1.15),
    "L2400灯箱": ("background_lightbox_cabinet", 2.4, 0.1, 1.2),
    "L3600灯箱": ("background_lightbox_cabinet", 3.6, 0.1, 1.2),
}


# 只有规格表或已经确认的规则能够确定的属性才在这里填写。
MODEL_ATTRIBUTES = {
    "5.0-L2400灯箱": {"fixture_type": "background_lightbox"},
    "5.0-L3600灯箱": {"fixture_type": "background_lightbox"},
    "5.0-L4800灯箱": {"fixture_type": "background_lightbox"},
    "L2400灯箱": {"fixture_type": "background_lightbox"},
    "L3600灯箱": {"fixture_type": "background_lightbox"},
    "5.0-侧边封口板": {"fixture_type": "end_panel"},
    "5.0-2.4x2.7hx0.44智能家居": {
        "theme": "智能家居", "cabinet_style": "shelf"},
    "5.0-2.4x2.7hx0.44运动健康": {
        "theme": "运动健康", "cabinet_style": "shelf"},
    "5.0-2.4x2.7hx0.44影音娱乐": {
        "theme": "影音娱乐", "cabinet_style": "shelf"},
    "5.0-1.2m影音娱乐（板）": {
        "theme": "影音娱乐", "cabinet_style": "shelf"},
    "5.0-2.4x2.7hx0.44潮玩配件": {
        "theme": "潮玩配件", "cabinet_style": "hook"},
    "5.0-1.2m潮玩配件（挂钩）": {
        "theme": "潮玩配件", "cabinet_style": "hook"},
    "5.0-2.4x2.7hx0.44影像创作": {"cabinet_style": "shelf"},
    "5.0-2.4x0.44影像创作": {"cabinet_style": "shelf"},
    "5.0-1.2m层板配件柜": {"cabinet_style": "shelf"},
    "5.0-2.4m层板配件柜-带背板": {"cabinet_style": "shelf"},
    "5.0-3.6m层板配件柜": {"cabinet_style": "shelf"},
    "5.0-1.2m挂钩配件柜": {"cabinet_style": "hook"},
    "5.0-3.6m挂钩配件柜-带背板": {"cabinet_style": "hook"},
}


def lookup(name):
    """返回 ``(category, length, width, height)``；未知型号返回None。"""
    return MODEL_SPECS.get(name)


def lookup_attributes(name):
    """返回型号扩展属性的副本；没有扩展属性时返回空字典。"""
    return dict(MODEL_ATTRIBUTES.get(name, {}))
