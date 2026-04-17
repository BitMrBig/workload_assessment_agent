# Workload Agent

一个基于多 Agent 混合编排模式的 CLI 工具，用于将需求文本转换为结构化工作量评估结果。

## 功能

- 售前需求澄清、模块拆解与岗位评估编排
- 最多 5 轮澄清
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
