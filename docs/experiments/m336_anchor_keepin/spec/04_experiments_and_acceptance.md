## 19. 实验矩阵

### E0 — Controlled baseline

- 新约束 flag 关闭；
- 同样的 25 anchors fixed；
- 同样的 15 unclustered fixed；
- 100 movable；
- rotation off；
- fillers off；
- 记录原 Cypress 结果。

### E1 — Hard keep-in only

- 解析异形区域；
- exact feasible domains；
- native fence region 可启用；
- 每步 hard projection；
- 无 anchor-aware 初始化；
- 无 anchor loss。

目的：衡量合法性约束本身造成的 HPWL 和收敛影响。

### E2 — E1 + anchor-aware initialization

目的：区分“初始点好”与“目标函数持续吸引”的贡献。

### E3 — E2 + anchor loss

启用：

```text
anchor_loss_weight ∈ {0.03, 0.10, 0.30}
```

先以 0.10 为主配置。

### E4 — E3 + exact repair

使用最终候选 repair，输出 E3 pre-repair 与 E4 post-repair。

### E5 — 可选

- SDF/geodesic distance field；
- cluster spread loss；
- rotation-aware feasible domain；
- orientation invalid mask。

### Seed

至少：

```text
1000
1001
1002
```

若 deterministic mode 产生完全一致输出，报告 hash 和数值证明，再允许减少重复 GPU run。

---

## 20. 指标定义

### 20.1 主要指标

每个非锚点成员：

```text
raw_anchor_distance_mm
feasible_anchor_distance_mm
```

聚合：

- weighted mean；
- mean；
- P50；
- P90；
- max；
- 按 subgroup；
- 按 side；
- 按 region。

### 20.2 紧凑度

每个 subgroup：

\[
R_g = \max_{i\in g}\|c_i-a_g\|
\]

以及：

- mean member-to-anchor distance；
- bounding-box HPWL；
- group centroid to anchor；
- shared-net star length；
- 可选 MST length。

### 20.3 合法性

- `keepin_violation_count`
- `keepin_violation_area_mm2`
- `min_keepin_margin_mm`
- `overlap_pair_count`
- `overlap_area_mm2`
- `fixed_overlap_pair_count`
- `anchor_displacement_dbu`

### 20.4 全局质量

- total HPWL；
- constrained-net HPWL；
- unconstrained-net HPWL；
- density overflow；
- max density；
- net crossing；
- runtime；
- peak GPU memory；
- projection calls/count/distance；
- repair displacement。

### 20.5 主要比较

```text
E3 vs E0：锚点目标是否有效
E1 vs E0：硬区域约束成本
E2 vs E1：初始化贡献
E3 vs E2：loss 贡献
E4 vs E3：repair 成本与合法化收益
```

---

## 21. 输出文件

每个 variant/seed：

```text
results/m336_anchor_keepin/<variant>/<seed>/
  effective_config.json
  resolved_assignment.json
  run.log
  initial.pl
  pre_repair.pl
  final.pl
  metrics.json
  components.csv
  groups.csv
  region_loads.json
  placement_before.png
  placement_after.png
  violations.png          # 有违规时必须存在
  artifacts_manifest.json
```

总报告：

```text
results/m336_anchor_keepin/REPORT.md
results/m336_anchor_keepin/summary.csv
results/m336_anchor_keepin/summary.json
```

图中必须显示：

- exact keep-in 边界；
- TOP/BOTTOM 分图；
- anchor；
- subgroup 颜色；
- member refdes；
- 违规 footprint；
- pre/post repair。

---

## 22. 测试计划

### 22.1 数据测试

- geometry SHA；
- schema；
- 140 named symbols；
- 6 empty-refdes；
- 125 clustered；
- 15 unclustered；
- 25 parsed modules；
- 100 movable non-anchor；
- 所有 refdes 可解析；
- 所有 named symbols 有 place-bound。

### 22.2 几何测试

至少构造：

- L shape；
- U shape；
- 带圆弧 shape；
- 极窄 corridor；
- 不连通 region；
- 锚点在 region 外；
- footprint 刚好可放；
- footprint 只差一个 grid 不可放。

验证：

