# F1 Independent Validation V1 selection and Human Review trace

This freezes one candidate and one control before any Validation performance
access. Source result commit: `91b89a97a9a2b54e133d2979c695d7c3da22626e`;
source handoff: `e388fdce6d846019b854704a1967ca0a6b12afd6`; implementation:
`fb207b8b868a3aaceed568d4a8e1b62340371bff`; preregistration:
`95e54ee6461b315b51f5ca7cc17cd985caa96a1d`; preregistration handoff:
`d28e42bf7bb09fcc5b9faa19ab3ff0a96429c1cd`. Component Replacement semantic
protocol hash: `4267d73f38fc8353002459b24640148cc49c4e5777b364eb14ca84404aef9fa7`.

The formal first/rerun metadata and all 21 content files in each run were
SHA-verified. Their summaries agree:

| Source scheme | Weighted RankIC | Weighted Spread | Formal status |
|---|---:|---:|---|
| F0_CONTROL | 0.08810651455546813 | 0.037216498377093545 | CONTROL_NOT_A_CANDIDATE |
| F1_H10_REPLACEMENT | 0.09349328088119589 | 0.044456330026128345 | FUSION_ADVANCED_FOR_FURTHER_REVIEW |
| F2_H10_H40_REPLACEMENT | 0.09486741148701808 | 0.015939832916397074 | FUSION_NOT_ADVANCED |

F1 improves both primary Development metrics: deltas +0.005386766325727765
and +0.0072398316490348. F2's higher RankIC does not waive its spread
deterioration. Formal next gate is H10_REPLACEMENT_ONLY_SUPPORTED. Human
Review authorizes only F1, renamed V1_F1_CANDIDATE, against V0_CONTROL.
No F2, H40 replacement, H120 replacement, new or backup candidate is admitted.
Development has been repeatedly reused; its estimates are selection-sensitive
and are not independent confirmation or OOS evidence. The late Development
block weakness and H40 evidence caveats remain disclosed.

Previous attempt stopped at VALIDATION_PURGE_TRAINING_SEMANTICS_BLOCKER,
with no edit/commit or Validation/OOS access. Human Review now distinguishes
evaluation eligibility from training-source eligibility:

- Purge1 is never evaluable; it is conditionally training-eligible after the
  corresponding horizon label legally matures, within the existing rolling
  window, as-of cutoff, minimum-data, feature/target validity rules.
- Validation is FROZEN_ALGORITHM_WALK_FORWARD. Each signal refits the frozen
  algorithm on its chronological information set. Earlier Validation origins
  can train later signals after maturity, without research-design adaptation.
- Existing `label_end <= current_signal_date` after-close semantics remain
  authoritative; observation origins must be strictly earlier than the signal.
- Purge2 evaluation is excluded. Its future Final OOS training admission is
  undecided and must be frozen in a separate Final OOS preregistration.

BLOCKER_RESOLVED_BEFORE_VALIDATION_OPEN=true. This Human Review settles
phase-level admission only. Historical Development protocols, label-window
inequalities, factors, model, target, fusion and decision gates are unchanged.
Independent Validation means the design is frozen before its first performance
view, then evaluated chronologically; it does not mean a static train-once fit.

This trace authorizes preregistration only. No actual Validation training set,
label-maturity check, model, prediction or result is generated here. Final OOS
remains SEALED. Opening requires a separate explicit Human Review instruction.
