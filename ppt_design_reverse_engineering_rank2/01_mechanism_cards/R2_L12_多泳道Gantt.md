# R2-L12｜多泳道 Gantt
## v3 执行合同

```json mechanism-card-v3
{
  "schema_version": "3.0",
  "id": "R2-L12",
  "name": "多泳道 Gantt",
  "relation_pattern": "single_group: matrix",
  "match_signature": {
    "group_count": {
      "min": 1,
      "max": 1
    },
    "between_groups": [
      "single_group"
    ],
    "groups": [
      {
        "relations": [
          "matrix"
        ],
        "count": {
          "min": 4,
          "max": 30
        },
        "order": "required",
        "position": "any"
      }
    ],
    "mapping": "none",
    "requires": [
      "time_axis",
      "precise_matrix"
    ],
    "forbids": []
  },
  "data_contract": {
    "legacy_slots": "{time_axis: 1, lanes: 2–8, tasks: 4–30, milestones: 1–8, dependencies: optional}"
  },
  "layout_contract": {
    "family": "gantt",
    "sizing": "adaptive",
    "geometry": [
      "横轴时间",
      "纵轴责任泳道",
      "任务条按持续期",
      "里程碑使用统一符号",
      "网格清晰可核读"
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
    "只有少数里程碑",
    "无并行任务或责任差异",
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
id: R2-L12
inherits: ../../ppt_design_mechanism_library/global_defaults.yaml
relation: teams_or_workstreams × time -> tasks_dependencies_milestones
match_when: [多团队/多任务并行且存在时间依赖, 需要精确执行审计]
reject_when: [只有少数里程碑, 无并行任务或责任差异]
slots: {time_axis: 1, lanes: 2–8, tasks: 4–30, milestones: 1–8, dependencies: optional}
layout_dna: [横轴时间, 纵轴责任泳道, 任务条按持续期, 里程碑使用统一符号, 网格清晰可核读]
qa_specific: [任务起止、责任人和依赖一致, 不为去框牺牲表格接口]
source: {reference: redacted}
```
