# Physics Bank Agent Architecture

## Scope

This repository packages the question-bank production and independent-review part of the Pocket Cosmos multi-agent design. `skills/physics-bank-agent-loop/SKILL.md` and the role profiles are the operational contract. The bundled `skills/physics-bank/` directory is the Creator's required production skill and is pinned here as a complete snapshot (`3.0.0-rc.1`).

## Roles

### Coordinator

The Main Agent owns the user's scope, source paths, output location, and handoff order. It coordinates the Creator and Reviewer sequentially, forwards only the evidence needed for a repair round, and reports acceptance only after the independent review and required mechanical validation both pass. It never lets the two agents write the same bank at the same time.

### Question Creator

The Creator is the only role that creates or repairs bank files. It follows the user's scope and the bundled Physics Bank skill, preserves source evidence, applies only scoped and evidence-backed findings, records changes, and runs the validators required by that skill. It reports changes, validator results, and unresolved evidence gaps to the Coordinator. It does not issue the final acceptance verdict.

### Question Reviewer

The Reviewer is independent and read-only. On the first pass, it receives the user's request, source material, and bank, but not the Creator's conclusions or proposed fixes. It checks the bank against the source PDFs, manifests, schema, authoritative taxonomy, answer data, asset files, and validator reports. It distinguishes confirmed defects, false positives, and evidence gaps.

The Reviewer returns `ACCEPT` or `REVISE`, with evidence for each finding. It may issue `ACCEPT` only when the request is met, required mechanical validation passes, and no blocking or inconclusive finding remains. On re-review, it checks every prior finding and inspects nearby changes for regressions.

## Handoff cycle

1. The Coordinator gives the Creator the task, source paths, destination, and explicit scope. For review-only requests, skip creation.
2. After creation, the Coordinator sends the bank and source context to the Reviewer. The first review is independent of the Creator's summary.
3. If the Reviewer returns `REVISE`, the Coordinator sends the scoped findings and evidence to the Creator.
4. The Creator repairs only supported findings, records the change log, and reruns relevant validators.
5. The Reviewer independently checks all prior findings and regressions. Repeat serially until acceptance, or stop after five repair rounds and report remaining issues.

Uncertainty remains `INCONCLUSIVE`; it is never silently treated as acceptance. Source ambiguity is preserved as an explicit limitation rather than guessed away.

## Acceptance gate

The Coordinator may report the bank accepted only when all of the following hold:

- The Reviewer returns `ACCEPT`.
- Every required validator passes.
- No blocking or inconclusive finding remains.
- The result still satisfies the user's original scope, including any question-range limit.

The Reviewer never edits bank files. The Creator never approves its own work. The Coordinator owns sequencing and final reporting.

## Included skill dependency

The Creator calls `$physics-bank`. Its extraction, answer handling, visual asset review, taxonomy, difficulty, schema, and validation rules live in `skills/physics-bank/`. That directory is included rather than relying on a separate local installation, so this repository contains the exact skill dependency needed by the architecture. The nested publisher skill is included as part of that complete snapshot; publishing is not part of the Creator/Reviewer acceptance decision.
