# Physics Bank Agent Loop

A reusable Creator → independent Reviewer workflow for building and repairing physics question banks. The repository packages the architecture, its Codex skill and role profiles, and the Physics Bank skill that the Creator must follow.

## What is included

- `skills/physics-bank-agent-loop/`: coordinator workflow, Creator and Reviewer role profiles, and Codex metadata.
- `skills/physics-bank/`: the complete Physics Bank skill snapshot used by the workflow (version `3.0.0-rc.2`), including its references, scripts, validators, tests, and nested publisher skill.
- `ARCHITECTURE.md`: roles, handoff sequence, review contract, and acceptance gate.
- `install_to_codex.py`: installs both skills and the role profiles into the current Codex home.

The workflow does not treat a Creator's self-review as independent acceptance. The Reviewer stays read-only, and the Coordinator keeps creation and review serial so both roles never edit the same bank at once.

## Install

Requires Python 3.10 or newer. Install the bundled skill dependencies with:

```bash
python3 -m pip install -r skills/physics-bank/requirements.txt
python3 install_to_codex.py
```

The installer targets `~/.codex` by default. Set `CODEX_HOME` to use another Codex home. It will refuse to overwrite an installed file whose contents differ; resolve that difference explicitly before retrying.

After installation, invoke `$physics-bank-agent-loop` for a bank task that requires independent review. The Creator uses `$physics-bank`; the Coordinator hands the completed bank to the read-only Reviewer and applies the review gate documented in `ARCHITECTURE.md`.

## Updating the bundled Physics Bank skill

The bundled skill is a versioned snapshot. When updating it, copy the complete skill directory, update the version noted above, and review the change against the upstream `physics-bank` repository before release.


## Post-acceptance delivery extension

The original high-quality source extraction/asset review and independent Creator/Reviewer loop remain unchanged. The optional new delivery phase can generate standardized reviewed student answers, compile per question, quarantine incompatible items without blocking valid questions, and pass the ready subset to the **already existing** Pocket Cosmos production publisher API. See \`skills/physics-bank-agent-loop/references/post-acceptance-delivery.md\` and \`skills/physics-bank-agent-loop/scripts/delivery.py\`.

This first-stage change is **not** a direct PDF/DOCX/image upload web endpoint or a completed online high-priority review queue. Those website-facing endpoints, plus v2/TIMBAD cloud editing, remain follow-on integration work. Publish defaults to preflight; only \`--apply\` makes production writes.
