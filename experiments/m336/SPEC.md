# M336：Cypress 锚点引导异形 Keep-in 布局实验规格

文档状态：**可执行实验规格 / Codex implementation brief**  
目标仓库：`Wellshh/Cypress`  
目标分支：`experiment`  
主实验板：`M336`  
第一阶段原则：**保持旋转关闭；先证明“同组器件在指定异形区域内且更靠近锚点”**。

---

## 1. 目标陈述

在 Cypress 现有连续全局布局框架上增加一套可开关的 PCB 约束实验能力，使 M336 中由聚类结果定义的器件组满足：

1. 每个聚类以一个物理器件为锚点；
2. 锚点位置默认冻结；
3. 同一聚类中的非锚点器件尽量靠近该锚点；
4. 每个器件必须完整落入与其 TOP/BOTTOM 面匹配的指定 `component_placeable_regions`；
5. 异形区域、窄通道、凹多边形与圆弧边界不能退化成整个板框包围盒；
6. 最终结果需要精确验证 keep-in 包含和器件间重叠；
7. 通过 E0–E4 消融实验证明锚点项与 keep-in 机制各自的效果；
8. 关闭新功能时不得改变 Cypress 原有行为。

核心问题不是“让所有器件靠板中心”，而是：

\[
\text{cluster/side subgroup}
\rightarrow
\text{assigned keepin region}
\rightarrow
\text{anchor-guided placement inside that region}
\]

主实验目标函数：

\[
L =
L_{\mathrm{Cypress\_wirelength}}
+\lambda_d L_{\mathrm{density}}
+\lambda_a L_{\mathrm{anchor}}
+\lambda_k L_{\mathrm{keepin-soft}}
+\lambda_o L_{\mathrm{macro-overlap}}
\]

同时使用 hard projection 保证每次优化更新后回到器件级可行域。

---

## 2. 输入与已知事实

### 2.1 聚类输入

输入文件：`experiments/m336/input/m336_clusters.json`

上游摘要声明：

- 总器件：140
- 聚类器件：125
- 模块数：27
- 未聚类：15

但提供的明细表实际列出 **25 个模块**，且这 25 行的成员数总和正好为 **125**。因此存在数据质量不一致：

- 不允许凭空补造两个模块；
- 首选仓库或输入目录中可找到的机器可读上游映射；
- 若找不到，则以提供的 25 行、125 个成员为本次实验清单，并把差异写入报告；
- 每个成员 refdes 必须能在几何输入和 Cypress node map 中解析；
- 聚类成员必须唯一，锚点必须包含在成员列表内。

### 2.2 几何输入

输入文件：`experiments/m336/input/pcb_geometry_keepin.json`

关键事实：

- schema：`pcb_geometry_lossless_v1`
- 坐标：integer DBU
- 单位：mm
- 比例：10000 DBU/mm
- 可摆件区域位于 `component_placeable_regions`
- `keepin_place` 在本导出中为空，不能错误读取它作为器件区域
- TOP：1 个区域
- BOTTOM：3 个区域
- 几何含 line/arc segments，精确实现不能只使用 bbox

稳定区域 ID 使用源顺序：

- `top_0`
- `bottom_0`
- `bottom_1`
- `bottom_2`

### 2.3 混合面聚类

以下聚类含 TOP 和 BOTTOM 器件：

- `page_2_J201`
- `page_3_J301`
- `page_6_J601`
- `page_7_J701`
- `page_7_J702`
- `page_86_J8601`

实现必须在优化/区域分配层把它们拆成 side-specific subgroup，例如：

```text
page_6_J601__top
page_6_J601__bottom
```

它们共享同一个物理 anchor 坐标和报告 group_id，但各自在同面区域中摆放。第一阶段禁止自动翻面。

---

## 3. 分支与代码基线

