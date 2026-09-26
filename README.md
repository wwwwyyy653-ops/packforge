# 包装参数化设计软件（全栈）

基于 DeepSeek 会话方案（PackForge Studio 全栈开发计划，融合 盒易PackTools / 结构工坊 Foldary 能力）实现的全栈 Web 应用：**15 种盒型参数化刀模引擎 + 2D 展开 + 3D 折叠 + 印前预检 + 生产导出 + 包装工具箱 + AI Agent**。

> 按原方案要求：已去除品牌名与插件系统，以独立 Web 全栈应用形态交付。

---

## 一、功能总览

| 模块 | 说明 |
|---|---|
| 🧩 **盒型设计器** | 15 种盒型参数化生成（单插盒/双插盒/扣底盒/锁底盒/吊孔盒/翻盖盒/邮寄盒/飞机盒/天地盖/抽屉盒/套筒/手提盒/展示盒/开窗盒/多件装），参数修改驱动全几何重算 |
| 📐 **2D 刀模** | SVG 矢量渲染：切割线（红）、折痕线（蓝虚线）、面板标签、孔洞 |
| 🧊 **3D 折叠** | Three.js 实时 3D 预览：拖拽旋转、滚轮缩放、折叠进度滑块动画、两件套分离显示 |
| 🛠️ **工具箱** | 抗压计算（McKee/BCT）、拼版算料（正放/旋转/混合交错）、纸张换算、装柜模拟（20GP/40GP/40HQ）、成本估算（材料/印刷/后道/模切/糊盒/人工/损耗） |
| 🔍 **印前预检** | 自相交/退化面板/零长度边/游离面板/尺寸阈值/面板重叠检测 |
| 📤 **生产导出** | SVG / DXF（R12 激光刀模机可读）/ PDF 三种格式 |
| 🤖 **AI Agent** | 自然语言 → 意图解析 → 工具调用计划（box.search/box.create/finish.apply 等）→ 执行并返回结果；执行成功的建盒可**一键存为配方**，配方模板支持一键复用 |
| 🗄️ **项目系统** | SQLite 项目/盒型 CRUD、示例种子项目、工具调用日志、AI 会话 |

## 二、技术栈

- **后端**：Python 3.14 · FastAPI · SQLite（WAL）· Pydantic
- **前端**：React 19 · TypeScript · Vite 6 · Three.js · React Router 7
- **部署**：前后端分离，开发期 Vite 代理 `/api` → `:8000`

## 三、目录结构

```
盒型AI软件制作/
├── 启动.bat                 # 一键启动前后端
├── backend/
│   ├── run.py               # 启动入口
│   ├── requirements.txt
│   └── app/
│       ├── main.py          # FastAPI 应用
│       ├── database.py      # SQLite + 种子数据
│       ├── ai_agent.py      # AI 意图解析/计划/执行
│       ├── routers/         # projects/boxes/tools/export/ai
│       └── engines/
│           ├── geometry.py  # 几何基础（面积/相交/共享边）
│           ├── dieline.py   # 15 盒型参数化刀模引擎
│           ├── folding.py   # 3D 折叠（铰链旋转）
│           ├── packtools.py # BCT/拼版/纸张/装柜/成本
│           ├── preflight.py # 印前预检规则引擎
│           └── export.py    # SVG/DXF/PDF 导出
└── frontend/
    ├── vite.config.ts       # 开发代理 /api → :8000
    └── src/
        ├── api.ts           # API 客户端
        ├── fold3d.ts        # 前端 3D 折叠计算（与后端同构）
        ├── components/      # DielineView / Preview3D
        └── pages/           # 概览 / 项目 / 设计器 / 工具箱 / AI
```

## 四、快速开始

### 方式一：一键启动（推荐）
双击 **`启动.bat`**，自动启动后端(:8000) + 前端(:5173) 并打开浏览器。

### 方式二：手动启动
```bash
# 1. 安装后端依赖（首次）
pip install -r backend/requirements.txt

# 2. 启动后端
cd backend && python run.py 8000

# 3. 启动前端（另开终端）
cd frontend && npm install && npm run dev

# 4. 浏览器打开 http://127.0.0.1:5173
```

### API 文档
启动后端后访问：http://127.0.0.1:8000/docs （Swagger 全量接口）

## 五、核心流程（验收链路）

```
选择盒型（如吊孔盒） → 输入 L/W/H → 生成刀模
→ 2D 展开图（切割线+折痕线）
→ 3D 折叠预览（滑块动画）
→ 印前预检（几何/制造规则）
→ 导出 SVG / DXF / PDF（下发激光刀模机）
→ 保存到项目
```

## 六、AI 使用示例

在「AI 助手」页输入：
- `创建一个 120×80×35 的吊孔盒`
- `创建天地盖：长90 宽60 高40，盖深32`
- `做一个 200×120×50 的飞机盒，用 B 瓦楞`
- `做一个 300×200×100 的邮寄盒，算一下抗压强度`

系统解析为工具调用计划 → 确认后执行 → 返回盒型/工艺/计算结果。

执行成功后，AI 助手页会显示「本次 AI 建盒已就绪」，可一键**存为配方**（命名后进入右侧配方模板）；配方模板支持点击一键复用建盒，也可在设计器「存为配方」手动保存当前方案。

## 七、可选配置（环境变量）

| 变量 | 说明 |
|---|---|
| `PACKFORGE_HOME` | 数据库目录（默认 `~/.packforge`，`run.py` 默认 `../.data`） |
| `PACKFORGE_LLM_KEY` | 可选：OpenAI 兼容 API Key（启用 LLM 增强） |
| `PACKFORGE_LLM_BASE` | 可选：LLM Base URL（默认 `https://api.openai.com/v1`） |
| `PACKFORGE_LLM_MODEL` | 可选：模型名（默认 `gpt-4o-mini`） |

## 八、已知边界

- 3D 折叠为通用铰链旋转模型，复杂盒型（展示盒斜切、多件装隔板）的折叠细节为示意级
- 天地盖/抽屉盒为两件套，3D 预览按 Z 轴分离显示
- 未内置实际生产印刷机/刀模机对接（输出标准 DXF R12 即可对接）
- LLM 增强为可选能力，默认本地规则引擎即可完成全部功能
