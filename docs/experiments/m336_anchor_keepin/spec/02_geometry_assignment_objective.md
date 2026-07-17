## 7. 坐标系统

### 7.1 单一变换对象

新增一个集中式 `CoordinateTransform`，不得在多个文件内散落手写比例和偏移。

推荐定义：

```python
@dataclass(frozen=True)
class CoordinateTransform:
    dbu_per_mm: int
    board_origin_dbu: tuple[int, int]
    bookshelf_units_per_mm: float

    def dbu_to_mm(self, xy): ...
    def mm_to_dbu(self, xy): ...
    def dbu_to_bookshelf(self, xy): ...
    def bookshelf_to_dbu(self, xy): ...
```

### 7.2 约束

- 所有几何解析先在整数 DBU 或 double-mm 中完成；
- 只有写 Bookshelf 和送入 Cypress 时再变换；
- round-trip 误差不得超过 1 DBU；
- 位置变量的语义必须明确：
  - Cypress `pos`：左下角；
  - 本实验几何和锚点损失：器件中心；
  - 转换时必须加/减半宽、半高。

### 7.3 测试

至少覆盖：

- DBU → mm → DBU；
- DBU → Bookshelf → DBU；
- TOP/BOTTOM 相同 XY；
- 负坐标；
- 90°方向尺寸交换的预留测试。

---

## 8. Keep-in 几何解析

### 8.1 圆弧离散

`segments` 中的 arc 提供：

- `start_end`
- `center`
- `radius`
- `is_clockwise`
- `is_circle`

按方向从 start 采样到 end。推荐最大 chord error：

```text
0.01 mm
```

或：

```text
min(0.01 mm, keepin_grid_step_mm / 4)
```

要求：

- 首尾闭合；
- polygon valid；
- 面积大于 0；
- tessellated bbox 与源 `b_box` 一致；
- orientation 修正后外环为统一方向。

### 8.2 原始多边形与矩形近似双轨制

保留两种表示：

1. `exact_polygon`：用于真实包含、距离、投影生成和最终检查；
2. `nonoverlap_rectangles`：用于接入 Cypress native fence-region / virtual-macro 管线。

同一个 region 内的矩形不得重叠，因为 Cypress 原生 fence legality 通过累加器件与各矩形重叠面积判断覆盖，重叠矩形会重复计数。

### 8.3 栅格化

MVP 推荐：

```text
keepin_grid_step_mm = 0.05
```

输出：

- region occupancy mask；
- 每个尺寸类的 feasible-center mask；
- row intervals 或无重叠矩形压缩结果；
- nearest-legal lookup 或 feasible boxes。

进行 0.025 / 0.05 / 0.10 mm 敏感性测试时，只改变预处理精度，不改变其他超参数。

---

## 9. 器件 footprint

### 9.1 来源

必须使用：

```text
PACKAGE GEOMETRY/PLACE_BOUND_TOP
PACKAGE GEOMETRY/PLACE_BOUND_BOTTOM
```

不要使用 symbol 顶层 `b_box`。顶层 bbox 可能包含丝印、文字等，显著大于实际摆件边界。

### 9.2 第一阶段简化

当前实验配置保持：

```json
"enable_rotation": false
```

所以第一阶段每个器件只采用源方向下的 axis-aligned place-bound 矩形。

定义有效 footprint：

\[
P_i^{eff} = P_i \oplus C_i
\]

其中第一阶段：

```text
keepin_clearance_mm = 0.0
```

后续可做 0.05 / 0.10 mm clearance 实验。

### 9.3 合法中心域

对于 region \(K_m\)，器件合法中心域：

\[
F_{i,m} = K_m \ominus P_i^{eff}
\]

MVP 用栅格 binary erosion 构造，避免错误使用普通 isotropic negative buffer 代替矩形 Minkowski erosion。

若：

\[
F_{i,m}=\emptyset
\]

