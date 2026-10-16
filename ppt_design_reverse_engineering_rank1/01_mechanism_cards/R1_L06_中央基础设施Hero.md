# R1-L06｜中央基础设施 Hero
## v3 执行合同

```json mechanism-card-v3
{
  "schema_version": "3.0",
  "id": "R1-L06",
  "name": "中央基础设施 Hero",
  "relation_pattern": "source_to_result: single_anchor + parallel_equal",
  "match_signature": {
    "group_count": {
      "min": 2,
      "max": 2
    },
    "between_groups": [
      "source_to_result"
    ],
    "groups": [
      {
        "relations": [
          "single_anchor"
        ],
        "count": {
          "min": 1,
          "max": 1
        },
        "order": "none",
        "position": "center"
      },
      {
        "relations": [
          "parallel_equal"
        ],
        "count": {
          "min": 3,
          "max": 6
        },
        "order": "none",
        "position": "outer"
      }
    ],
    "mapping": "none",
    "requires": [
      "hero_asset"
    ],
    "forbids": []
  },
  "data_contract": {
    "legacy_slots": "{hero_asset: 1, capabilities: 3–6, evidence: 0–2_per_capability}"
  },
  "layout_contract": {
    "family": "hero_with_satellites",
    "sizing": "adaptive",
    "geometry": [
      "中央大幅资产图承担空间锚点",
      "能力沿周边挂载并指向对应部位或作用",
      "文字面积低于Hero"
    ]
  },
  "encoding_contract": {
    "priority": "先执行关系与几何编码",
    "fallback": "未覆盖的数字按数学属性和比较目的使用全局数字编码规则",
    "style": "项目样式令牌后置注入"
  },
  "adaptation": [
    "区域比例按实际内容量自适应，不参与硬匹配",
    "项目数量超出槽位范围时由上游重新分组、拆页或更换机制",
    "不得为适配版式虚构内容、顺序、映射或权重"
  ],
  "hard_fail": [
    "图片仅作装饰",
    "多项能力与中央资产无直接联系",
    "页面关系不满足match_signature",
    "改变原内容的并列、顺序、层级或映射关系",
    "为填满版式虚构内容",
    "缺少执行卡要求的证据形态或结构条件"
  ],
  "source": {
    "reference": "redacted"
  }
}
```

> 以下为原拆解注释，仅用于溯源和人工复核，不参与机器匹配。

```yaml
id: R1-L06
inherits: ../../ppt_design_mechanism_library/global_defaults.yaml
relation: one_physical_or_system_asset -> multiple_capabilities
match_when: [一项实体或系统资产同时支撑多项能力, 资产本身具有可识别空间结构]
reject_when: [图片仅作装饰, 多项能力与中央资产无直接联系]
slots: {hero_asset: 1, capabilities: 3–6, evidence: 0–2_per_capability}
layout_dna: [中央大幅资产图承担空间锚点, 能力沿周边挂载并指向对应部位或作用, 文字面积低于Hero]
asset_notes: [Hero优先使用真实照片、等距示意或生成中性结构图, 不保留项目专属原图]
qa_specific: [删除Hero会破坏结构而不仅是审美, 每项能力可回指中央资产]
source: {reference: redacted}
```
