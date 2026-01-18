# Claude Code Chat History Viewer

一个优雅的 Claude Code 对话历史查看器，支持实时读取所有对话窗口，无需手动保存。

## ✨ 功能特点

- 🔄 **实时自动读取** - 自动扫描所有项目的 jsonl 文件，无需手动保存
- 🌙 **暗黑模式** - 护眼深色主题，一键切换
- 📱 **可折叠侧边栏** - 全屏查看对话内容
- 🔧 **工具调用折叠** - 自动识别并折叠 Tool Use / Tool Result
- 📋 **一键复制** - 复制任何消息或工具调用
- 🎯 **智能标题** - 自动分析对话内容生成标题
- 🔍 **实时搜索** - 快速查找对话内容
- 🚀 **一键启动** - 自动检查依赖并安装
- ⚡ **后台运行** - 关闭窗口服务继续运行
- 🔄 **开机自启** - 可选设置开机自动启动

## 🚀 快速开始

### Windows 用户（推荐）

```bash
# 1. 下载项目
git clone https://github.com/yourusername/chat-history.git
cd chat-history

# 2. 一键启动
start.bat

# 3. 选择是否设置开机自启动 (Y/N)
# 4. 选择是否打开浏览器 (Y/N)
# 5. 关闭窗口，服务在后台继续运行
```

访问地址：**http://localhost:13001**

### 系统要求

- Windows 10/11
- Python 3.7+
- Claude Code 已安装使用

## 📦 安装

### 一键启动（含依赖检查）

双击运行 `start.bat`，脚本会自动：
- ✓ 检查 Python 环境
- ✓ 检查并安装 Flask 依赖
- ✓ 检查端口 13001 是否可用
- ✓ 在后台启动服务
- ✓ 可选设置开机自启动

### 手动启动

```bash
python scripts/web_server.py
```

## 🎨 界面预览

### 亮色模式
- 简洁明亮的设计
- 白色/绿色气泡（微信风格）
- 适合白天使用

### 暗黑模式
- 深色护眼主题
- 深蓝/深绿配色
- 适合夜间使用

## 📂 项目结构

```
chat-history/
├── scripts/
│   ├── web_server.py         # Web服务器（端口13001）
│   └── save_from_jsonl.py    # 手动保存脚本（可选）
├── assets/
│   └── manager.html           # Web界面
├── start.bat                  # 一键启动脚本
├── stop_service.bat           # 停止服务脚本
├── uninstall_service.bat      # 取消自启动脚本
├── 自启动方案说明.md           # 详细使用文档
├── README.md                  # 本文件
├── LICENSE                    # MIT许可证
├── requirements.txt           # Python依赖
└── .gitignore                 # Git忽略文件
```

## 🔧 配置

### 修改端口

编辑 `scripts/web_server.py` 最后一行：

```python
if __name__ == '__main__':
    run_server(13001)  # 改为你想要的端口
```

同时编辑 `start.bat` 中的端口号。

### 修改数据源

编辑 `scripts/web_server.py` 中的：

```python
PROJECTS_DIR = Path("C:/Users/YOUR_USERNAME/.claude/projects")
```

## 💡 使用方法

1. **查看对话** - 打开界面自动显示所有对话
2. **搜索** - 使用搜索框查找关键词
3. **筛选** - 按项目名称筛选对话
4. **复制** - 悬停消息点击复制按钮
5. **暗黑模式** - 点击右上角月亮图标
6. **折叠侧边栏** - 点击左上角菜单图标
7. **工具调用** - 点击工具区域展开详情

## 🛠️ 服务管理

| 操作 | 命令 |
|------|------|
| 启动服务 | `start.bat` |
| 停止服务 | `stop_service.bat` |
| 取消自启动 | `uninstall_service.bat` |
| 访问地址 | http://localhost:13001 |

## 🌟 开机自启动

### 方法一：使用 start.bat（推荐）

运行 `start.bat`，当提示时输入 `Y`：

```
Enable auto-start on boot? (Y/N): Y
```

### 方法二：手动设置

详见 [自启动方案说明.md](自启动方案说明.md)

## 🆚 与 claude-run 对比

| 功能 | 本项目 | claude-run |
|------|--------|------------|
| 一键启动 | ✅ BAT脚本 | ❌ 需Node.js |
| 依赖检查 | ✅ 自动安装 | ❌ 手动安装 |
| 后台运行 | ✅ | ❌ |
| 开机自启 | ✅ 支持 | ❌ 不支持 |
| 暗黑模式 | ✅ | ✅ |
| 可折叠侧边栏 | ✅ | ✅ |
| 工具调用折叠 | ✅ | ✅ |
| 一键复制 | ✅ | ❌ |
| 中文界面 | ✅ | ❌ |
| 微信风格 | ✅ | ❌ |
| 实时刷新 | ✅ 点击刷新 | SSE流式 |

## 📝 开发计划

- [x] 后台运行
- [x] 开机自启动
- [x] 依赖自动检查
- [ ] 添加恢复对话功能
- [ ] 支持导出对话为 Markdown
- [ ] 添加标签和收藏
- [ ] SSE 实时流式更新
- [ ] 多语言支持

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [claude-run](https://github.com/kamranahmedse/claude-run) - 提供设计灵感
- Claude Code 团队

---

**Made with ❤️ for Claude Code users**
