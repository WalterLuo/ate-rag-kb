### 检查表

| 序号 | 问题 | 使用 MCP | 内容相关 | 含 source_md | 含 section_title | 无幻觉 | 通过 | 回答步骤 |
|------|------|----------|----------|--------------|------------------|--------|------|------------------|
| 1 | smt7中，如何在测试代码中通过代码的方式写limit | [是] | [1、方式一：使用 LIMIT 宏/类（最常用）LIMIT 是一个数据容器类，用于在代码中动态指定上下限和比较操作符。对于此方式的回答中缺少：Syntax:
LIMIT(TM::COMPARE opl, DOUBLE low, TM::COMPARE oph, DOUBLE high);opl: Comparison operator for the lower limit (TM::GT, TM::GE, TM::LT, TM::LE, TM::NA)low: Lower limit valueoph: Comparison operator for the upper limithigh: Upper limit value] | [含] | [含] | [无] | [通过] | [1. ate_kb_ask — 先向知识库直接提问，获取相关引用和 citations（返回了 8 条关于 SMC_TEST()、LIMIT
  类、addLimit 的引用）。
  2. ate_kb_retrieve — 尝试做更深入的语义检索（因 HuggingFace 连接问题失败）。
  3. ate_kb_get_document (120084.md) — 拉取 SMC_TEST() 的完整文档，用 grep 提取了：
    - SMC_TEST() 的重载签名（含 LIMIT 对象参数的版本）
    - LIMIT(TM::GT, low_limit, TM::LT, high_limit) 的用法示例
    - addLimit("test_limit") + GET_LIMIT_OBJECT() 的完整代码示例
  4. ate_kb_get_document (29504.md) — 拉取 LIMIT 类的完整文档，提取了：
    - 构造函数签名
    - low() / high() / unit() 成员函数
    - TEST("pin", "testname", LIMIT(...), value) 的三种示例写法
  5. ate_kb_get_document (110432.md) — 拉取 TMLimits 文档，提取了 CSV 加载方式和适用场景。
  6. 综合输出 — 将以上信息按使用场景整理成结构化的回答（LIMIT 宏 / TestMethod 注册 / TMLimits + CSV）。] |
| 2 | What is the difference between drive edge and compare edge? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 3 | How to create a new timeset? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 4 | How to enable burst pattern mode? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 5 | How to debug pattern miscompare? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 6 | What does DPS alarm 2034 mean? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 7 | How to configure voltage clamp? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 8 | How to configure PMU force current mode? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 9 | How does flow bypass work? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| 10 | How to share variables between test methods? | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |