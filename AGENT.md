# AGENT.md

## 项目定位

这是一个用于结构化工作量评估的 CLI harness 项目，不是通用聊天机器人。

系统目标：

- 将原始需求文本转换为结构化模块
- 为模块分配参与岗位
- 调用对应岗位 agent 进行工时评估
- 合并输出 Excel、Markdown 报告和 session 记录

## 核心目录索引

### 根目录

- `main.py`
  CLI 入口。
- `harness.py`
  主编排流程，负责 agent 调用链、澄清循环、合并与导出。
- `config.toml`
  实际运行配置。
- `config.example.toml`
  配置模板。
- `pyproject.toml`
  项目依赖和安装配置。
- `README.md`
  使用说明。
- `AGENT.md`
  本文件，作为仓库级 agent 索引和公共约束说明。

### agents/

每个 agent 一个独立 prompt 文件，文件名即 agent 标识。

- `presale_agent.md`
  负责需求拆解、模块树构建、岗位分配、澄清问题生成。
- `dispatcher_agent.md`
  负责决定本轮需要激活哪些岗位 agent。
- `product_agent.md`
  产品岗位工时评估。
- `backend_agent.md`
  后端岗位工时评估。
- `frontend_agent.md`
  前端岗位工时评估。
- `app_agent.md`
  APP/移动端岗位工时评估。
- `ui_agent.md`
  UI/UX 岗位工时评估。
- `testing_agent.md`
  测试岗位工时评估。
- `algorithm_agent.md`
  算法岗位工时评估。
- `ops_agent.md`
  运维岗位工时评估。

### core/

核心基础设施。

- `config.py`
  加载配置、默认值合并、API key 解析。
- `llm.py`
  LLM provider 抽象，当前支持 OpenAI 和 Claude。
- `parser.py`
  模型 JSON 输出提取与解析。
- `module.py`
  模块树拍平。
- `merge.py`
  多岗位评估结果合并。
- `prompts.py`
  agent prompt 目录定位与加载。
- `session.py`
  session 目录和文件落盘。
- `validation.py`
  schema 与业务校验。

### output/

- `excel.py`
  Excel 导出。
- `report.py`
  Markdown 报告生成。

### sessions/

每次运行的输出目录，保存：

- `workload.xlsx`
- `report.md`
- `session.json`

## 主调用链

主流程固定为：

1. CLI 读取输入
2. `presale_agent`
3. 澄清循环，最多 `max_clarify_rounds`
4. `dispatcher_agent` 给出岗位建议
5. 所有岗位 agent 都参与评估
6. normalize + validate
7. merge
8. 导出 session / report / excel

## 当前 agent 注册方式

当前项目没有独立的 agent registry 文件，使用两层约定：

1. `harness.py` 中的 `ROLE_AGENTS` 维护岗位 agent 名单
2. `core/prompts.py` 默认从 `agents/{agent_name}.md` 加载 prompt

因此新增 agent 时，至少需要同步：

1. 新增 `agents/<name>_agent.md`
2. 更新 `harness.py` 中的 `ROLE_AGENTS`
3. 更新 `core/validation.py` 中的合法角色集合
4. 如有必要，更新 README 和本文件

## 公共约束

### 输入输出约束

- 所有 agent 必须输出 JSON，不允许输出 Markdown 或额外解释。
- `presale_agent` 输出：
  - `modules`
  - `module_assignments`
  - `clarifications`
  - `next_action`
- 岗位 agent 输出：
  - `estimations`

### 模块约束

- 模块默认只保留一个层级，所有模块都应视为最细模块。
- 如果用户已经提供了模块列表，应优先直接采用，不再重新抽象为更大模块。
- `module_assignments` 必须覆盖所有模块。

### 澄清约束

- 最多 5 轮澄清。
- `--non-interactive` 模式下，如果需要澄清则直接失败。

### 评估约束

- 从 `product` 到 `ops` 的所有岗位都会参与评估，不再只调用 dispatcher 推荐的角色。
- 如果需求包含移动端或 APP 交付，`app` 角色应参与评估。
- 已分配给某岗位的模块，岗位 agent 必须给出估算。
- 未分配给某岗位的模块，岗位 agent 可以自行返回 `0h`，harness 也可以自动补 `0h`。
- 工时必须是非负数。
- 支持通过 `app.effort_buffer_ratio` 为原始工时增加冗余，默认 20%。

### Provider 约束

- 当前支持 `openai` 和 `claude`。
- 通过 `config.toml` 提供 API key 或环境变量名。

## 维护建议

- 优先修改 `agents/*.md` 来调整各岗位评估策略。
- 如果修改 schema，必须同步更新 `validation.py` 和 `README.md`。
- 如果新增角色，必须同步更新 `ROLE_AGENTS`、校验逻辑、agent prompt 和文档。
