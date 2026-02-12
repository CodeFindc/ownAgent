---
name: loguru
description: Python logging made (stupidly) simple. Focuses on a single, global logger with progressive disclosure to deep source understanding.
version: 1.0.0
---

# Loguru: Simplified Python Logging

Loguru replaces the standard `logging` module with a more powerful, easier-to-use API. This skill provides the "Surface Layer" (Tier 1) for rapid onboarding.

## Quick Start

```python
from loguru import logger

# Add a sink (Tier 1: Basic Usage)
logger.add("file.log", rotation="500 MB")

# Log something
logger.info("That is it, beautiful and simple logging!")
```

## Core Patterns

| Feature | Pattern | Description |
| :--- | :--- | :--- |
| **Sinks** | `logger.add(sys.stderr, format="{time} {level} {message}")` | Configure where logs go. |
| **Levels** | `logger.debug("Debug msg")`, `logger.warning("Warn msg")` | Standard logging levels. |
| **Exceptions** | `@logger.catch` | Decorator to capture and log exceptions with full stack traces. |
| **Parsing** | `logger.parse(file)` | Extract structured data from log files. |

## Progressive Disclosure (The Iceberg)

For deeper understanding, "dive" into the following references:

- **[Core Concepts (Tier 2)](./references/core.md)**: Architectural purpose, Sinks, and Log Levels.
- **[Source Bedrock (Tier 3)](./references/source_map.md)**: Mapping patterns to the physical Python source code and AST nodes.
- **[Examples](./examples/)**: Complex usage scenarios verified against the sandbox.

