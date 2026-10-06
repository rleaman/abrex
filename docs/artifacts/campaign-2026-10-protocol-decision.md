# Milestone C protocol decision

Decision status: **awaiting user approval**

## Recommended disposition

Approve the narrowed confirmatory protocol as prepared:

- 48 representative article groups with paired PMC prose and PubMed abstract
  passages, plus 24 disjoint structural-challenge groups;
- 72 groups and 120 passages total, with an estimated 8–12 hours of primary
  prediction-blind review;
- five confirmatory methods: native-offset Ab3P, Schwartz–Hearst, PLODv2
  pairing, complete CLP V5.1, and Jev candidate judging;
- direct extraction retained as negative development evidence only, with no
  additional Azure requests;
- strict exact-pair F1 on the representative component as the primary endpoint;
- one primary contrast, complete CLP V5.1 versus Schwartz–Hearst;
- superiority only when the absolute F1 gain is at least 0.05 and the paired
  article-group-bootstrap 95% interval excludes zero;
- the structural challenge reported separately and never pooled into the
  representative estimate.

## Evidence behind the recommendation

The new draw excludes 238 PMIDs, 83 PMCIDs, known CLP overlap, and every linked
development identity. T067 is already exposed and too group-concentrated for
confirmation. The direct extractor failed three predeclared gates and therefore
does not justify adding a second model-based primary contrast. Keeping one
primary contrast avoids post-result endpoint choice and removes the need for a
multiple-comparison correction.

The source-only reviewer and disposable save/resume/lock flow are already
browser-tested. The actual frozen packet will be tested again before it is
delivered for annotation.

## What approval authorizes

Approval authorizes the campaign owner to acquire and freeze the source-only
sample, build the sidecar carrying ordered passages and raw table XML, and
deliver the tested prediction-blind review packet. It does not authorize:

- any TypeSafe scientific-data request or spend;
- any resolver prediction run;
- unlocking annotations or exposing predictions to reviewers;
- additional Azure OpenAI requests.

After the sample and rules-only CLP dry run are complete, the owner will present
the exact TypeSafe request count, passages, and hard cost cap for separate
authorization. Ab3P and PLODv2 execution will use the documented portable Linux
bundle because this Windows host has no installed WSL distribution.

## Minimal response

To accept this recommendation, reply:

> Approve the Milestone C protocol as prepared.

If you want a scientific change, identify only the field to change (sample
size, method set, review burden, primary contrast, or success threshold). All
clerical freeze, acquisition, packet construction, and validation work remains
with the campaign owner.
