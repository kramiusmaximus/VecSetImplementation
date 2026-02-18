# Repository Guidelines

## Project Structure & Module Organization
- `app.py`: Gradio web UI for running VecSetEdit locally.
- `vecset_edit.py`: Main 3D mesh editing pipeline (CLI entry point).
- `preserving_texture_baking.py`: Optional texture repaint/baking pipeline.
- `vecset_edit_functions.py`: Core VecSetEdit helpers and rendering utilities.
- `custom_control/`, `triposg/`, `mvadapter/`: Model components and pipelines.
- `example/`, `assets/`: Sample inputs and media.
- `.runpod/`: RunPod serverless worker (`handler.py`), Docker build, hub config.

## Build, Test, and Development Commands
- `python app.py`  
  Launches the local web GUI on `http://localhost:7860`.
- `python vecset_edit.py --input_dir ... --output_dir ...`  
  Runs the core mesh edit pipeline.
- `python preserving_texture_baking.py --input_mesh ...`  
  Runs texture repaint/baking after editing.
- RunPod serverless build uses `.runpod/Dockerfile` and `.runpod/handler.py`.

## Coding Style & Naming Conventions
- Python code uses 4-space indentation and standard PEP8 naming.
- Prefer descriptive function names (`run_texture_repaint`, `attend_2d`).
- Keep new modules in the most specific directory (`custom_control/`, `triposg/`).

## Testing Guidelines
- No automated tests are defined in this repo.
- When adding new functionality, provide a minimal CLI example in `README.md`.
- If you add tests, document the command to run them.

## Commit & Pull Request Guidelines
- No strict commit convention is enforced. Use concise, imperative messages.
  Example: `Add RunPod serverless handler`.
- PRs should describe:
  - What changed and why
  - How to run or verify (commands or screenshots for UI changes)
  - Any new dependencies or model weights required
- Before opening a PR, ensure all intended files are added and committed.
  Example:
  - `git status -sb`
  - `git add <paths>`
  - `git commit -m "Describe change"`
- Push your branch after committing so remote CI and reviewers can access it.
  Example: `git push -u origin <branch>`

## Configuration & Assets
- Large weights should not be committed; store in `pretrained_weights/` or
  `checkpoints/` and document download links in `README.md`.
- RunPod serverless dependencies live in `.runpod/requirements_serverless.txt`.
