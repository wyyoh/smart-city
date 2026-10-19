NAMES = {
    'DS': '动稳定度', 'strain': '最大弯拉应变', 'TSR': '冻融劈裂强度比', 'residual': '残留稳定度',
    'PG_grade': 'PG等级', 'fatigue_life': '疲劳寿命', 'dynamic_modulus': '动态模量',
    'temperature': '试验温度', 'load': '荷载', 'conditioning': '试件处理', 'loading_rate': '加载速率',
    'aging': '老化条件', 'frequency': '频率', 'compaction': '压实条件', 'test_method': '试验方法',
    'unit': '单位', 'data_scope': '数据范围', 'maintenance_method': '养护工法', 'layer': '结构层位',
    'structure_type': '路面结构', 'mixing_window': '拌和窗口', 'compaction_window': '压实窗口',
    'equipment': '设备', 'modifier': '改性剂', 'additive': '功能助剂', 'rap_nominal_pct': '名义RAP及质量基准',
    'source_code': '来源标识', 'product': '产品标识', 'gradation': '级配', 'oil_stone_ratio_pct': '油石比',
    'binder_content_pct': '计算沥青用量', 'budget': '预算', 'carbon_cap': '碳排上限', 'schedule_days': '供货期限',
}


def label(value):
    return NAMES.get(value.removeprefix('condition.'), value)
