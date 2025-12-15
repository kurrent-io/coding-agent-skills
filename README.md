# KurrentDB Skill for Coding Agents

A comprehensive skill that enables AI coding agents to generate code for [KurrentDB](https://kurrent.io) (formerly EventStoreDB) - the event-native database. 
Benchmarks have shown around 50% less token usage and 3x faster code generation compared to generating code without the skill.

## Supported Coding Agents

This skill is compatible with multiple AI coding agents that support the SKILL.md format:

| Agent | Platform | Skill Docs |
|-------|----------|------------|
| **Claude Code** | Anthropic | [Skills Documentation](https://docs.anthropic.com/en/docs/claude-code) |
| **OpenAI Codex** | OpenAI | [Codex CLI](https://github.com/openai/codex) |

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

## Verifying Skill Installation

After installation, verify the skill is working with any of these methods:

1. **Ask your agent directly:**
   ```
   What skills do you have available?
   ```
   or
   ```
   Do you have the KurrentDB skill installed?
   ```

2. **Test with a KurrentDB-specific task:**
   ```
   Generate a Python example that appends events to KurrentDB
   ```
   If the skill is loaded, the agent will use the accurate API from the skill reference rather than potentially outdated training data.

3. **Check for correct API usage:**
   - Stream names should use `order-{id}` format (not `orders` collection)
   - Should use `append_to_stream()` not generic database writes
   - Event types should be properly structured with type names and JSON data

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
