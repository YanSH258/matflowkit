# TCCKit DPA4 commands

Read this reference when choosing a command, constructing inputs, predicting outputs, resuming work, or interpreting exit codes. Confirm details against `tck dpa4 COMMAND -h` in the active checkout.

## `relax`

```bash
tck dpa4 relax INPUT
```

Use for one ASE-readable structure. Defaults: fixed cell, BFGS, `fmax=0.05 eV/Å`, 300 steps, and DPA4 + PBE-D3(BJ).

Important options:

- `--output/-o`: output structure path
- `--model`: model path
- `--fmax`: optimizer force threshold
- `--steps`: maximum steps
- `--optimizer`: `bfgs`, `lbfgs`, or `fire`
- `--fixed-cell/--relax-cell`: atomic-only or variable-cell optimization
- `--fix-indices-file`: whitespace-separated one-based atom indices
- `--d3/--no-d3`: include or exclude PBE-D3(BJ)

Default outputs sit beside the input:

- `STEM_dpa4_relaxed.extxyz`
- `STEM_dpa4_relaxed.log`
- `STEM_dpa4_relaxed_trajectory.extxyz`
- `STEM_dpa4_relaxed_status.json`

Require `status = PASS`, `converged = true`, and `final_optimizer_fmax_eV_A <= fmax_target_eV_A`. For variable-cell optimization, use optimizer forces rather than atomic forces alone to judge convergence.

## `batch-relax`

```bash
tck dpa4 batch-relax structures.csv
```

Require an `input` column; accept an optional `id` column. Resolve relative input paths from the manifest directory. Sanitize IDs to safe path components and reject duplicates.

Defaults: output directory `dpa4_batch_relax`, fixed cell, BFGS, `fmax=0.05 eV/Å`, 300 steps, and D3 enabled.

Behavior:

- Skip prior `PASS` tasks.
- Skip prior `ERROR` and `NOT_CONVERGED` tasks unless `--retry-failed` is set.
- With `--retry-failed`, remove only the known output files generated for those tasks and rerun them.
- Update `batch_status.csv` after every attempted task.
- Write `batch_summary.json` at the end.
- With `--strict`, return exit code 2 when any manifest task is not `PASS`.

Use `--strict` in automation. Report task counts by status, not only the process exit code.

The current interactive menu asks for the manifest, output directory, and model path. It does not expose `--retry-failed` or `--strict`. After an interrupted or failed run, use a short explicit recovery command from the directory containing the manifest:

```bash
tck dpa4 batch-relax structures.csv --retry-failed --strict
```

Keep the same manifest and output directory. Do not omit the manifest path unless it is actually named `structures.csv` in the current directory.

## `evaluate`

```bash
tck dpa4 evaluate INPUT
```

Use for single-point prediction on one or more ASE-readable frames. The default ASE index `:` reads every frame. Use `--index` for an explicit selection.

Defaults: energy and atomic forces with D3 enabled. Add `--stress` to request six-component Voigt stress.

Outputs:

- `STEM_dpa4_evaluated.extxyz`: predicted labels
- `STEM_dpa4_evaluated_metrics.csv`: per-frame formula, atom count, energy per atom, force-component RMS/MAE, and maximum atomic force
- `STEM_dpa4_evaluated_summary.json`: model, calculator, frame count, ranges, and paths

The output labels are DPA4 predictions. Keep them separate from DFT labels unless a later workflow clearly marks their origin.

## `neb`

```bash
tck dpa4 neb INITIAL FINAL
```

Require separately optimized endpoints with identical atom count, element order, cell within tolerance, and PBC. Defaults: five intermediate images, IDPP interpolation, ordinary ASE NEB to `0.10 eV/Å`, then CI-NEB to `0.05 eV/Å` when the ordinary NEB converges and the maximum is internal.

Important options:

- `--output-dir/-o`: empty or nonexistent output directory
- `--images`: number of intermediate images
- `--fix-indices-file`: one-based indices applied to every image
- `--neb-fmax`, `--ci-fmax`: stage thresholds
- `--neb-steps`, `--ci-steps`: stage limits
- `--climb/--no-climb`: enable or disable the CI stage
- `--d3/--no-d3`: calculator identity

Key outputs:

- `interpolated_images.extxyz`
- `neb_images.extxyz`
- `ci_neb_images.extxyz` when attempted
- `neb_fire.log` and optionally `ci_neb_fire.log`
- `energy_profile.csv`
- `highest_energy_image.extxyz`
- `status.json`

Interpret statuses exactly:

- `PASS_CI_NEB`: both stages converged
- `PASS_NEB`: ordinary NEB converged and climbing was disabled
- `PASS_NEB_ENDPOINT_MAXIMUM`: ordinary NEB converged but the path maximum is an endpoint; do not call it a transition state
- `INCOMPLETE_CI_NEB`: ordinary NEB converged but CI-NEB did not
- `INCOMPLETE_NEB`: ordinary NEB did not converge

Incomplete statuses return exit code 2. A `PASS_NEB_ENDPOINT_MAXIMUM` process succeeds computationally but does not establish an internal barrier.
