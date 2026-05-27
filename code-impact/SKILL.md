# 代码影响面调用链分析

在影响面分析阶段，根据代码 diff 自动追踪变更文件向上到入口层（Controller/Handler/Tool）和向下到数据层（DAO/Repository/Service）的完整调用链，生成结构化影响面报告。

## 适用场景

- PR 代码审查的影响面评估
- 后端自动化项目的变更影响分析
- 多语言微服务架构的依赖传导追踪

## 支持语言

Go (.go) · PHP (.php) · Java (.java) · TypeScript/JavaScript (.ts/.tsx/.js/.jsx)

## 使用方式

### 第一步：运行调用链分析脚本

从 git diff 获取变更文件列表，管道传入分析脚本：

```bash
git diff main --name-only | bash code-impact/impact-chain.sh
```

参数：
- `--depth 3` — 传导深度（默认 2）
- `--lang go` — 强制指定语言（默认自动检测）

### 第二步：分析输出

脚本输出 markdown 格式的影响面报告，按变更文件逐个展示：

```markdown
### `internal/service/order.go`

**📡 向上 → 入口层:**
  - `internal/api/order_handler.go`
  - `internal/grpc/order_server.go`

**🗄️ 向下 → 数据 / 服务层:**
  - `repo.OrderRepo`
  - `store.Transaction`
```

### 第三步：模型语义分析

将脚本输出交给模型，由模型判断：
- 哪些入口文件确实需要修改（不是所有匹配的文件都真的受影响）
- 数据层变更是否需要迁移或兼容处理
- 给定具体的修改建议

## 工作原理

```
变更文件 → 提取导出符号（按语言解析 AST 特征）
        → git grep 全仓库反查调用者 → 筛出入口层文件（向上）
        → 解析 import/use 语句 → 提取数据层依赖（向下）
```

全程使用 `git grep`（直读 `.git/objects`，不走磁盘），无需建立缓存索引，每次分析都在秒级完成。
