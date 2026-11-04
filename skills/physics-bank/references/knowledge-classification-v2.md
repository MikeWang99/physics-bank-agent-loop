# Physics Bank knowledge classification v2 · v3.0 candidate

## Authority, sync and semantics

Website authority: MikeWang99/pocket-cosmos-online,
src/data/pocket_cosmos_physics_taxonomy_v1.json, pinned by
references/knowledge-taxonomy.lock.json. The site currently labels this taxonomy
1.0.0-draft and contains 936 nodes. Node UID is the durable identity; human
numbered codes and bilingual paths are display-only. Copy it **without edits**
using scripts/sync_knowledge_taxonomy.py. Any blob/version mismatch fails.

Question canonical tuple: stable question ID + source_system + (source_event
when needed) + exactly one primary_knowledge_uid for reviewed questions +
unaltered full TIMBAD v1.0 difficulty audit. V2 questions have no authority from
the per-bank curriculum unit/topic/subtopic or free-text specialty classifications.
User-owned classroom/homework/high-value/custom tags remain independent.

## Process before a reviewed UID may be published

1. Verify complete PDF text, context, choices, math, diagrams, source answer,
   figure provenance, narrative order and image review. Missing source conditions
   stop classification.
2. Independently solve. Record concise required_concepts, solution_summary and
   latest_required_reason. Do not expose hidden reasoning or store an unsupported
   claim of physics correctness.
3. Search a small number of **real** candidate nodes in the full taxonomy using
   search_knowledge_nodes.py. Explore more specific siblings and later integrated
   chapters; lexical retrieval only identifies candidates.
4. Compare candidates by physical target, all indispensable laws/steps, highest
   necessary prerequisite, later integrated node, specificity and false keyword
   matches. Write a concise selected/excluded decision with reasons.
5. A fresh independent pass explicitly seeks a counterexample, missing later
   prerequisite or better integrated node. Record initial and independent UIDs,
   agreement, reviewer method, cross_chapter_checked and evidence. A person must
   resolve disagreement or uncertainty before status reviewed.
6. If no correct existing node, classify needs_review with reason and candidate
   nodes, and optionally a suggestion for a *separately reviewed* taxonomy
   extension. Do not auto-create a UID, force Other, or silently place at basic
   Circular Motion when Energy/Momentum are required.

Audit: keep classification-review.json containing per-question UID, bilingual
display info (resolved from taxonomy), candidates, excluded reasons,
cross-chapter evidence, reviewer agreement, confidence, status, issues,
taxonomy version and SHA-256. The report is audit output and is NOT a tag list.

Confidence is not accuracy. To measure actual performance collect
educator-confirmed gold questions across Circular Motion, Energy, Momentum,
friction, pulleys, rotational motion, potential, capacitors, induction, thermal
and BPhO/F=ma constraint problems. Report coverage, accuracy among auto
assignments, accuracy over all questions, integrated-problem accuracy, source
breakdown, manual review, rejection, and error examples. Never claim a numeric
accuracy without real gold labels.

## Minimal canonical example

The sample below is a shape illustration. A real run MUST replace the
placeholder UID with a checked record from the pinned taxonomy, the taxonomy
SHA-256 with the verified digest, and the illustrative TIMBAD fragment with
the **complete unmodified v2.9 TIMBAD audit including T/I/M/B/A/D evidence,
overall/boundary reasons, status, bottlenecks, solution outline, etc.**:

    {
      "id": "stable-original-id",
      "source_system": "competition",
      "source_event": "fma",
      "classification": {
        "schema": "physics-question-classification/v2",
        "primary_knowledge_uid": "<real UID from locked taxonomy>",
        "status": "proposed",
        "confidence": 0.8,
        "taxonomy": {"version": "1.0.0-draft", "sha256": "<SHA256 bytes>"},
        "physics_analysis": {
          "required_concepts": ["energy conservation", "centripetal force"],
          "solution_summary": "Find speed from energy, then net radial force.",
          "latest_required_reason": "Energy is necessary before radial equation."
        },
        "candidates": [
          {"uid":"<same real UID>", "decision":"selected", "reason":"Covers the complete route"}
        ],
        "review": {
          "reviewed": false, "method": "second-physics-pass",
          "initial_uid": null, "independent_uid": null,
          "agreement": false, "cross_chapter_checked": false
        },
        "difficulty": { "...": "FULL Pocket Cosmos TIMBAD v1.0 object here" }
      }
    }

A nonfinal proposal may have primary_knowledge_uid null and
status needs_review. It cannot pass strict publication. For strict publication,
candidate comparison + independent review + the complete APPROVED TIMBAD audit
must pass scripts/validate_knowledge_classification.py.

## Compatibility / migration / rollback

v1 classification-taxonomy.json and class/v1 validator remain supported; do not
map arbitrary old IDs to real UIDs, remap old 1–5 difficulty numbers to TIMBAD
levels, rewrite stable question IDs, update old student attempts or erase
question_versions. Review and migrate v1 questions one by one using validated
UIDs and the already-approved source data. Preserve source years even though
v2 does not require year. Old generated labels are read for legacy display but
are not re-emitted for new v2 banks.

Publisher emits the same Practice question identity and a new immutable version
only where existing transaction rules deem the published content changed;
metadata.physicsBank holds full TIMBAD evidence and classification; runtime
step stores approved level, sourceSystem and primaryKnowledgeUid. Topic Practice
queries the UID on the SAME question; it does not duplicate a question.

Rollback: leave both original main branches and production data unchanged,
revert the feature PR/commit if tests fail, and stop v2 publication rather
than retroactively deleting valid v1 versions. Before any rollout, verify
latest-version resolution, Practice, teacher review, homework, wrong answers,
source refs, PDFs and assets against a disposable preview Supabase environment.

### Limitations

The taxonomy is still Draft and does NOT provide a verified per-topic
prerequisite DAG. The candidate script is lexical discovery; actual physical
classification and independent physics review are semantic model/human steps.
CI tests deterministic validation, not true classification accuracy.
