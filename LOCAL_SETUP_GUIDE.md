# ROMA 本地运行指南

## 📋 已配置的修改

这个版本已经预配置了以下修改：

### ✅ 端口配置
- **前端端口：** 3001 (避免与其他服务冲突)
- **后端端口：** 5000

### ✅ Claude API 配置
- **Provider：** anthropic
- **API Key：** 通过环境变量 `ANTHROPIC_API_KEY`
- **Base URL：** 通过环境变量 `ANTHROPIC_BASE_URL`

## 🚀 本地安装步骤

### 1. 克隆您的 Fork 仓库

```bash
git clone https://github.com/tulong66/ROMA.git
cd ROMA
```

### 2. 创建环境配置文件

```bash
cp .env.example .env
```

然后编辑 `.env` 文件，添加您的 Claude API 配置：

```bash
# ===== LLM Provider Keys =====
# Anthropic API key (for Claude models)
ANTHROPIC_API_KEY=sk-rBpxbR3mWOCea0GZ1YpaGaiHicUb13IgapN62iJD9jrInPiG

# Anthropic API custom base URL
ANTHROPIC_BASE_URL=https://anyrouter.top

# ===== 其他可选配置 =====
# OpenRouter API key (primary LLM provider) - 可选
OPENROUTER_API_KEY=your_openrouter_key_here

# OpenAI API key (optional - for direct OpenAI usage)
OPENAI_API_KEY=your_openai_key_here

# Google GenAI API key (optional - for Gemini models)
GOOGLE_GENAI_API_KEY=your_google_genai_key_here

# Exa API key (for web search capabilities)
EXA_API_KEY=your_exa_key_here

# ===== Server Configuration (Optional) =====
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# ===== Logging Configuration (Optional) =====
LOG_LEVEL=INFO
LOG_FILE_MODE=w
```

### 3. 运行 Docker 安装

```bash
./setup.sh
```

选择 `1` (Docker Setup - 推荐)

### 4. 访问应用

安装完成后：

- **前端界面：** http://localhost:3001
- **后端 API：** http://localhost:5000
- **健康检查：** http://localhost:5000/api/health

## 🔧 命令行 API 使用

### 检查状态
```bash
curl http://localhost:5000/api/simple/status
```

### 执行任务
```bash
curl -X POST http://localhost:5000/api/simple/execute \
     -H 'Content-Type: application/json' \
     -d '{"goal": "分析人工智能在医疗领域的应用"}'
```

### 研究任务
```bash
curl -X POST http://localhost:5000/api/simple/research \
     -H 'Content-Type: application/json' \
     -d '{"topic": "量子计算的最新突破"}'
```

## 🔍 故障排除

### 端口冲突
如果仍有端口冲突，可以修改 `docker/docker-compose.yml`：
```yaml
ports:
  - "3002:3000"  # 改为其他端口
```

### API 连接问题
1. 确认 `.env` 文件中的 API 配置正确
2. 重启 Docker 容器：
   ```bash
   cd docker && docker compose restart
   ```

### 查看日志
```bash
cd docker && docker compose logs -f
```

## 📚 文档资源

- **用户指南：** `.bmad-core/user-guide.md`
- **架构文档：** `CLAUDE.md`
- **设置文档：** `docs/SETUP.md`

## 🎯 功能特性

- ✅ 递归层次化任务分解
- ✅ 实时 WebSocket 可视化
- ✅ 多代理协作
- ✅ Claude API 支持
- ✅ 命令行和 Web 界面
- ✅ 企业级安全配置

---

**祝您使用愉快！** 🚀