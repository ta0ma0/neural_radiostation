# AGENTS.md

## Overview
This repository contains a Python‑based music DJ application with a small supporting web‑socket service. The file below provides **build, lint, and test commands** as well as **code‑style guidelines** for agents that will work on this codebase.

---

## 1️⃣ Build / Run Commands

| Action | Command | Description |
|--------|---------|-------------|
| **Create virtual environment** | `python -m venv venv && source venv/bin/activate` | Isolate dependencies. |
| **Install dependencies** | `pip install -r requirements.txt` | Installs Python packages listed in `requirements.txt`. |
| **Run the DJ app** | `python -m dj_alyx.play_music` | Starts the main music player. |
| **Start the web‑socket service** (Docker) | ```bash\ncd django-aws-terminal-websocket\n docker compose up --build\n``` | Spins up the Docker containers defined in `docker-compose.yml`. |
| **Run a single test** | `pytest path/to/test_file.py::test_name` | Executes a specific pytest test. If `pytest` is not installed, add it to `requirements.txt` (e.g., `pytest`). |
| **Run all tests** | `pytest` | Discovers and runs all tests in the repository. |
| **Lint** | `ruff check .` | Lints the Python code using **ruff** (add to requirements if desired). |
| **Format** | `ruff format .` | Auto‑formats code using **ruff** (or `black`). |

*If a tool like `ruff` or `pytest` is missing, simply install it with `pip install ruff pytest`. The commands above assume the virtual environment is active.*

---

## 2️⃣ Code‑Style Guidelines

> These rules are enforced by the agents (and any CI you add). They are intentionally strict to keep the codebase uniform.

### 📦 Imports
- **Standard library imports** first, then **third‑party**, then **local** imports.
- Separate each group with a single blank line.
- Use absolute imports for local modules (e.g., `from dj_alyx.voice_engine import VoiceEngine`).
- Sort imports alphabetically within each group (e.g., `import os`, `import sys`).
- No wildcard imports (`from module import *`).

### 🧹 Formatting
- Use **ruff** or **black** with a line length of **88** characters.
- Indentation: **4 spaces**, no tabs.
- Trailing whitespace is prohibited.
- End files with a single newline.

### 🏷️ Naming Conventions
| Entity | Convention |
|--------|------------|
| Modules / packages | **snake_case** (`dj_alyx`, `voice_engine`) |
| Classes | **PascalCase** (`VoiceEngine`) |
| Functions / methods | **snake_case** (`process_audio`) |
| Constants | **UPPER_SNAKE_CASE** (`DEFAULT_VOLUME`) |
| Variables | **snake_case** (`audio_buffer`) |
| Private members | prefix with a single underscore (`_helper`) |
| Protected members | double underscore (`__internal`) |

### 📄 Types & Annotations
- All public functions and methods must have **type hints** for parameters and return values.
- Use `typing` constructs (`List`, `Dict`, `Optional`, `Union`, `Literal`, etc.) where appropriate.
- For complex data structures, define `TypedDict` or `Protocol`.
- When returning `None`, explicitly annotate as `-> None`.
- Example:
  ```python
  def get_track_duration(path: Path) -> float:
      ...
  ```

### ❗ Error Handling
- Prefer **exceptions** over error‑code returns.
- Raise built‑in exceptions (`ValueError`, `FileNotFoundError`, etc.) or custom ones derived from `Exception`.
- Catch only the exceptions you can meaningfully handle; re‑raise otherwise.
- Include a helpful error message; never expose raw traces to end‑users.
- Use context managers (`with` statements) for resource cleanup.

### 🧪 Testing
- Place tests in a `tests/` directory mirroring the package layout.
- Use **pytest** as the test runner.
- Write **unit tests** for pure functions and **integration tests** for I/O.
- Name test functions `test_<behaviour>` and keep them **self‑contained**.
- Use fixtures for reusable setup/teardown logic.
- Aim for **≥80 % coverage**; use `coverage run -m pytest && coverage report` to check.

### 📦 Dependency Management
- Pin exact versions in `requirements.txt` for reproducibility.
- Add new packages with `pip freeze > requirements.txt` after confirming they work.
- Avoid unnecessary dependencies; prefer the Python standard library when possible.

### 📜 Documentation
- Every public module, class, and function must have a **docstring** in *Google* style.
- Keep docstrings concise but include:
  - Brief description.
  - Args (type and description).
  - Returns (type and description).
  - Raises (exception types).
- Example:
  ```python
  def load_track(path: Path) -> AudioSegment:
      """Load an audio file.

      Args:
          path: Path to the audio file.

      Returns:
          An ``AudioSegment`` instance containing the audio data.

      Raises:
          FileNotFoundError: If ``path`` does not exist.
      """
      ...
  ```

### 🗂️ Project Structure
```
├─ dj_alyx/                 # core Python package
│   ├─ __init__.py
│   ├─ play_music.py
│   ├─ voice_engine.py
│   └─ …
├─ django-aws-terminal-websocket/  # auxiliary web‑socket service
│   ├─ Dockerfile
│   ├─ docker-compose.yml
│   └─ …
├─ tests/                   # pytest test suite
│   ├─ test_play_music.py
│   └─ …
├─ requirements.txt
├─ .env                     # local environment variables (not committed)
├─ AGENTS.md                # **THIS** file
└─ README.md
```

### 📜 Cursor / Copilot Rules (if present)
- No **.cursor** directory exists, so there are no custom cursor rules.
- No **.github/copilot‑instructions.md** file is present, therefore no special Copilot guidance applies.

---

## 3️⃣ How Agents Should Use This File
1. **Read** this file at the start of any task to understand the expected command set and style.
2. **Run** the appropriate command from the table when building, linting, or testing.
3. **Validate** code against the style rules before committing:
   - Run `ruff check . && ruff format .` (or `black .`).
   - Ensure type hints and docstrings are present.
4. **When adding new code**, follow the naming, import, and documentation conventions **exactly**.
5. **If a new dependency is required**, add it to `requirements.txt` and update the version pinning.

---

*Generated by the autonomous AGENT assistant on 2026‑04‑17.*
