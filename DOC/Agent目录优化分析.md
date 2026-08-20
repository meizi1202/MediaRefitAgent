# Agent 目录优化分析

## Context

用户询问 agent 目录是否有可优化的方向。

## 当前状态

| 文件 | 行数 | 主要内容 |
|------|------|----------|
| `video_agent.py` | 1339 | LangGraph 状态机、7个Node函数、VideoAgent类 |
| `langchain_agent.py` | 666 | LLM调用、历史管理、意图解析 |
| `cli.py` | 190 | 命令行接口 |
| `llm_client.py` | 84 | LLM客户端 |
| `prompts.py` | 56 | 提示词模板 |
| `__init__.py` | 21 | 模块导出 |

**总行数：2356行**

## 优化方向分析

### 1. 文件拆分（高优先级）
- `video_agent.py` 1339行过大，可按职责拆分
- `langchain_agent.py` 666行包含多个不相关类

### 2. 协议接口（已实施 Phase 2）
- ✅ `agent/interfaces.py` 已定义 Protocol 接口
- ⚠️ video_agent.py 中 node 函数尚未使用依赖注入

### 3. 持久化分离（中优先级）
- `SessionHistoryStore` 可独立为 `memory/store.py`
- 支持多种存储后端（内存/Redis/数据库）

### 4. LLM 客户端分离（低优先级）
- `MinMaxLLM` 可独立为 `llm/minimax.py`
- 统一 LLM 接口，便于切换provider

## 推荐方案：文件拆分

拆分 `video_agent.py` 和 `langchain_agent.py` 为多个文件，保持相同逻辑：

```
agent/
├── __init__.py
├── cli.py
├── prompts.py
├── llm_client.py
├── interfaces.py          # 已存在
├── nodes/                 # 新增：Node函数拆分
│   ├── __init__.py
│   ├── analyze.py         # analyze_node
│   ├── detect.py          # detect_node
│   ├── execute.py         # execute_transform_node
│   └── routing.py         # route_after_execute
├── memory/               # 新增：历史管理
│   ├── __init__.py
│   └── store.py          # SessionHistoryStore
├── video_agent.py        # 精简后的入口（状态机编排）
└── langchain_agent.py   # 精简后的LLM调用
```

**风险评估：低** - 仅移动代码，不改变逻辑

## 实施步骤

1. 创建 `nodes/` 目录，移动 node 函数
2. 创建 `memory/` 目录，移动 SessionHistoryStore
3. 精简 `video_agent.py` 为状态机编排入口
4. 精简 `langchain_agent.py` 为纯LLM调用
5. 更新 `__init__.py` 导出
6. 验证测试通过

## 已完成优化

1. ✅ `agent/interfaces.py` - Protocol 接口定义
2. ✅ `VideoAgent` 支持依赖注入
