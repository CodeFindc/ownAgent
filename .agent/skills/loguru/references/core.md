# Loguru Core Concepts (Tier 2)

This tier provides the "Core" documentation acquired from CodeWiki and official vignettes.

## The Global Logger
Loguru revolves around a single `logger` object. This simplifies configuration by avoiding the need for `getLogger(__name__)`.

## Sinks and Handlers
A "sink" is any object that receives log messages.
- Files (with rotation and retention)
- Standard Output/Error
- Custom callables
- Coroutines (async support)

## The Catch Decorator
The `catch()` method is a powerful way to ensure that any unexpected error is properly logged before the application crashes.

```python
@logger.catch
def my_function(x, y):
    return x / y
```

*For implementational truth, see the source mapping in [Source Bedrock](./source_map.md).*
