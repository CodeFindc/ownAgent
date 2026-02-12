# Loguru Source Bedrock (Tier 3)

This tier provides the "Implementational Truth" by mapping high-level patterns to the actual source code extracted from the repository.

## Core Module: `loguru/_logger.py`
This is the heart of the library. It contains the primary `Logger` class.

| Symbol | Type | Line | Purpose |
| :--- | :--- | :--- | :--- |
| `Logger` | class | ~100 | The main class orchestrating all logging. |
| `add` | function | ~200 | Implementation of sink registration. |
| `catch` | function | ~600 | Logic for the exception-catching decorator. |

## Exception Formatting: `loguru/_better_exceptions.py`
Handles the "vibrant" exception reports that Loguru is famous for.

| Symbol | Type | Line | Purpose |
| :--- | :--- | :--- | :--- |
| `ExceptionFormatter` | class | ~126 | Formats stack traces into readable markdown/color output. |

## Async Support: `loguru/_asyncio_loop.py`
Contains the logic for handling asynchronous sinks.

*Note: Line numbers are indicative of the current Git version of `loguru` (`Delgan/loguru`).*
