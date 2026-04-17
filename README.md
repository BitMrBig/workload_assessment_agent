# Workload Agent

一个基于多 Agent 混合编排模式的 CLI 工具，用于将需求文本转换为结构化工作量评估结果。

## 功能

- 售前需求澄清、模块拆解与岗位评估编排
- 最多 5 轮澄清
- 每个模块都会带一段功能描述，描述来源于售前 Agent 对需求的理解
- 澄清完成后会先展示模块清单及对应描述，必须由用户确认后才进入评估
- 用户可在确认阶段继续与售前 Agent 对话，增删改模块或修正模块描述，直到明确确认
- CLI 输出阶段进度日志，便于观察执行状态
- Dispatcher 提供岗位建议，但从产品到运维的所有岗位都会参与评估
- 支持 APP 岗位评估，用于移动端/客户端工作量
- 各岗位输出结构化工时估算，包含产品、UI、后端、前端、APP、测试、算法、运维，并可自行决定是否给出 0h
- 支持可配置的工作量冗余比例，默认 20%
- 默认按单层最细模块评估；如果用户已经给出模块列表，优先直接使用
- 导出 Excel、Markdown 报告和完整会话记录
- 支持 OpenAI 与 Claude API

## 快速开始

1. 创建并激活 Python 3.9+ 虚拟环境
2. 安装依赖：

```bash
pip install -e .
```

3. 复制 `config.example.toml` 为 `config.toml`
4. 填写 `config.toml` 中的 API Key，或设置环境变量 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`
5. 运行：

```bash
python3 main.py --config config.toml --input "做一个支持登录、注册、订单管理的后台系统"
```

或：

```bash
python3 main.py --config config.toml --input-file ./requirements.txt
```

安装后也可以直接使用 CLI 命令：

```bash
workload-harness --config config.toml --input "做一个支持登录、注册、订单管理的后台系统"
```

默认 OpenAI 模型为 `gpt-5.4-mini`，默认澄清轮次上限为 `5`。

## 流程

1. 输入原始需求文本。
2. `presale_agent` 做需求澄清，并生成单层最细模块列表、模块功能描述与岗位分配建议。
3. 如果信息不足，CLI 进入澄清问答，直到达到可评估状态或超过最大澄清轮次。
4. 澄清完成后，CLI 展示当前模块清单及对应功能描述，请用户确认。
5. 用户如果提出“新增、删除、修改、补充”要求，仍然交给 `presale_agent` 处理，更新模块列表和描述后再次展示确认。
6. 只有当 `presale_agent` 判断用户已经明确确认模块清单及描述后，才继续进入评估流程。
7. `dispatcher_agent` 提供岗位建议，但所有岗位都会参与评估。
8. 各岗位 Agent 会结合最细模块及其功能描述输出估算，最后合并为 Markdown 报告、Excel 和完整会话记录。

## 输出

每次运行会在 `sessions/<session_id>/` 下生成：

- `session.json`
- `report.md`
- `workload.xlsx`

## 打包

```bash
python3 -m build --no-isolation
```

## 许可证

本项目使用 MIT License。
