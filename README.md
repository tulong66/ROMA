# 🚀 SentientResearchAgent

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![PDM](https://img.shields.io/badge/PDM-purple)](https://pdm-project.org)
[![Built on AgnoAgents](https://img.shields.io/badge/Built%20on-AgnoAgents-green)](https://github.com/your/agnoagents)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Community](https://img.shields.io/badge/Community-SENT%20Tokens-orange)]()

**Build ANY hierarchical task-solving agent using just three building blocks: Think 🤔, Write ✍️, and Search 🔍**

SentientResearchAgent is a **general-purpose hierarchical task execution framework** that can decompose ANY complex task into manageable subtasks using the MECE (Mutually Exclusive, Collectively Exhaustive) principle. Whether you're building a podcast generator, market analyzer, story writer, or code reviewer - if you can think of it in terms of Think, Write, and Search operations, you can build it here.

## 🎯 What Can You Build?

The only limit is your imagination. Here are just a few examples:

### 🎙️ **Content Creation**
- **Podcast Generator**: Research topics → Generate scripts → Create show notes
- **Blog Automation**: Research → Outline → Write → Edit → Publish
- **Story Writer**: Plot development → Character creation → Chapter writing
- **Video Scripts**: Research → Storyboard → Script → Shot lists

### 📊 **Analysis & Intelligence**
- **Market Analyzer**: Data gathering → Trend analysis → Report generation
- **Crypto Analytics**: On-chain data → Technical analysis → Trading signals
- **Competitor Research**: Information gathering → SWOT analysis → Strategy recommendations
- **Scientific Literature Review**: Paper search → Analysis → Synthesis → Citation management

### 💻 **Technical Applications**
- **Code Generator**: Requirements analysis → Architecture design → Implementation → Documentation
- **API Designer**: Specification → Implementation → Testing → Documentation
- **Documentation Writer**: Code analysis → Structure planning → Content generation

### 🎨 **Creative Workflows**
- **Game Designer**: Concept → Mechanics → Narrative → Level design
- **Art Director**: Mood boards → Style guides → Asset specifications
- **Music Composer**: Theme analysis → Composition → Arrangement

## 🧠 The MECE Framework

Every task in SentientResearchAgent is broken down into three fundamental operations:

### 🤔 **THINK** - Reasoning & Analysis
- Data analysis and interpretation
- Strategic planning and decision making
- Pattern recognition and insights
- Problem solving and evaluation

### ✍️ **WRITE** - Content Generation & Synthesis
- Report writing and documentation
- Creative content generation
- Code implementation
- Summary and synthesis creation

### 🔍 **SEARCH** - Information Retrieval
- Web searches and research
- Database queries
- Literature reviews
- API calls and data fetching

These three operations can be combined recursively to create sophisticated workflows of any complexity.

## ⚡ Key Features

### 🔄 **Recursive Task Decomposition**
- Automatically breaks down complex tasks into subtasks
- Customizable depth control
- Intelligent dependency management
- Parallel execution of independent tasks

### 🤖 **Agent/LLM Agnostic**
- Use ANY LLM provider (OpenAI, Anthropic, Google, local models)
- Built on [AgnoAgents](https://github.com/your/agnoagents) for maximum flexibility
- Multi-modal support out of the box
- Tool integration and MCP support

### 🔍 **Transparent Execution**
- **Stage Tracing**: See exactly what goes into and comes out of every agent
- Debug and optimize your workflows with full visibility
- Understand the reasoning behind every decision
- Perfect for rapid iteration and improvement

### 🌊 **Execution Flow**
- **Top-down decomposition**: Tasks break down from general to specific
- **Bottom-up aggregation**: Results synthesize from specific to general
- **Left-to-right dependencies**: Tasks can depend on siblings for context

### 👥 **Human-in-the-Loop (HITL)**
- Review and modify plans before execution
- Intervene at any stage of the process
- Continuous improvement through human feedback
- Build trust through transparency

### 🎯 **"Vibe Prompting" for Non-Technical Users**
Just describe what you want in natural language, and the framework will figure out the rest:
- "Make me a podcast about AI safety"
- "Analyze the crypto market for the next bull run"
- "Write a fantasy story about dragons in space"
- "Create a business plan for my startup idea"

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/SentientResearchAgent.git
cd SentientResearchAgent

# Run the automated setup
./setup.sh
```

Choose between:
- **Docker Setup** (Recommended) - One-command setup with isolation
- **Native Setup** - Direct installation for development

### 🏗️ Optional: E2B Sandbox Integration

For secure code execution capabilities, optionally set up E2B sandboxes:

```bash
# After main setup, configure E2B (requires E2B_API_KEY and AWS credentials in .env)
./setup.sh --e2b

# Test E2B integration
./setup.sh --test-e2b
```

**E2B Features:**
- 🔒 **Secure Code Execution** - Run untrusted code in isolated sandboxes
- ☁️ **S3 Integration** - Automatic data sync between local and sandbox environments  
- 🚀 **goofys Mounting** - High-performance S3 filesystem mounting
- 🔧 **AWS Credentials** - Passed securely via Docker build arguments

### 💾 S3 Data Persistence

SentientResearchAgent includes a comprehensive S3 mounting solution for seamless data persistence across all environments:

```bash
# During setup, you'll be asked:
# "Setup S3 mounting for data persistence? (y/n)"

# Universal mount directory: /opt/sentient (identical across all platforms)
```

**🔒 Enterprise-Grade Security Features:**
- 🛡️ **Path Injection Protection** - Validated mount directories prevent security vulnerabilities
- 🔐 **AWS Credentials Validation** - Pre-flight checks ensure S3 bucket access before mounting
- 📁 **Safe Environment Parsing** - Secure handling of configuration files and environment variables
- 🔍 **Mount Verification** - Comprehensive testing of mount functionality before proceeding
- ⚡ **FUSE Dependency Checking** - Automatic verification of macFUSE/FUSE requirements

**🚀 Advanced Mounting Capabilities:**
- 🔄 **Exact Path Matching** - Identical mount paths across local, Docker, and E2B environments
- ⚡ **Zero-Sync Latency** - Live filesystem access via high-performance goofys mounting
- 📁 **Dynamic Project Isolation** - Runtime project-based folders with configurable structures
- 🛠 **Cross-Platform Support** - Seamless operation on macOS and Linux with auto-installation
- 🔐 **Persistent Services** - Auto-mount on boot via systemd/launchd with proper configuration
- 🔧 **Flexible Configuration** - Boolean values accept multiple formats (true/yes/1/on/enabled)

**🏗️ Architecture Benefits:**
1. **Unified Data Layer**: All environments access the exact same S3-mounted directory
2. **No Path Translation**: Eliminates complexity with consistent `${S3_MOUNT_DIR}` across all systems
3. **Instant Availability**: Files written by data toolkits appear immediately in E2B sandboxes
4. **Secure Docker Integration**: Dynamic compose file selection with validated mount paths
5. **Production-Ready**: Enterprise security validation with comprehensive error handling

**How It Works:**
```bash
# Local System: Data toolkit saves to
${S3_MOUNT_DIR}/project_123/binance/price_data_1642567890.parquet

# Docker Container: Exact same path
${S3_MOUNT_DIR}/project_123/binance/price_data_1642567890.parquet  

# E2B Sandbox: Identical path structure
${S3_MOUNT_DIR}/project_123/binance/price_data_1642567890.parquet
```

Make sure that S3_MOUNT_DIR is universal across all platform as absolute path so the path of the files would be consistent.

**Perfect data consistency with zero configuration overhead!**

### 🐳 Docker S3 mounting with goofys (setup.sh pipeline)

When you run `./setup.sh` and choose Docker, the script:

1. Validates `S3_MOUNT_ENABLED` and `S3_MOUNT_DIR` from your `.env`.
2. If enabled and valid, starts Compose with `docker/docker-compose.yml` plus the S3 override `docker/docker-compose.s3.yml`.
3. The override grants FUSE permissions (`/dev/fuse`, `SYS_ADMIN`, apparmor unconfined) required for `goofys` inside the container.
4. The backend container entrypoint runs `/usr/local/bin/startup.sh`, which mounts S3 using `goofys` before launching the app.

macOS note (Docker mode): Docker Desktop does not support FUSE mounts inside containers. Our setup mounts S3 on the host at the universal path (`/opt/sentient`) and bind-mounts it into the container. The container startup detects the existing mount and verifies it maps to the intended bucket, skipping in-container goofys. On Linux Docker engines, the container can mount directly.

Pass additional `goofys` flags via the environment variable `GOOFYS_EXTRA_ARGS` in your `.env`:

```bash
# .env
S3_MOUNT_ENABLED=true
S3_MOUNT_DIR=/opt/sentient
S3_BUCKET_NAME=your-s3-bucket
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1

# Optional: extra goofys flags
GOOFYS_EXTRA_ARGS="--allow-other --stat-cache-ttl=10s --type-cache-ttl=10s"
```

Notes:
- All variables from `.env` are injected into the backend container by Compose and read by `startup.sh`.
- The command specified in the image (`uv run python -m sentientresearchagent`) is forwarded unchanged by `startup.sh` via `exec "$@"`.

### Your First Agent in 5 Minutes

```python
from sentientresearchagent import SentientAgent

# Create a podcast generator
agent = SentientAgent.create()

result = await agent.run(
    "Create a 10-minute podcast episode about the future of renewable energy"
)

print(result)  # Your complete podcast script with intro, segments, and outro!
```

### Using Pre-built Profiles

```python
from sentientresearchagent import ProfiledSentientAgent

# Use the crypto analytics profile
agent = ProfiledSentientAgent.create_with_profile("crypto_analytics_agent")

result = await agent.run(
    "Analyze Ethereum's DeFi ecosystem and identify emerging trends"
)
```

## 📖 Documentation

- **[🚀 Introduction](docs/INTRODUCTION.md)** - Understand the vision and possibilities
- **[🍳 Quick Start Cookbook](docs/QUICKSTART_COOKBOOK.md)** - 5-minute agent recipes
- **[🧠 Core Concepts](docs/CORE_CONCEPTS.md)** - Master the MECE framework
- **[💡 Use Cases](docs/USE_CASES.md)** - Real-world applications by industry
- **[🤖 Agents Guide](docs/AGENTS_GUIDE.md)** - Create and customize agents
- **[🔄 Execution Flow](docs/EXECUTION_FLOW.md)** - Understand the task flow
- **[🔍 Stage Tracing](docs/STAGE_TRACING.md)** - Debug and optimize your agents
- **[⚙️ Configuration](docs/CONFIGURATION.md)** - Fine-tune your setup

## 🏗️ Architecture Overview

```
Your Request: "Create a market analysis report"
                    │
                    ▼
           ┌─────────────────┐
           │    ATOMIZER     │ ← "Is this task atomic or needs planning?"
           └────────┬────────┘
                    │ Decides: PLAN node
                    ▼
           ┌─────────────────┐
           │   PLAN NODE     │ ← "Break into subtasks"
           └────────┬────────┘
                    │ Decomposes into
     ┌──────────────┼──────────────┐
     ▼              ▼              ▼
┌─────────┐   ┌─────────┐   ┌─────────┐
│ SEARCH  │   │ THINK   │──▶│ WRITE   │  ← Horizontal flow
│ Market  │   │ Analyze │   │ Report  │    (WRITE waits for THINK)
│  Data   │   │  Data   │   │         │
└────┬────┘   └────┬────┘   └────┬────┘
     │              │              │
     ▼              ▼              ▼
[ATOMIZER]     [ATOMIZER]     [ATOMIZER] ← 🔄 RECURSIVE: Each subtask
     │              │              │         goes through same process
     ├──────────────┼──────────────┤
     ▼              ▼              ▼
[EXECUTE]      [EXECUTE or    [EXECUTE or
              PLAN→AGGREGATE]  PLAN→AGGREGATE]
     │              │              │
     └──────────────┼──────────────┘
                    ▼
           ┌─────────────────┐
           │   AGGREGATOR    │ ← "Combine all subtask results"
           └────────┬────────┘    (Only after PLAN nodes complete)
                    │ Returns to parent
                    ▼
           ┌─────────────────┐
           │ Final Result    │
           └─────────────────┘

Key Components:
- ATOMIZER: Decides if task needs decomposition (PLAN) or direct execution (EXECUTE)
- PLAN NODE: Breaks complex tasks into subtasks (THINK, WRITE, SEARCH)
- EXECUTE NODE: Directly executes atomic tasks (no aggregation needed)
- AGGREGATOR: Only combines results after PLAN nodes complete their subtasks
- ➡️ Horizontal Dependencies: Tasks can depend on siblings (must wait for completion)
- 🔄 RECURSIVE: Each subtask goes through the entire process again
- 📦 Aggregation happens locally after each group of subtasks completes
```

## 💰 Community & SENT Token Incentives

### 🏆 Build Agents, Earn Rewards!

We're building a vibrant community of agent creators. Share your innovative agents and earn SENT tokens!

**Current Bounties:**
- 🎙️ **Best Podcast Generator**: 10,000 SENT
- 📊 **Best Market Analyzer**: 10,000 SENT  
- 📝 **Best Content Creator**: 10,000 SENT
- 🎮 **Most Creative Use Case**: 10,000 SENT

### How to Participate:
1. Build an awesome agent using SentientResearchAgent
2. Share it with the community
3. Get votes and feedback
4. Earn SENT tokens for popular agents!

**Join our community:**
- [Discord](https://discord.gg/sentientagent)
- [Telegram](https://t.me/sentientagent)
- [Twitter](https://twitter.com/sentientagent)

See [COMMUNITY.md](docs/COMMUNITY.md) for details on the SENT token program.

## 🙏 Acknowledgments

This project was inspired by the hierarchical planning approach described in:

```bibtex
@misc{xiong2025heterogeneousrecursiveplanning,
      title={Beyond Outlining: Heterogeneous Recursive Planning for Long-form Writing with Language Models}, 
      author={Ruibin Xiong and Yimeng Chen and Dmitrii Khizbullin and Mingchen Zhuge and Jürgen Schmidhuber},
      year={2025},
      eprint={2503.08275},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2503.08275}
}
```

Special thanks to the WriteHERE project for pioneering the hierarchical approach to AI task planning.

## 🛠️ Technical Stack

- **Framework**: Built on [AgnoAgents](https://github.com/your/agnoagents)
- **Backend**: Python 3.12+ with FastAPI/Flask
- **Frontend**: React + TypeScript with real-time WebSocket
- **LLM Support**: Any provider via LiteLLM
- **Data Persistence**: Enterprise S3 mounting with security validation
  - 🔒 **goofys FUSE mounting** for zero-latency file access
  - 🛡️ **Path injection protection** with comprehensive validation
  - 🔐 **AWS credentials verification** before operations
  - 📁 **Dynamic Docker Compose** with secure volume mounting
- **Code Execution**: E2B sandboxes with unified S3 integration
- **Security**: Production-grade validation and error handling
- **Features**: Multi-modal, tools, MCP, hooks, caching

## 📦 Installation Options

### Quick Start (Recommended)
```bash
# Main setup (choose Docker or Native)
./setup.sh

# Optional: Setup E2B sandbox integration
./setup.sh --e2b

# Test E2B integration  
./setup.sh --test-e2b
```

### Command Line Options
```bash
./setup.sh --docker     # Run Docker setup directly
./setup.sh --docker-from-scratch  # Rebuild Docker images/containers from scratch (down -v, no cache)
./setup.sh --native     # Run native setup directly (macOS/Ubuntu/Debian)
./setup.sh --e2b        # Setup E2B template (requires E2B_API_KEY + AWS creds)
./setup.sh --test-e2b   # Test E2B template integration
./setup.sh --help       # Show all available options
```

### Manual Installation
See [docs/SETUP.md](docs/SETUP.md) for detailed instructions.

### Configuration
1. Copy `.env.example` to `.env`
2. Add your LLM API keys
3. **Optional**: Configure comprehensive S3 mounting:
   ```bash
   # ===== S3 Mounting Configuration =====
   # Enable S3 mounting (accepts: true/yes/1/on/enabled)
   S3_MOUNT_ENABLED=true
   
   # Universal mount directory (identical across all platforms)
   S3_MOUNT_DIR=/opt/sentient
   
   # AWS S3 Configuration
   S3_BUCKET_NAME=your-s3-bucket
   AWS_ACCESS_KEY_ID=your_aws_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret
   AWS_REGION=us-east-1
   
   # ===== E2B Integration (Optional) =====
   E2B_API_KEY=your_e2b_api_key_here
   ```
4. Customize `sentient.yaml` as needed

**🔒 Security Features in Configuration:**
- **Path validation**: Mount directories are validated against injection attacks
- **AWS verification**: Credentials are tested before mounting attempts
- **FUSE checking**: System dependencies verified automatically
- **Mount verification**: Comprehensive functionality testing before proceeding
- **Flexible booleans**: `S3_MOUNT_ENABLED` accepts multiple true/false formats

## 🤝 Contributing

We welcome contributions! Whether it's:
- New agent templates
- Use case examples
- Documentation improvements
- Core framework enhancements

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) file

## 👥 Contributors

### 🏆 Lead Contributor

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/salzubi401">
        <img src="https://github.com/salzubi401.png" width="100px;" alt="Salah Al-Zubi"/>
        <br />
        <sub><b>Salah Al-Zubi</b></sub>
      </a>
      <br />
      <sub>Creator & Lead Developer</sub>
    </td>
  </tr>
</table>

### ✨ Contributors

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tr>
    <td align="center">
      <a href="https://github.com/contributor1">
        <img src="https://github.com/contributor1.png?size=50" width="50px;" alt=""/>
        <br />
        <sub><b>Contributor 1</b></sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/contributor2">
        <img src="https://github.com/contributor2.png?size=50" width="50px;" alt=""/>
        <br />
        <sub><b>Contributor 2</b></sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/contributor3">
        <img src="https://github.com/contributor3.png?size=50" width="50px;" alt=""/>
        <br />
        <sub><b>Contributor 3</b></sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/contributor4">
        <img src="https://github.com/contributor4.png?size=50" width="50px;" alt=""/>
        <br />
        <sub><b>Contributor 4</b></sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/contributor5">
        <img src="https://github.com/contributor5.png?size=50" width="50px;" alt=""/>
        <br />
        <sub><b>Contributor 5</b></sub>
      </a>
    </td>
  </tr>
</table>
<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->
<!-- ALL-CONTRIBUTORS-LIST:END -->

<sub>This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!</sub>

## 🚀 Start Building Today!

```bash
# Install
git clone https://github.com/yourusername/SentientResearchAgent.git
cd SentientResearchAgent
./setup.sh

# Optional: Enable secure code execution
./setup.sh --e2b

# Create your first agent
python -m sentientresearchagent

# Or dive into examples
jupyter notebook notebooks/quickstart.ipynb
```

**Remember**: If you can think it, you can build it with Think, Write, and Search! 🚀

---

<p align="center">
  <strong>Join the revolution in hierarchical AI agents. Build something amazing today!</strong>
</p>