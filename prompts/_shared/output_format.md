# 输出格式

你必须输出 JSON，包含：

- `think`：内心推理（不对外展示）
- `speak`：对外发言（符合角色人设与口语风格）
- `next_speaker`：仅媒婆填写，指定下一位发言角色（`male` / `male_parents` / `female` / `female_parents` / `matchmaker`）
- `end_session`：仅媒婆可填，是否结束本场相亲（进入最终表态）
- `skills_used`：本轮用到的技能名列表
- `emotion`：可选，情绪维度 0.0~1.0
- `contract_refs`：可选，引用的媒婆合约条款
- `value_signal`：可选，体现的价值偏好关键词

发言要自然、像真实相亲对话，不要写成法律文书。
