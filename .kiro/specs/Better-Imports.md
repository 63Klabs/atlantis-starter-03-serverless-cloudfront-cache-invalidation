A clean way to organize **Python Lambda + Layer** projects is to separate **infrastructure**, **function code**, **shared code**, and **tests**, while keeping imports identical **locally and in AWS**. Below is a structure that works well with CloudFormation, `pytest`, and Lambda Layers.

---

## Recommended Directory Structure

```
project-root/
├── template.yaml                  # CloudFormation / SAM template
├── template-configuration.json
│
├── layers/
│   └── common/
│       ├── python/
│       │   └── common/
│       │       ├── __init__.py
│       │       ├── utils.py
│       │       └── logging.py
│       └── requirements.txt       # layer dependencies
│
├── functions/
│   ├── function_one/
│   │   ├── app.py                 # Lambda handler
│   │   ├── __init__.py
│   │   └── requirements.txt
│   │
│   └── function_two/
│       ├── app.py
│       ├── __init__.py
│       └── requirements.txt
│
├── tests/
│   ├── unit/
│   │   ├── test_function_one.py
│   │   └── test_function_two.py
│   │
│   └── conftest.py
│
├── requirements-dev.txt           # pytest, moto, etc.
├── pyproject.toml                 # or setup.cfg (recommended)
└── README.md
```

---

## Key Design Principles

### 1. **Mirror Lambda’s Python Path**

AWS Lambda automatically adds:

* `/var/task` (function code)
* `/opt/python` (layer)

Your structure mirrors this by placing shared code under:

```
layers/common/python/common/
```

This allows **identical imports locally and in Lambda**.

---

### 2. **Shared Code via Lambda Layer**

Example: `layers/common/python/common/utils.py`

```python
def normalize_event(event):
    return event.get("detail", {})
```

Import it in **both functions** like this:

```python
from common.utils import normalize_event
```

✅ Works locally
✅ Works in Lambda
❌ No relative import hacks

---

### 3. **Lambda Handlers Stay Simple**

`functions/function_one/app.py`

```python
from common.utils import normalize_event

def handler(event, context):
    data = normalize_event(event)
    return {"statusCode": 200, "body": data}
```

CloudFormation:

```yaml
FunctionOne:
  Type: AWS::Lambda::Function
  Properties:
    Handler: app.handler
    CodeUri: functions/function-one/
    Layers:
      - !Ref CommonLayer
```

---

### 4. **Local Unit Testing Without Import Pain**

Add the layer path during tests.

`tests/conftest.py`

```python
import sys
from pathlib import Path

layer_path = Path(__file__).parent.parent / "layers" / "common" / "python"
sys.path.insert(0, str(layer_path))
```

Now pytest works normally:

```python
from src.function_one.app import handler
```

Run tests:

```bash
pytest
```

---

### 5. **Packaging for Deployment**

**Function zip**

```
function-one.zip
└── app.py
```

**Layer zip**

```
common-layer.zip
└── python/
    └── common/
        └── utils.py
```

This exactly matches Lambda’s runtime expectations.

---

## CloudFormation Layer Definition

```yaml
CommonLayer:
  Type: AWS::Lambda::LayerVersion
  Properties:
    LayerName: common-python
    CompatibleRuntimes:
      - python3.14
    ContentUri: layers/common/
```

---

## Why This Works Well (Especially for You)

Given your background with **CloudFormation-first workflows** and **multi-function stacks**:

* ✅ No SAM-specific lock-in
* ✅ Works with CI/CD and linting
* ✅ Easy to add more functions
* ✅ Layer stays clean and reusable
* ✅ Imports behave the same locally and in AWS

This is very close to how larger platform teams structure Lambda repos.

---

## Optional Enhancements

If you want to go one step further:

* Use `pyproject.toml` to define `common` as an editable package locally
