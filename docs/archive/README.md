# Historical provenance

This directory retains frozen contract provenance, research protocols and prior
engineering certificates. Historical statements describe their original source
state; the current [repository health](../engineering/repository-health.md) records
corrections and the active implementation.

Redundant agent transcripts and handoffs were removed from the current tree.
[Documentation mapping](../../config/engineering/documentation-map.json) records
original paths, byte hashes and a Git recovery commit for each removed file:

```sh
git show <git_recovery_commit>:<git_recovery_path> > recovered.md
sha256sum recovered.md
```

Use a full clone for recovery. Retained contracts are in `delivery-records/`, and
prior engineering manifests are in `engineering/`. Archive aliases support historical
lookup; active Markdown must link to a literal current GitHub path.
