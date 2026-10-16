# PPT Mechanism Library

AI读取顺序：

1. 当前页 `page_structures/page_XX.json`
2. `relation_taxonomy.json`
3. `mechanism_registry.yaml`
4. 候选执行卡顶部的 `mechanism-card-v3` 合同
5. 命中卡片的布局、编码与适配合同

匹配执行硬门槛：组间关系、组内关系、顺序、映射、容量和证据形态。区域比例不参与硬匹配，命中后按内容量自适应。Rank来源文件和卡片下方旧YAML只负责溯源，不参与行业匹配。
