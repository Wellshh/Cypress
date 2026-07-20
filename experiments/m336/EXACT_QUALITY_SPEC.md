# M336 0.05 mm 精确质量优化规格

文档状态：**Active phase specification**  
证据范围：`M336-105` 至 `M336-133`

上位合同：[`SPEC.md`](SPEC.md)

本文只规定当前 exact-site 质量优化阶段。原始 `SPEC.md` 仍是几何、
keep-in、锚点、E0-E4 与默认关闭行为的验收合同；本文不得削弱其中任一
合法性要求。

## 评估结论

提案的主方向被采纳：冻结 M336-118、显式排除 incumbent、拆分 topology
generation 与 HPWL closure、按 residual net 生成 guide、按物理闭包扩张
support，并在 page-7 改善后顺序重跑后续 closure。执行时必须应用以下修正：

- 提案快照止于 M336-122；当前证据已推进到 M336-128。
- guide-rank 是稳定的拓扑成本，不是多样性约束；M336-128 已证明无 HPWL
  上限时它仍返回 seed 3001。
- M336-050 和旧 Q601/two-anchor 证明只能约束各自声明的有限域，不能外推为
  当前 EMI601-only policy 的不可行证明。
- issue ledger 保持 append-only；轨道与 supersession 由
  `docs/issues/ACTIVE_ROADMAP.md` 表达，不批量重写历史状态。
- Hamming/no-good 必须使用独立、精确映射且可重放的 site reference，不能从
  candidate guide 或 solver hint 隐式推断。

## 1. 冻结实验合同

| 项目 | 固定值 |
| --- | --- |
| Source/checkpoint | `experiments/m336/checkpoints/M336-118/` |
| Assignment | checkpoint 内的固定 assignment |
| Endpoint policy | manual `EMI601`，runtime `Q601` |
| Grid | `0.05 mm` |
| Collision | exact `BOTH` sides |
| Rotation | disabled |
| Anchors | frozen，包括 `MIC401` |
| Scoring incumbent | HPWL `15634.450477332834`，integer `15634450483` |
| Necessary score-1 limit | HPWL `<= 15260.369571786632` |

人工 baseline 的 native HPWL/RSMT 分别为 `14627.84765625` 和
`15950.0654296875`。它仅作为 score `1.0` 的评分基准，不是合法 placement
模板。当前 incumbent 的必要 HPWL 差距是 `374.080905546202`，仅由 HPWL
得到的 normalized score upper bound 是 `0.9760732936479889`。

除非建立独立、命名明确的新实验，不得恢复 Q601 manual endpoint，也不得
重新启用 two-anchor 合同。

## 2. 当前证据边界

- `M336-105` 证明当前 endpoint policy 可在 `0.05 mm` 网格上逐字节回放。
- `M336-106` 至 `M336-118` 把精确合法 HPWL 从 `15811.065584` 降到当前值。
- `M336-119` 将 incumbent 导出为不可覆盖、可移植 checkpoint。
- `M336-120/122/125` 的有限域 lower bound 低于 score-1 阈值，但只返回
  incumbent；这些结果是 **search-open**，不是 infeasibility proof。
- `M336-121` 的三个合法 escape family 只移动
  `C703,FV707,R707,R708`，普通 HPWL closure 会全部回退。
- `M336-124/125` 将 page-7 的完整一跳可移动 blocker 闭包扩为
  `B402,L401`；`MIC401` 是不可释放物理锚点。
- `M336-126/127` 的单步 escape 与 `+20/+50/+100/+200` rank envelope
  仍只复现已有 family。
- `M336-128` 去除 HPWL 模型后，四次全局 rank solve 均 `OPTIMAL` 于 rank
  `72`，并逐字节复现 seed 3001。guide rank 本身不能强制拓扑多样性。
- `M336-129` 用显式 exclusion 在 M336-122 域中生成并认证了不同于 incumbent
  的 `C703/FV707` swap plateau；其 HPWL 与 M336-118 相同，但独立 closure
  尚未产生严格改善。
- `M336-130` 生成六组 residual-directed exact-legal family，并在 `Delta=20`
  内认证首个 d6 topology。该 topology 经 one-opt 与三轮 exact pair closure
  回到 M336-129 swap plateau，未形成评分提升；`C404/FV704/FV705/FV708` 是
  实测所需 closure partner，说明 page-7 18-component support 不完整。
