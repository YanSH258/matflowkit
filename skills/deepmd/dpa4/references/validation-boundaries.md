# Validation boundaries

Read this reference before making scientific claims from DPA4 relaxation, single-point prediction, or NEB results.

## Separate calculator success from scientific validity

Use the following evidence ladder:

1. **Load check:** dependencies import and the model loads.
2. **Smoke check:** one representative structure produces finite energy and forces.
3. **Workflow check:** expected files, status fields, frame counts, constraints, and thresholds are correct.
4. **Numerical convergence:** the optimizer or NEB stage meets its stated criterion.
5. **Domain check:** structures remain chemically and geometrically plausible and are not obvious extrapolations.
6. **Reference check:** representative results agree with independent DFT calculations at the level required by the research question.

Do not skip directly from level 1–4 to a claim of DFT accuracy.

## Structure relaxation

- Report fixed-cell versus variable-cell and all fixed atoms.
- Inspect the final geometry and trajectory, not only the final energy.
- Check for atom overlap, dissociation, unintended reactions, large cell changes, or atoms crossing constrained regions.
- Compare the same calculator definition across candidates. DPA4 and DPA4 + D3 energies are not interchangeable.
- For ranking structures with different compositions, do not compare raw total energies without a defined thermodynamic reference.

## Single-point prediction

- Preserve frame identifiers and the source trajectory.
- When evaluating selected frames, record the mapping from output order to the original frame indices; do not assume a renumbered `frame` field is the source trajectory index.
- Report energy per atom only when it answers the comparison; retain total energy as evidence.
- Treat force statistics as model outputs, not error metrics, unless DFT reference forces exist for the same frames.
- Treat requested stress as a prediction with explicit units and sign convention. Do not silently rename stress to virial.
- Do not mix predicted labels into the canonical DFT training set without provenance fields or a separate dataset boundary.

## NEB and barriers

- Optimize endpoints with the same calculator and compatible constraints before interpolation.
- Inspect for atom mapping errors, periodic jumps, and implausible intermediate bonds.
- Require an internal maximum before calling an image a transition-state candidate.
- Require CI-NEB convergence before presenting the default result as a converged climbing-image barrier.
- State that MatFlowKit reports a DPA4 minimum-energy path. Validate key endpoints and the highest-energy region with DFT before making a DFT barrier claim.
- Remember that NEB identifies a path under the supplied endpoint mapping and constraints; it does not prove that no lower path exists.

## Reporting language

Use precise statements such as:

- “The MatFlowKit DPA4 + PBE-D3(BJ) relaxation reached `fmax < 0.05 eV/Å`.”
- “The DPA4 CI-NEB stage converged and produced a model-predicted forward barrier of X eV.”
- “DFT validation has not yet been performed.”

Avoid statements such as:

- “The DFT structure is converged” when only DPA4 was run.
- “The barrier is validated” when only the ordinary NEB stage converged.
- “The dataset error is low” when only predicted force magnitudes were calculated.
