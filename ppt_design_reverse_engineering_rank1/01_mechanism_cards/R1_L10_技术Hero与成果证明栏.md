# R1-L10｜技术 Hero + 成果证明栏
## v3 执行合同

```json mechanism-card-v3
{
  "schema_version": "3.0",
  "id": "R1-L10",
  "name": "技术 Hero + 成果证明栏",
  "relation_pattern": "source_to_result: single_anchor + parallel_equal + evidence_set",
  "match_signature": {
    "group_count": {
      "min": 3,
      "max": 3
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
        "position": "left"
      },
      {
        "relations": [
          "parallel_equal"
        ],
        "count": {
          "min": 2,
          "max": 5
        },
        "order": "none",
        "position": "center"
      },
      {
        "relations": [
          "evidence_set"
        ],
        "count": {
          "min": 2,
          "max": 5
        },
        "order": "none",
        "position": "right"
      }
    ],
    "mapping": "none",
    "requires": [
      "hero_asset"
    ],
    "forbids": []
  },
  "data_contract": {
    "legacy_slots": "{hero: 1, capabilities: 2–5, outcomes: 2–5}"
  },
  "layout_contract": {
    "family": "hero_capability_outcome",
    "sizing": "adaptive",
    "geometry": [
      "左侧或中央大Hero",
      "中部能力说明",
      "右侧窄成果栏",
      "阅读顺序从来源到能力再到结果"
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
    "只有技术图片无结果",
    "Hero与能力无直接关系",
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
id: R1-L10
inherits: ../../ppt_design_mechanism_library/global_defaults.yaml
relation: enabling_technology_or_platform -> capabilities -> validated_outcomes
match_when: [技术/平台是能力来源, 存在可验证成果证明其价值]
reject_when: [只有技术图片无结果, Hero与能力无直接关系]
slots: {hero: 1, capabilities: 2–5, outcomes: 2–5}
layout_dna: [左侧或中央大Hero, 中部能力说明, 右侧窄成果栏, 阅读顺序从来源到能力再到结果]
asset_notes: [Hero可用结构图、设备图或系统界面, 成果优先数字/认证/客户]
qa_specific: [Hero不是装饰, 每个结果能回指至少一项能力]
source: {reference: redacted}
```
