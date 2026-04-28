# Evaluation Phase Prompt

## 角色

评估研究结果并给出 verdict。

## 评估流程

1. 读取包含所有 phase 结果的 research plan
2. 按 research-scoring.md 对每个维度评分：

| 维度 | 满分 |
|------|------|
| Hypothesis clarity | 1.0 |
| Data rigor | 1.0 |
| Strategy soundness | 1.0 |
| Performance | 1.0 |
| Robustness | 1.0 |

3. 检查过拟合信号：
   - 样本内 vs 样本外性能差距 > 50% → 很可能过拟合
   - 参数敏感性：小的变化导致大的性能波动 → 脆弱
   - 相对数据大小参数过多 → 过拟合
4. 确定 verdict：
   - 总分 ≥ 4.0 → GO
   - 总分 3.0-3.9 → NEEDS-WORK
   - 总分 < 3.0 → NO-GO

## 重要

- NO-GO verdict 是有效的研究结果，不是失败
- 负结果是宝贵的 — 它们防止在无效假设上浪费精力
- 不要为了避免 NO-GO 而虚报分数

## 输出

- 每个维度的分数和证据
- 总分
- Verdict (GO / NEEDS-WORK / NO-GO)
- 下一步具体反馈（如果是 NEEDS-WORK）
- 关键风险和注意事项
