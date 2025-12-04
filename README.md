# KurrentDB Skill for Coding Agents

A comprehensive skill that enables AI coding agents to generate accurate, production-ready code for [KurrentDB](https://kurrent.io) (formerly EventStoreDB) - the event-native database.

## Supported Coding Agents

This skill is compatible with multiple AI coding agents that support the SKILL.md format:

| Agent | Platform | Skill Docs |
|-------|----------|------------|
| **Claude Code** | Anthropic | [Skills Documentation](https://docs.anthropic.com/en/docs/claude-code) |
| **OpenAI Codex** | OpenAI | [Codex CLI](https://github.com/openai/codex) |
| **Hugging Face Skills** | Hugging Face | [HF Skills Repository](https://github.com/huggingface/skills) |

> **Note:** The SKILL.md format has become a cross-platform standard. OpenAI Codex uses AGENTS.md but is compatible with SKILL.md, and Hugging Face has adopted the same format for their skills library.

## Installing Skills for Claude Code

### Prerequisites

- [Claude Code](https://claude.ai/code) installed and configured
- Git (for cloning skill repositories)

### Installation Methods

#### Method 1: Add as a Skill Directory (Recommended)

1. Clone this repository to a local directory:
   ```bash
   git clone https://github.com/kurrent-io/coding-agent-skills ~/skills/kurrentdb
   ```

2. Add the skill to Claude Code by adding it to your `~/.claude/settings.json`:
   ```json
   {
     "skills": [
       "~/skills/kurrentdb/kurrent_skills"
     ]
   }
   ```

3. Restart Claude Code or start a new session.

#### Method 2: Project-Level Skills

Add the skill to a specific project by creating a `.claude/skills` directory:

```bash
cd your-project
mkdir -p .claude/skills
cp -r /path/to/kurrentdb/kurrent_skills .claude/skills/kurrentdb
```

#### Method 3: Global Skills Directory

Copy the skill to Claude Code's global skills directory:

```bash
# macOS/Linux
cp -r /path/to/kurrentdb/kurrent_skills ~/.claude/skills/kurrentdb

# Windows
xcopy /E /I "C:\path\to\kurrentdb\kurrent_skills" "%USERPROFILE%\.claude\skills\kurrentdb"
```

## Installing Skills for OpenAI Codex

OpenAI Codex CLI supports skills through the AGENTS.md format, but also recognizes SKILL.md files.

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/kurrent-io/coding-agent-skills ~/skills/kurrentdb
   ```

2. Copy the skill to your project or reference it in your Codex configuration:
   ```bash
   # Copy to your project
   cp ~/skills/kurrentdb/kurrent_skills/SKILL.md ./AGENTS.md

   # Or symlink the reference
   ln -s ~/skills/kurrentdb/kurrent_skills/reference.md ./kurrentdb-reference.md
   ```

3. Codex will automatically discover and use the skill when working in that directory.

For more details, see: [Porting Skills to OpenAI Codex](https://blog.fsck.com/2025/10/27/skills-for-openai-codex/)

---

## Installing Skills for Hugging Face Agents

Hugging Face Skills use the same SKILL.md format and are compatible with smolagents and other HF agent tools.

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/kurrent-io/coding-agent-skills ~/skills/kurrentdb
   ```

2. Reference the skill in your agent configuration or copy to your project:
   ```bash
   # Copy skill folder to your project
   cp -r ~/skills/kurrentdb/kurrent_skills ./skills/kurrentdb
   ```

3. The skill will be available to Hugging Face agents working in that directory.

For more details, see: [Hugging Face Skills Repository](https://github.com/huggingface/skills)

---

### Checking if Skills are Available

After installation, you can verify the skill is loaded:

1. **Ask Claude Code directly:**
   ```
   What skills do you have available?
   ```
   or
   ```
   Do you have the KurrentDB skill installed?
   ```

2. **Test with a KurrentDB-specific question:**
   ```
   Generate a Python example that appends events to KurrentDB
   ```

   If the skill is loaded, Claude Code will use the accurate API from the skill reference rather than potentially outdated training data.

3. **Check the skill metadata:**
   ```
   Describe the KurrentDB skill capabilities
   ```

### Skill Structure

```
kurrentdb/
├── README.md                 # This file - installation guide
└── kurrent_skills/           # The actual skill content
    ├── SKILL.md              # Skill metadata and quick reference
    ├── reference.md          # Complete API reference (all languages)
    ├── templates/            # Ready-to-run project templates
        ├── docker-compose.yaml
        ├── python/
        ├── nodejs/
        ├── dotnet/
        ├── fsharp/
        ├── golang/
        ├── java/
        └── rust/
```

---

## Overview

This skill provides:

- **Complete API reference** for all 7 supported client languages
- **Best practices** demonstrating common patterns
- **Project templates** for quick bootstrapping
- **In-memory projection examples** for event-driven state building

## Supported Languages

| Language | Package | Version |
|----------|---------|---------|
| Python | `kurrentdbclient` | Latest |
| Node.js | `@kurrent/kurrentdb-client` | Latest |
| .NET/C# | `KurrentDB.Client` | Latest |
| F# | `KurrentDB.Client` | Latest |
| Java | `com.eventstore:db-client-java` | 5.4.1+ |
| Go | `github.com/kurrent-io/KurrentDB-Client-Go` | 1.0+ |
| Rust | `kurrentdb` | 1.0+ |

## Official Resources

- **Documentation:** https://docs.kurrent.io
- **Server Guide:** https://docs.kurrent.io/server/
- **Client SDKs:** https://docs.kurrent.io/clients/
- **GitHub:** https://github.com/kurrent-io

## License

This skill is provided for use with Claude Code. See individual client libraries for their respective licenses.