该器件不能分配到 region \(m\)。活跃 subgroup 中任何成员无合法域都必须触发 assignment repair 或失败，不能继续并等待后处理“救回来”。

---

## 10. Subgroup 到 Region 的分配

### 10.1 显式 manifest

使用：

```text
docs/experiments/m336_anchor_keepin/data/m336_assignment_seed.json
```

第一阶段优化期间不动态换区。运行前先验证或修复分配，生成最终 resolved manifest：

```text
results/m336_anchor_keepin/resolved_assignment.json
```

### 10.2 当前 seed 的生成方式

- TOP 只有 `top_0`，所以活跃 TOP subgroup 全部分配到 `top_0`；
- BOTTOM 使用 0/1 area-capacity assignment：
  - 目标：最小化“成员数 × 锚点到原始 region 距离”；
  - 原始 place-bound 面积利用率上限：0.80；
  - 只作为初始 seed。

seed 的原始面积负载约为：

| region | raw demand / raw area |
|---|---:|
| `bottom_0` | 0.523586 |
| `bottom_1` | 0.580082 |
| `bottom_2` | 0.469440 |
| `top_0` | 0.776507 |

这不是精确可行性的证明。腐蚀、形状碎片、固定障碍和器件长宽比可能使 region 实际不可用。

### 10.3 精确验证/修复

对每个 subgroup \(g\) 和候选 region \(m\)：

1. 所有成员至少有一个非空 \(F_{i,m}\)；
2. 估计可用容量；
3. 检查大器件尺寸是否可穿过窄处；
4. 计算锚点到各成员合法域的投影距离；
5. 生成 cost：

\[
C_{g,m}
=
\alpha\sum_{i\in g} w_i\,dist(a_g,F_{i,m})
+
\beta\,capacityPenalty(g,m)
+
\gamma\,fragmentationPenalty(g,m)
\]

再做 CP-SAT/MILP 分配：

\[
\sum_m z_{g,m}=1
\]

\[
\sum_g A_g z_{g,m} \le \eta A_m
\]

若 exact assignment 仍不可行，输出不可行成员、尺寸、候选区域和原因，停止 E1–E4。

### 10.4 单例模块

8 个单例模块没有非锚点成员，不参与 anchor loss，也不消耗 movable area；保留在报告中作为 control。

---

## 11. 锚点语义

### 11.1 锚点固定

所有 25 个锚点：

- 保持源 XY；
- 保持源 layer；
- 保持源 orientation；
- 不参与 optimizer；
- 不计入 movable area；
- 不被 keep-in projector 移动。

### 11.2 跨层成员

例如 anchor 在 BOTTOM，但成员在 TOP：

- TOP 成员仍使用同一物理 anchor XY；
- 其目标 \(q_i\) 是该 XY 在 TOP 分配 region 的合法中心域投影；
- 不要求 TOP 和 BOTTOM subgroup 使用同一 region ID。

### 11.3 锚点在区域外

不要求 anchor 自身位于 keep-in。目标不是把 anchor 移入区域，而是把成员尽量放到“区域中最靠近 anchor 的合法位置”。

---

## 12. Anchor-aware 初始化

对每个活跃 subgroup：

1. 按候选域大小升序处理器件；
2. 大 footprint / 少候选器件优先；
3. 从 \(q_i\) 附近搜索未占用合法中心点；
4. 使用当前 fixed cells 和已经初始化的成员维护 occupancy；
5. 若局部搜索失败，扩大半径；
6. 若全域失败，返回初始化不可行错误。

建议顺序 key：

```python
(
    feasible_site_count,
    -footprint_area,
    -anchor_weight,
    refdes,
)
```

基线 E0 也必须使用相同 fixed/movable 集合，但可以使用原 Cypress 初始化。E2 开始启用 anchor-aware 初始化。

---

## 13. 目标函数修改

### 13.1 原有项

保留 Cypress：

