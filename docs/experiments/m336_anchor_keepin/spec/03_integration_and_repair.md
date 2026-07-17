## 15. Cypress Native Fence-region 的复用

### 15.1 复用点

`PlaceDB.py` 已有：

- `regions`
- `flat_region_boxes`
- `flat_region_boxes_start`
- `node2fence_region_map`

`PlaceObj.py` 已有 multi-electric-field 路径；`BasicPlace.py` 已有 multi-fence legalization。

应尽量复用这些结构，用 non-overlap rectangle decomposition 注入 raw keep-in，获得区域级 density 场。

### 15.2 不把 native fence 当作最终几何判定

native fence legality 适合 axis-aligned box union。最终 E4 仍必须回到：

```text
exact keep-in polygon
+ transformed place-bound footprint
```

做精确包含检查。

### 15.3 窄区风险：virtual macro clamp

当前 multi-fence legalization 中存在：

```python
virtual_macros_size_x = (...).clamp(min=30)
virtual_macros_size_y = (...).clamp(min=30)
```

这可能把薄障碍扩大并堵塞窄区域。新增配置：

```text
anchor_keepin_preserve_virtual_macro_geometry = true
```

在该模式下：

- 不做 `min=30`；
- 删除近零面积 box；
- 记录所有 virtual macro 原始尺寸；
- 添加窄通道单元测试。

默认旧 benchmark 保留旧行为，避免无关回归。

### 15.4 Filler 策略

第一阶段：

```json
"enable_fillers": 0
```

原因：

- region 面积小且异形；
- 现有 filler 基于矩形面积和平均宽度；
- 小子区域可能小于 filler；
- filler 会掩盖锚点损失效果。

后续单独做 E6 filler 实验，使用 region-aware site filler。

---

## 16. 精确后修复

连续优化结束后，对每个 region/side 独立处理。

### 16.1 候选生成

对器件 \(i\)：

- 从其 feasible-center mask 取候选；
- 优先靠近 Cypress 结果和 \(q_i\)；
- 对每个器件保留 top-K 候选，例如 50–200；
- 候选必须精确包含于 keep-in。

候选 cost：

\[
cost(i,c)
=
\alpha\|c-p_i^{GP}\|_1
+
\beta\|c-q_i\|_1
+
\gamma\Delta HPWL(i,c)
\]

### 16.2 MVP repair

先实现 deterministic greedy candidate repair：

1. 候选数少/面积大者优先；
2. 选择最低 cost 且不冲突候选；
3. 冲突时局部 rip-up/reinsert；
4. 输出失败原因。

### 16.3 E4 exact repair

若 OR-Tools 可用，加入 CP-SAT：

\[
z_{i,c}\in\{0,1\}
\]

\[
\sum_c z_{i,c}=1
\]

冲突候选：

\[
z_{i,c}+z_{j,d}\le1
\]

目标为候选 cost 总和。若依赖不可用，保留 greedy，并在报告中明确说明没有运行 CP-SAT，不得假装 exact solver 已执行。

---

## 17. 需要修改的代码

### 17.1 新增模块

建议：

```text
dreamplace/pcb_constraints/
  __init__.py
  geometry.py
  transform.py
  clusters.py
  assignment.py
  feasible_domain.py
  metrics.py

dreamplace/ops/anchor_keepin/
  __init__.py
  anchor_keepin.py

scripts/m336/
  prepare_m336.py
  run_m336_experiment.py
  analyze_m336_results.py

unittest/ops/anchor_keepin_unittest.py
unittest/pcb_constraints/
  test_geometry.py
  test_assignment.py
  test_feasible_domain.py
  test_transform.py
```

### 17.2 `dreamplace/params.json` / `Params.py`

新增参数并给出默认值，所有默认关闭：

```text
anchor_keepin_flag = false
pcb_geometry_input = ""
anchor_cluster_input = ""
anchor_keepin_assignment_input = ""
anchor_components_fixed = true
unclustered_components_fixed = true
keepin_region_source = "component_placeable_regions"
keepin_grid_step_mm = 0.05
keepin_arc_chord_error_mm = 0.01
keepin_clearance_mm = 0.0
keepin_region_utilization_limit = 0.80
keepin_projection_flag = true
keepin_projection_frequency = 1
keepin_project_after_optimizer_step = true
anchor_init_flag = true
anchor_loss_flag = true
anchor_loss_metric = "smooth_l1_to_projected_anchor"
anchor_loss_weight = 0.10
anchor_member_weight_mode = "shared_signal_net_count_plus_one"
keepin_exact_repair_flag = true
keepin_exact_repair_engine = "greedy_candidate_repair"
keepin_metrics_flag = true
```

### 17.3 `dreamplace/PlaceDB.py`

新增职责：

- 加载几何和 cluster manifest；
- 验证 SHA、schema、refdes；
- 构造 fixed/movable policy；
- 生成 side subgroup；
- 注入 region arrays；
- 生成 active node arrays；
- 保存 coordinate transform；
- 计算 place-bound 尺寸；
- 生成 resolved assignment；
- 计算 target density 时使用真实 region 容量诊断。

不要把 M336 路径写死在核心代码中。

### 17.4 `dreamplace/BasicPlace.py`

新增 data collections：

```text
anchor_node_ids
anchor_target_x/y
anchor_member_weights
active_constrained_node_ids
node_region_ids
flat_feasible_boxes
flat_feasible_boxes_start
```

新增 op：

```text
anchor_keepin_projector
anchor_loss_op
anchor_keepin_metrics_op
```

### 17.5 `dreamplace/PlaceObj.py`

在 `obj_fn()` 中加入 anchor loss，并将当前值放入 model state，供 `EvalMetrics` 读取。

当 flag 关闭时不得改变 objective。

### 17.6 `dreamplace/NonLinearPlace.py`

- 每步投影；
- optimizer state 处理；
- 记录 projection metrics；
- 运行结束后调用 repair；
- 保存 pre-repair 和 post-repair 两套结果。

### 17.7 `dreamplace/EvalMetrics.py`

新增：

```text
anchor_distance_raw_mean
anchor_distance_feasible_mean
anchor_distance_feasible_p50
anchor_distance_feasible_p90
anchor_distance_feasible_max
cluster_radius_mean
cluster_radius_p90
keepin_violation_count
keepin_violation_area_mm2
projection_count
projection_distance_mm
region_utilization
```

### 17.8 `dreamplace/Placer.py`

- 输出 resolved assignment；
- 写有效 config；
- 调用 M336 report writer；
- 不改变非 M336 正常流程。

---

## 18. M336 Bookshelf 准备

仓库当前没有检索到 M336 benchmark，不能用 small-6 替代。

若运行环境没有现成 M336 `.aux`，`prepare_m336.py` 必须从几何 JSON 生成：

- `.nodes`：140 named symbols，但 fixed/movable 按实验 policy；
- `.nets`：使用 symbol pins/net；
- `.pl`：源 XY、layer、orientation；
- `.scl`：板 bounding rectangle；
- `.aux`。

真实可摆区不依赖 `.scl` 表达，而由 anchor-keepin 约束模块处理。

### 18.1 `.nodes`

尺寸来自 place-bound，不来自 symbol bbox。

### 18.2 `.pl`

- anchor 和未聚类写 `/FIXED`；
- TOP/BOTTOM orientation 保持；
- 所有 E0–E4 使用同一初始文件和 fixed set。

### 18.3 网络过滤

保留原网表，指标和 anchor weight 可排除：

- empty net；
- GND；
- 可配置高扇出 power/global net。

不要从主 placement netlist 中随意删除网络；只在权重和诊断层过滤。

---