- `M336-131` 将 M336-130 d6 certificate 作为同一 M336-122 域的精确可行
  hint，使原先 `UNKNOWN` 的 d6/Delta20 模型在 14.332 DT 内证明 rank 11
  `OPTIMAL`。该解的独立 closure 仍回到 M336-129 swap plateau；下一步必须对
  rank-11 tuple 加 no-good，而不是重复 infeasible-hint seed ladder。
- `M336-132` 修复 exact-site result 对相对环境路径的歧义序列化；source、
  guide、hint、assignment、diversity/no-good 与输出依赖在 I/O 前统一规范为
  绝对路径，`/tmp` 结果可在无 exporter override 时直接生成 portable artifact。
- `M336-133` 对首个 rank-11 d6 tuple 加 exact no-good 后，再次于 rank 11
  `OPTIMAL`，说明该层存在退化多解。两个不同 d6 topology 经 one-opt 后 placement
  SHA 完全一致，随后均回到 M336-129 swap plateau；尚不能视为 rank-11 层穷尽。

当前六个主要乐观 residual 均集中在 page 7：

| Net | Residual HPWL | 受控端点 |
| --- | ---: | --- |
| `VSIM2` | 105.487757 | `C703,FV707,R707` |
| `SIM_DET1` | 92.990012 | `FV705,R703` |
| `PSIM2_DATA2` | 86.990657 | `FV710,R708` |
| `NFC_SWP` | 78.716197 | `FV706` |
| `PSIM2_SRST2` | 76.672372 | `FV708,R709` |
| `PSIM2_SCLK2` | 73.992053 | `FV709,R710` |

`514.849048` 的总 residual 只是定位信号；网络改善不可直接相加。

## 3. Incumbent Exclusion 合同

`probe_exact_site_cpsat.py` 必须增加与 source、candidate guide 和 solver hint
相互独立的多样性输入：

```text
M336_DIVERSITY_REFERENCE_JSON=<exact result or placement>
M336_MIN_CHANGED_SITES=<d>
M336_EXCLUDED_SITE_JSONS=<result1,result2,...>
```

对 reference 中每个声明为 movable 且候选域大于一的器件，必须找到唯一的
精确候选 site；不得静默投影到最近候选。设 site 变量为 `s_i`、reference
site 为 `s_i_ref`，模型必须建立双向等价：

\[
c_i \Leftrightarrow s_i \ne s_i^{ref},\qquad \sum_i c_i \ge d
\]

固定域不得计入 changed count。每个 excluded placement 必须映射为同一作用域
上的完整 site tuple，并以 exact forbidden assignment 实现：

\[
(s_1,\ldots,s_n) \ne (t_1,\ldots,t_n)
\]

缺失 refdes、非唯一 site、超出 movable support 的差异或无法区分的 no-good
都必须在建模前 fail closed。结果必须记录 reference 路径与 SHA-256、requested
和 actual changed count/refdes、canonical reference tuple、no-good SHA-256 与
逐项 replay。solver hint 不得隐式充当 diversity reference。

## 4. 两阶段求解

### 4.1 Solve A：生成合法拓扑

先复用 `M336-122` 的 18-component K4096 域以隔离 exclusion 的效果；再复用
`M336-125` 的 20-component 域验证 `B402/L401` blocker 闭包。共同条件为固定
assignment、exact BOTH collisions、one worker、M336-118 source，以及稳定
guide-rank objective。

按 `d = 2,4,6,8` 与下列 HPWL rise envelope 递增：

| Delta | Integer ceiling |
| ---: | ---: |
| 0 | 15634450483 |
| 1 | 15635450483 |
| 2 | 15636450483 |
| 5 | 15639450483 |
| 10 | 15644450483 |
| 20 | 15654450483 |

每找到一个 exact-legal topology，立即加入完整 no-good，再枚举下一解。保存
topology 不要求其优于 incumbent；它是独立 closure 的非评分 guide。
`INFEASIBLE` 只证明该 support/candidate/d/Delta 组合无解；`UNKNOWN` 或预算
耗尽不得表述为不可行。

### 4.2 Solve B：独立 HPWL Closure