开始前必须记录：

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log -5 --oneline
```

必须在 `experiment` 分支上工作，不得覆盖该分支已有的构建与 benchmark 改动。

现有可复用入口：

- `dreamplace/PlaceDB.py`
  - 已有 `regions`
  - 已有 `flat_region_boxes`
  - 已有 `flat_region_boxes_start`
  - 已有 `node2fence_region_map`
- `dreamplace/BasicPlace.py`
  - 构造 move-boundary、legality、multi-fence legalization
- `dreamplace/PlaceObj.py`
  - 现有 wirelength、multi-electric-field density、macro-overlap objective
- `dreamplace/NonLinearPlace.py`
  - 每个 descent step 调用边界投影并执行 optimizer
- `dreamplace/ops/fence_region/`
  - 已有基于矩形并集和 virtual macros 的 region 机制
- `dreamplace/ops/legality_check/`
  - 已有 rectangle-union fence containment 检查

已知不适合窄区域的代码：

```python
virtual_macros_size_x = (...).clamp(min=30)
virtual_macros_size_y = (...).clamp(min=30)
```

该行为会人为扩大窄障碍，可能把可摆区域堵死。本实验必须删除这种几何膨胀，改成过滤零/负尺寸 box，或者使用保守但不扩大的 blocked intervals。

---

## 4. 非目标

第一阶段不要求：

- 完整工业级 PCB legalizer；
- 任意角度旋转；
- 自动换面；
- 全板所有器件都纳入聚类；
- 修改 Cypress 的核心 CUDA 电势算法；
- 用单一超参数在所有板上泛化；
- 以区域 bbox 代替异形区域；
- 为了得到“好看结果”而跳过精确合法性检查。

---

## 5. 总体架构

新增能力应 feature-gated，建议逻辑结构：

```text
M336 input loader
  ├─ cluster manifest
  ├─ geometry polygons
  ├─ Cypress node/refdes map
  └─ coordinate alignment
          ↓
side-specific subgroup builder
          ↓
region assignment + capacity preflight
          ↓
orientation-specific feasible-domain cache
          ↓
Cypress initialization
          ↓
wirelength + density + anchor loss + soft keepin
          ↓
pre-step/post-step hard projection
          ↓
optional bounded exact repair
          ↓
exact geometry validator + report
```

建议代码目录：

```text
dreamplace/constraints/
  __init__.py
  pcb_geometry.py
  anchor_keepin.py
  region_assignment.py
  region_projection.py
  region_validation.py

dreamplace/ops/anchor_keepin/
  __init__.py
  anchor_keepin.py

experiments/m336/
  SPEC.md
  configs/
  input/
  scripts/
  reports/