- weighted-average/logsumexp wirelength；
- electric density；
- net crossing；
- 可选 macro overlap。

### 13.2 新增锚点项

对每个活跃非锚点成员 \(i\)：

\[
L_{anchor}
=
\sum_i w_i\,
SmoothL1(c_i-q_i)
\]

MVP 权重：

\[
w_i=1+\#SharedNonGndNets(anchor,i)
\]

若没有直接共享 anchor net，也至少为 1，因为聚类算法已经判定其属于该模块。

可选 schedule：

```text
0%–10% iterations: 0.2 × anchor_loss_weight
10%–70%: linearly ramp to 1.0 ×
70%–100%: hold
```

目的：

- 前期允许 density 展开；
- 中期逐步吸引；
- 后期稳定局部紧凑。

### 13.3 可选组内紧凑项

MVP 默认关闭：

\[
L_{spread}
=
\sum_g\sum_{i\in g}
SmoothL1(c_i-\bar c_g)
\]

只有当 E3 仍出现成员围绕锚点松散时再启用。不要一开始同时加入多个新损失，避免无法归因。

### 13.4 总目标

\[
L =
L_{Cypress}
+
\lambda_a(t)L_{anchor}
+
\lambda_sL_{spread}
+
\lambda_kL_{keepin-soft}
\]

MVP 中 `L_keepin-soft` 可为 0，因为硬投影保证合法；后续可增加 SDF barrier 改善边界附近梯度。

### 13.5 旋转路径注意事项

当前 `PlaceObj.obj_fn()` 在 `orient_logits is not None` 时较早返回，后续 density 项不会参与 orientation-only 优化。第一阶段禁用 rotation。第二阶段启用时必须把 orientation-conditioned region penalty 放在提前返回之前，并屏蔽空可行域方向。

---

## 14. 异形区域硬投影

### 14.1 为什么必须新增

现有 `move_boundary` 只执行矩形板框 clamp：

\[
x_i\in[x_l,x_h-w_i],\quad
y_i\in[y_l,y_h-h_i]
\]

它不能保证器件位于异形 keep-in。

### 14.2 新算子

新增：

```text
dreamplace/ops/anchor_keepin/anchor_keepin.py
```

或同等清晰目录，提供：

```python
class AnchorKeepinProjector(nn.Module):
    def forward(self, pos, node_size_x, node_size_y) -> ProjectionResult:
        ...
```

`ProjectionResult` 至少包含：

- 更新后的 `pos`；
- 被投影 node mask；
- 投影距离；
- 投影前后合法状态；
- region ID。

### 14.3 MVP 表示

把每个器件的合法中心域压缩为可投影矩形集合：

```text
flat_feasible_boxes
flat_feasible_boxes_start
constrained_node_ids
```

对当前位置中心 \(p\)，投影到每个 box：

\[
\hat x_k=clamp(x,x_l^k,x_h^k)
\]

\[
\hat y_k=clamp(y,y_l^k,y_h^k)
\]

选择最短距离 box：

\[
k^*=\arg\min_k\|p-\hat p_k\|^2
\]

返回 \(\hat p_{k^*}\)，再转换为左下角。

M336 只有 100 个活跃 movable，先用 PyTorch/Python 实现。只有实际 profiling 证明它是瓶颈后才添加 CUDA。

### 14.4 调用位置

在 `NonLinearPlace.one_descent_step()`：

1. 现有矩形 `move_boundary_op` 后；
2. `optimizer.step()` 后再次调用；
3. 仅对活跃 constrained nodes；
4. 记录每步投影计数和距离。

建议：

```python
move_boundary_op(pos)
anchor_keepin_projector(pos)

optimizer.step()

projection = anchor_keepin_projector(pos)
reset_optimizer_state_for_projected_coordinates(...)
```

对 Adam/动量优化器，被硬投影的坐标应清理对应 momentum；Nesterov 也需防止历史状态持续向外推。

---