每个 Solve A topology 仅作为独立 hint。移除 Hamming、no-good、guide-rank
objective 和过紧 rank ceiling，恢复全局 HPWL objective，并保留 M336-118 的
integer hard ceiling。只有同时满足下列条件才可 promotion：

- integer objective 严格小于 `15634450483`；
- floating selected-site/per-net replay 严格小于 `15634.450477332834`；
- 精确合法性与 all-fixed K1 certification 全部通过。

closure 回到 M336-118 是有效负结果，不得把 Solve A 的上升态写入 incumbent
链。

## 5. Residual-Net Guides 与候选预算

为六个 residual net 分别构建 bounded-rise、exact-legal guide。每个 guide 只
优化目标 net span，同时释放其列出的端点及 exact physical collision closure；
随后才组合多个 guide。不得再从单个全局 collision-relaxed placement 直接抽取
一个四器件 escape 作为 page-7 的完整代表。

`M336-130` 的首轮 portfolio 是此步骤的部分证据，不是完成标志。它已为六个
net 生成独立 coordinate target，并认证了对应合法 topology，但 target 仍来自
collision-relaxed page-7 quality guide，且 `R703/FV710/R709/R710` 尚未发生
target-directed 位移。下一轮必须直接优化各 residual net span，并补齐这些端点
及实测 blocker `C404/FV704/FV705/FV708` 的候选覆盖。

候选报告必须增加：

- 每个 guide 实际贡献的 unique sites；
- 新旧 candidate set 的 Jaccard；
- per-component guide coverage；
- per-net endpoint coverage；
- candidate set 到目标坐标的最小距离。

高 residual endpoint/blocker 可用 full-site 或 K8192，次要 page-7 member 用
K2048/K4096，低相关 member 用 K512/K1024。只有 coverage 报告证明新增了不同
site，才允许增加求解预算。

## 6. Support 扩张与顺序组合

movable support 只能按证据扩张：page-7 18 components，随后
`B402/L401`，再到 direct collision blockers、residual-net adjacent components、
page-6/page-86 physical neighbors，最后才是完整 affected region。`MIC401`
保持冻结。

每层记录 candidate count、rigorous lower bound、incumbent 与 score threshold。
bound 高于阈值只证明该有限域不足；bound 低于阈值但没有新 incumbent 表示
搜索尚未闭合。`M336-050` 等旧 restricted-domain 结论也必须按其原始 domain
解释，不能外推到当前域。

取得 page-7 严格改善后，从新 certificate 依次重跑：

```text
page-7 -> page-86 U8601 -> page-4 -> full one-opt -> blocker-aware pair closure
```

禁止直接拼接不同 portfolio 的 placement 文件。

## 7. Promotion 与最终评分

每个正式 incumbent 必须通过 selected-site HPWL、per-net replay、objective
replay、candidate collision equivalence、100/100 containment、零 keep-in、零
overlap、one-worker all-fixed K1 replay，并导出新的不可覆盖 portable checkpoint。
placement SHA-256 必须在 certificate、checkpoint 和重放间一致。

每个关键证据或严格改善都使用 signed commit 推送当前 `experiment` 分支；下一
节点先 `git pull --rebase personal experiment`。临时目录不得成为唯一证据源。

只有 HPWL `<= 15260.369571786632` 后才运行最终 native gate：native HPWL、
FLUTE RSMT、serialized `.pl` 精确合法性、零坐标漂移、normalized score
`>= 1.0`，并以相同 placement hash 第二次重放。

## 8. 暂停项与停止规则

停止继续测试相同 K4096 域上的 seed ladder、current/quality weight ladder 或
单纯增加 deterministic time。Cypress 的 soft-margin barrier、warm-start 成本与
E3/E4 runtime/anchor-distance 属于 production-integration track；在取得
score-1 exact-site reference 前不抢占本阶段主线，也不得被误报为已解决。

恢复 production track 时，应把当前投影后为零梯度的 outside-only penalty
替换为内部 margin barrier 候选：

\[
L_{margin}=\operatorname{softplus}\left(\frac{m-d_{inside}}{\tau}\right)^2
\]

该公式仍需独立实现、梯度测试和 E0-E4 验证，不是本文阶段的已验收功能。