```

首次实验优先 Python/PyTorch 实现。M336 只有约 140 个器件，不要在没有 profile 证据前新增 CUDA kernel。

---

## 6. 坐标对齐

不得假设几何 JSON 坐标与 Bookshelf/Cypress 坐标天然一致。

实现 `GeometryAlignment`：

1. 找到同时出现在 geometry symbols 和 Cypress nodes 中的 refdes；
2. 使用至少 3 个、建议 10 个以上分散器件中心拟合仿射映射；
3. 候选模型至少覆盖：
   - translation
   - uniform scale
   - optional Y flip
4. 输出：
   - 选中的 transform
   - 配准点数
   - mean/max residual mm
5. 默认 max residual 必须不大于 0.05 mm；
6. 超限时 fail fast，禁止静默使用 board bbox 或零偏移。

持久化：

```text
results/m336/input_alignment.json
```

所有 polygon、anchor、footprint 和输出位置必须通过同一 transform。

---

## 7. 区域模型

### 7.1 两套区域表示

必须同时维护：

1. **物理区域 polygon**
   - 作为最终合法性的 source of truth
   - 精确保留 line/arc/void
2. **Cypress region boxes / raster**
   - 用于多电场 density、初始化和快速投影
   - 必须是物理区域的保守近似
   - 不得包含物理区域外空间

对于正交区域，可分解成互不重叠矩形。对于圆弧/斜边，优先使用 site-grid 保守 rasterization，再压缩为 row intervals 或 boxes。

Cypress 原生 legality checker 假设同一 region 内的 boxes 不重叠，因此预处理必须消除重叠。

### 7.2 器件级可行域

对器件 \(i\)、区域 \(K_m\)、方向 \(r\)，真正合法的是器件参考点可行域：

\[
F_{i,m,r}=K_m\ominus P^{eff}_{i,r}
\]

其中 \(P^{eff}\) 包含 footprint/courtyard 和 clearance。

第一阶段：

- rotation disabled；
- 使用当前方向；
- footprint 来源优先级：
  1. exact place-bound/courtyard（若数据中存在）
  2. symbol `b_box`
  3. Cypress `node_size_x/y`
- clearance 默认 0.0 mm，之后 sweep 0.2 mm；
- grid 默认 0.10 mm，之后验证 0.05 mm。

共享缓存 key：

```text
(side, region_id, width_sites, height_sites, orientation, clearance_class)
```

若某器件可行域为空：

- 输出 refdes、尺寸、方向、区域；
- 当前 assignment 标记 infeasible；
- `allow_region_reassignment=false` 时 fail；
- 不得偷偷放到其他区域或整个板框。

---

## 8. 聚类与区域分配

### 8.1 锚点政策

默认：

- 锚点保持输入物理位置；
- 锚点若在 Cypress 中是 movable，实验模式下将其冻结；
- 锚点本身不计入 anchor loss；
- 锚点可以位于 keepin 外；
- 非锚点器件的目标点是“物理锚点在该器件可行域上的最近投影”。

对器件 \(i\)：

\[
q_i=\Pi_{F_{i,m,r}}(a_G)
\]

### 8.2 区域 assignment

包内提供 `m336_region_assignment.seed.json`，它按：

1. cluster 拆分为 side subgroup；
2. 选择同面的 region；
3. 最小化物理 anchor 点到 region polygon 的距离；

生成一个**提议**。

该 seed 不是 ground truth。实现必须做：

- 每个成员可行域非空检查；
- group 总面积/候选数量检查；
- fixed obstacle 检查；
- region 过载诊断；
- 生成 reviewable final assignment。

若仓库中已有人工 region mapping，则它优先于 seed。

第一阶段不做运行时离散换区；assignment 在优化开始前固定。后续可以将 group-to-region assignment 建模成 CP-SAT/min-cost-flow，但不属于首个可行性实验的必需项。

---

## 9. 初始化

Cypress 默认中心随机初始化不适合窄异形区域。

对约束器件进行 region-aware initialization：

1. 固定 anchor 和 fixed obstacles；
2. 每个 subgroup 从 projected anchor 向外枚举可行 sites；
3. 排序优先级：
   - 候选 sites 最少
   - footprint 最大
   - anchor 权重最高
4. 选择不与已占用矩形冲突且代价最小的位置；
5. 初始代价：
   - anchor distance
   - 与原始位置的位移
   - 局部 HPWL 增量
6. 若贪心失败，保留诊断并进入 bounded backtracking/repair；
7. 禁止把器件先放在区域外再期待 density 自动修复。

---

## 10. Anchor loss

对所有约束、可移动、非锚点器件：

\[
L_{\text{anchor}}
=
\frac{1}{N}
\sum_i w_i\,
\operatorname{SmoothL1}
\left(
\frac{\|c_i-q_i\|_2}{D_{\text{board}}}
\right)
\]

其中：

- \(c_i\)：器件中心
- \(q_i\)：该器件 feasible domain 中最靠近物理锚点的点
- \(D_{\text{board}}\)：板框对角线，用于尺度归一化
- \(w_i\)：可选的重要性权重，默认 1

不要实现所有成员两两距离的 \(O(n^2)\) loss。现有 net HPWL + anchor star loss 已能产生聚拢作用。

权重初始化建议使用梯度范数匹配：

\[
\lambda_a =
s_a
\frac{\|\nabla L_{\mathrm{WL}}\|_1}
     {\|\nabla L_{\mathrm{anchor}}\|_1+\epsilon}
\]

其中 `anchor_weight_scale` sweep：

```text
0.25, 0.5, 1.0, 2.0
```

必须在日志中记录实际 \(\lambda_a\) 和各项 loss/gradient norm。

在 `PlaceObj.obj_fn()` 中加入 anchor loss。注意当前 orientation-only 路径会在 density 前提前返回；第一阶段 rotation disabled，因此不修改方向优化行为。第二阶段再加入 orientation-conditioned feasible-domain loss。

---

## 11. Soft keep-in loss

为减少“optimizer 推出区域—hard projector 拉回”的震荡，加入：

\[
L_{\text{keepin-soft}}
=
\frac{1}{N}
\sum_i
\operatorname{softplus}
\left(
\frac{d^{out}_i}{\tau}
\right)^2
\]

其中 \(d^{out}_i\) 是器件 anchor 点到其 feasible domain 的外部距离，域内为 0。

推荐实现：

- 预计算 occupancy/SDF；
- 用 `torch.nn.functional.grid_sample` 双线性采样；
- 只对约束 movable nodes 计算；
- 权重也使用梯度范数或明确 sweep；
- hard projection 仍是最终保证，soft loss 不是合法性证明。

---

## 12. Hard projection

新增 `move_region_boundary_op`：

\[
p_i \leftarrow \Pi_{F_i}(p_i)
\]

要求：

- 只修改违反可行域的约束器件；
- 通过预计算 nearest-valid lookup 做 O(1) 或近似 O(1) 查询；
- `torch.no_grad()` 下原地更新；
- 在 objective 前执行；
- 在 `optimizer.step()` 后再次执行；
- 记录每轮 projected node count 和最大投影距离；
- 对被投影坐标，在支持的 optimizer 中清零对应动量/state，避免持续撞墙；
- feature flag off 时不执行。

`NonLinearPlace.py` 的集成点：

```text
existing move_boundary_op
→ move_region_boundary_op
→ metric/objective/gradient
→ optimizer.step
→ move_region_boundary_op
```

---

## 13. Fillers 与窄区域

第一阶段：

- 约束窄区内禁用 fillers；
- non-fence 区可保持原逻辑；
- 不允许 `virtual_macro.clamp(min=30)`；
- 对零/负尺寸 virtual macro 过滤；
- region density grid 应满足：

\[
\min(bin_x,bin_y) \le W_{\min}/3
\]

但不需要为了一个窄区把全板 grid 无限增大；局部 feasible mask 和 projector 承担精确性。

---

## 14. Legalization 与 exact repair

Cypress density 不保证最终零重叠，原生 row-based legalizer也不适合所有 PCB 异形窄区。

第一阶段建议：

1. Global placement + hard projection；
2. exact validator；
3. 仅对违反 keepin/overlap 的约束器件运行 bounded repair；
4. repair 候选来自 feasible-domain grid；
5. fixed obstacles 和已接受器件先占用；
6. cost：
   - anchor distance
   - Cypress displacement
   - incremental HPWL
7. 优先 greedy + limited backtracking；
8. 若仓库已有 OR-Tools，则可加 CP-SAT；不要为了首个实验强制新增大型生产依赖；
9. E4 必须输出修复前后指标。

CP-SAT 形式：

\[
z_{i,c}\in\{0,1\},\quad \sum_c z_{i,c}=1
\]

冲突候选：

\[
z_{i,c}+z_{j,d}\le1
\]

目标：

\[
\min\sum_{i,c}z_{i,c}
\left[
\alpha D_{\mathrm{anchor}}(c)
+\beta\|p_c-p_i^{GP}\|_1
+\gamma\Delta HPWL(c)
\right]
\]

---

## 15. 精确验证器

最终 source-of-truth validator 必须使用物理 polygon 与实际 footprint，而不是只用 Cypress region boxes。

输出：

- constrained component count
- full-containment count
- keepin violation count
- violation area mm²
- overlap pair count
- overlap area mm²
- 每个违规 refdes、group、side、region、位置和面积
- 每个 group 的 anchor distance
- 坐标 transform residual

包含判断：

\[
\operatorname{Area}(P_i\setminus K_m)\le\epsilon
\]

重叠判断至少覆盖：

- constrained vs constrained
- constrained vs fixed
- 同一面的器件
- TOP/BOTTOM 根据设计规则分别检查

E3/E4 的成功定义不能只依赖 Cypress 自带 `legality_check`。

---

## 16. 参数与向后兼容

在 `dreamplace/params.json` 增加可选参数，默认全部关闭：

```json
{
  "anchor_keepin_config": "",
  "anchor_keepin_flag": false,
  "anchor_loss_flag": false,
  "anchor_loss_weight_scale": 1.0,
  "keepin_soft_loss_flag": false,
  "keepin_soft_loss_weight_scale": 1.0,
  "keepin_projection_flag": false,
  "constraint_grid_mm": 0.1,
  "keepin_clearance_mm": 0.0,
  "freeze_anchor_nodes": true,
  "allow_region_reassignment": false
}
```

要求：

- 无配置文件或 flag=false 时，原有 benchmarks 行为一致；
- 不把 M336 路径硬编码到核心类；
- 所有 M336 特定内容放在 `experiments/m336/`；
- 不使用绝对路径；
- 不提交大规模生成日志、图片序列或模型缓存。

---

## 17. 实验矩阵

### E0：Cypress baseline

- 无 anchor loss
- 无 region constraints
- 评估但不强制 keepin
- 用于总线长和运行时参考

### E1：Anchor only

- 有 anchor loss
- 无 keepin enforcement
- 仅诊断 anchor loss 是否有效
- 不作为合法结果

### E2：Keepin only

- region density
- hard projection
- anchor loss off
- 作为主要可行性 baseline

### E3：Anchor + Keepin

- region density
- anchor loss
- soft keepin
- hard projection
- 主实验

### E4：Anchor + Keepin + exact repair

- E3
- bounded repair/legalization
- 最终可交付结果

每个实验至少运行 seeds：

```text
1000, 1001, 1002
```

权重 sweep：

```text
anchor_weight_scale = 0.25, 0.5, 1.0, 2.0
```

首轮可先用 1.0 做 smoke，再跑完整矩阵。

---

## 18. 指标

### 18.1 Hard legality

- `keepin_violation_count`
- `keepin_violation_area_mm2`
- `fully_contained_components / constrained_components`
- `overlap_pair_count`
- `overlap_area_mm2`
- infeasible-domain count
- projected-nodes per iteration

### 18.2 Anchor metrics

对所有约束、可移动、非锚点成员：

- mean
- median
- p90
- max
- 每 group/subgroup mean/max
- group radius
- 到 physical anchor 和 projected anchor 两套距离（报告中明确区分）

### 18.3 Electrical/placement

- total HPWL
- clustered nets/groups HPWL
- net crossing（若启用）
- density overflow
- runtime
- iterations
- convergence reason

### 18.4 主要统计比较

Primary：

```text
E3 vs E2
```

因为两者都执行 keepin，差别主要是 anchor attraction。

Secondary：

```text
E4 vs E0
E3 vs E0
```

---

## 19. 成功标准

### 必须满足

- E4：约束 movable 器件 100% 完整位于 assigned keepin；
- E4：约束器件与 fixed/其他约束器件零重叠；
- 所有输入 refdes 完成解析或在报告中明确排除；
- feature flag off 的 existing small benchmark smoke test 不回归；
- 无 silent board-bbox fallback；
- 结果 JSON 含 git SHA、config、seed、输入哈希；
- 不能伪造未实际运行的 GPU/build 实验。

### 目标值

相对 E2：

- E3/E4 mean anchor distance 降低 ≥ 25%
- p90 anchor distance 降低 ≥ 15%

相对 E0：

- HPWL 回退 ≤ 10%，理想 ≤ 5%
- runtime ≤ 2× baseline，若超过需 profile 解释

若目标未达到，不视为代码失败；必须给出权重 sweep、容量瓶颈和 per-group 诊断。

---

## 20. 测试要求

新增纯 Python/CPU 单元测试，GPU 不可用时也能运行：

1. `test_cluster_manifest_integrity`
2. `test_geometry_dbu_to_mm`
3. `test_geometry_alignment`
4. `test_arc_polygon_reconstruction`
5. `test_region_decomposition_is_conservative`
6. `test_region_boxes_are_non_overlapping`
7. `test_component_feasible_domain`
8. `test_projected_anchor_target`
9. `test_hard_projector_inside_domain`
10. `test_exact_validator_detects_violation`
11. `test_anchor_loss_zero_at_target`
12. `test_anchor_loss_gradient_direction`
13. `test_feature_flag_off_is_noop`

集成 smoke：

- M336 input preparation
- E0 short run
- E3 short run
- existing small-6 or repository-equivalent smoke

测试命令必须写入报告。不能运行的命令要记录原因、环境和替代验证。

---

## 21. 产出物

代码：

- feature-gated constraints loader
- geometry alignment
- region assignment/preflight
- feasible-domain cache
- anchor loss
- hard projector
- exact validator
- optional bounded repair

实验：

```text
results/m336/<run_id>/
  config.resolved.json
  metrics.json
  legality.json
  per_group.csv
  placement.pl
  placement.png
  input_alignment.json
  run.log