- tessellation；
- area/bbox；
- erosion；
- nearest target；
- hard projection；
- exact containment。

### 22.3 Objective 测试

- anchor loss 梯度方向正确；
- 在 target 点梯度为零/近零；
- flag off objective 不变；
- fixed anchors 无梯度；
- mixed-side subgroup 权重和 target 正确。

### 22.4 回归测试

- `anchor_keepin_flag=false` 运行已有小 benchmark；
- 与修改前 HPWL/overflow 比较；
- 新参数缺省不破坏旧 config；
- CPU-only test 可执行。

### 22.5 M336 smoke

- 输入预处理；
- 一次短迭代 E1/E3；
- 所有数组维度和索引一致；
- 输出文件齐全；
- 无 NaN/Inf。

---

## 23. 实施里程碑

### Milestone A — Input and baseline

交付：

- input validator；
- Bookshelf generator；
- E0；
- 数据报告。

### Milestone B — Keep-in MVP

交付：

- polygon parser；
- feasible domains；
- hard projector；
- E1；
- synthetic tests。

### Milestone C — Anchor objective

交付：

- anchor-aware init；
- anchor loss；
- E2/E3；
- metrics。

### Milestone D — Repair and report

交付：

- candidate repair；
- exact final legality；
- E4；
- complete report。

### Milestone E — Optional extension

- SDF/geodesic；
- rotation；
- CP-SAT；
- filler-aware regions；
- CUDA projector if needed。

Codex 应按里程碑提交，避免一次性大改且没有可运行中间点。

---

## 24. 风险和处理

### 风险 1：25 vs 27 模块不一致

处理：以 25 行表格为实验源，持续报告 warning，不补造数据。

### 风险 2：TOP 区域负载高

当前 raw place-bound demand 约为 top_0 面积的 77.65%。腐蚀和间隙后可能不可行。必须在 Milestone A/B 做 exact capacity 检查。

### 风险 3：原始面积可行但几何不可装

处理：成员级 feasible domain 非空是硬门槛；assignment 必须可修复。

### 风险 4：硬投影导致优化器振荡

处理：

- anchor-aware init；
- loss schedule；
- 清理 projected coordinate optimizer state；
- 记录投影次数；
- 可选 SDF soft barrier。

### 风险 5：native virtual macro 扩大窄障碍

处理：M336 flag 下禁用 `clamp(min=30)`，保留旧默认。

### 风险 6：圆弧离散误差

处理：固定 chord error、面积/bbox 校验、精确输入 hash 和 sensitivity run。

### 风险 7：全局 HPWL 下降失败

处理：调节 anchor weight，比较 0.03/0.10/0.30；不要牺牲合法性换 HPWL。

### 风险 8：GPU 环境不可用

处理：完成代码、CPU tests 和输入预处理；明确列出未执行 GPU 矩阵，绝不伪造指标。

---

## 25. Definition of Done

只有满足以下全部条件才算完成：

- [ ] 代码在 `anchor_keepin_flag=false` 下无回归；
- [ ] M336 geometry 和 cluster 输入校验通过；
- [ ] 27 vs 25 discrepancy 明确记录；
- [ ] 100 movable 成员全部有 resolved subgroup/region；
- [ ] 所有活跃成员 exact feasible domain 非空；
- [ ] E0–E4 使用相同 fixed/movable set；
- [ ] E4 keep-in violation = 0；
- [ ] E4 overlap = 0；
- [ ] anchors 未移动；
- [ ] anchor-distance acceptance gate 通过；
- [ ] HPWL gate 通过；
- [ ] 结果目录和报告完整；
- [ ] 实际运行命令和测试日志可审计；
- [ ] 代码中没有 M336 refdes/坐标硬编码；
- [ ] PR 目标为 `experiment`，不修改 `main`。

---

## 26. 推荐的第一条实现原则

先实现一个清晰、可测试、纯 Python/PyTorch 的正确版本：

\[
\boxed{\text{正确几何}+\text{可复现实验}>\text{过早 CUDA 优化}}
\]

M336 只有 100 个活跃 movable，足够验证算法。完成正确性和指标闭环后，再根据 profiling 决定是否下沉 CUDA。
