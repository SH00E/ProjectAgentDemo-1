import os
import json
import random

_prompts = None

def _load_prompts():
    global _prompts
    if _prompts is not None:
        return _prompts
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts.json")
    with open(path, "r", encoding="utf-8") as f:
        _prompts = json.load(f)
    return _prompts

def get_prompt(*keys):
    prompts = _load_prompts()
    val = prompts
    for k in keys:
        val = val[k]
    return val

def fmt_prompt(section, key, **kwargs):
    template = get_prompt(section, key)
    safe_kwargs = {}
    for k, v in kwargs.items():
        if isinstance(v, str):
            safe_kwargs[k] = v.replace('{', '{{').replace('}', '}}')
        else:
            safe_kwargs[k] = v
    return template.format(**safe_kwargs)

def random_reduce_count(count):
    if count <= 0:
        return 0
    reduction = random.uniform(0.05, 0.10)
    reduced = count * (1 - reduction)
    result = int(reduced)
    if result <= 0:
        result = max(1, count - 1)
    if result >= count:
        result = count - 1
    return result