```

汇总：

```text
results/m336/summary.json
results/m336/REPORT.md
```

报告必须包括：

- 实际 git SHA
- 分支
- 构建环境
- 所有运行命令
- E0–E4 对比表
- per-group 最差案例
- 未解决问题
- 建议下一步

---

## 22. 实施阶段

### Phase A：输入与基线

- 仓库巡检
- 找 M336 现有 aux/Bookshelf 数据
- 若不存在，基于 geometry JSON 生成最小 Bookshelf benchmark
- 校验 25/27 模块差异
- 坐标对齐
- E0 smoke

### Phase B：Keepin 基础

- region parsing
- side subgroup
- assignment preflight
- feasible-domain cache
- hard projection
- E2 smoke
- exact containment report

### Phase C：Anchor objective

- anchor target
- anchor loss
- gradient normalization
- E3 smoke
- weight sweep

### Phase D：Repair 与完整实验

- bounded repair
- E4
- 3 seeds
- existing benchmark regression
- REPORT.md

建议在每个 phase 结束时创建小而可审阅的 commit；不经用户要求不要 push。

---

## 23. Codex 完成时必须返回

1. 修改文件摘要；
2. 关键设计决策；
3. 运行过的命令；
4. 测试结果；
5. M336 实验结果；
6. 未运行/失败项及原因；
7. 与成功标准的逐项对照；
8. `git diff --stat`；
9. 建议人工重点 review 的代码位置。

不得仅回答“已实现”，不得用估计值冒充实际实验数据。
