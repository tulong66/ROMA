# 快速推送到您的 GitHub

由于 GCP 环境的网络限制，无法直接推送到 GitHub。但是修改已经保存在本地。

## 🔄 如何同步到您的 GitHub

### 方法一：在本地克隆后手动同步（推荐）

1. **在您的本地机器上：**
```bash
git clone https://github.com/tulong66/ROMA.git
cd ROMA
```

2. **应用相同的修改：**

**修改 `docker/docker-compose.yml` 第40行：**
```yaml
# 将这行：
- "3000:3000"
# 改为：
- "3001:3000"
```

**修改 `sentient.yaml` 第5-9行：**
```yaml
# LLM Infrastructure (used by your AgnoAgents)
llm:
  provider: "anthropic"  # Using Anthropic via anyrouter.top
  api_key: "${ANTHROPIC_API_KEY}"  # Use environment variable
  base_url: "${ANTHROPIC_BASE_URL}"  # Use custom base URL
  timeout: 300.0  # Increased to 5 minutes for complex code execution and reasoning
  max_retries: 3
```

3. **提交并推送：**
```bash
git add docker/docker-compose.yml sentient.yaml
git commit -m "配置 ROMA 支持自定义 Claude API"
git push origin main
```

### 方法二：直接在 GitHub 网页编辑

1. 访问 https://github.com/tulong66/ROMA
2. 点击 `docker/docker-compose.yml` 文件
3. 点击编辑按钮（铅笔图标）
4. 将第40行 `"3000:3000"` 改为 `"3001:3000"`
5. 提交更改

重复上述步骤编辑 `sentient.yaml` 文件。

### 方法三：使用 GitHub CLI（如果已安装）

```bash
# 如果您在 GCP 上安装了 GitHub CLI
gh auth login
git push my-fork main
```

## ✅ 完成后

无论用哪种方法，完成后您就可以在本地运行：

```bash
git clone https://github.com/tulong66/ROMA.git
cd ROMA
cp .env.example .env
# 编辑 .env 添加您的 API 配置
./setup.sh
```

然后访问 http://localhost:3001 使用 ROMA！