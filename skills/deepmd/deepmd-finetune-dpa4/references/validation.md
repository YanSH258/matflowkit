# DPA4 Fine-tuning: Validation and Runtime Compatibility

## Contents

1. Validation hierarchy
2. Direct checkpoint testing
3. Frozen DPA4/SeZM artifacts
4. Metrics and energy offsets
5. Mechanics validation
6. Model card and acceptance decision

## 1. Validation hierarchy

Keep these claims separate:

```text
training process completed
checkpoint loads
held-out numerical errors are acceptable
unseen configuration families transfer
target physics is reproduced
deployment runtime is stable
```

A model is not production-ready merely because the final training loss is low.

Recommended test layers:

1. one production-size held-out frame;
2. all held-out frames, grouped by composition/system;
3. unseen trajectories or mother configurations;
4. target observables such as relaxation convergence, stress-strain, elastic constants, MD
   stability, or diffusion;
5. frozen-artifact test in the actual deployment runtime.

## 2. Direct checkpoint testing

Test the training checkpoint before export:

```bash
dp --pt test \
  -m /path/to/models/model.ckpt-500000.pt \
  -s /path/to/test_system \
  -n 1 \
  -d smoke_checkpoint
```

Then test all frames:

```bash
dp --pt test \
  -m /path/to/models/model.ckpt-500000.pt \
  -s /path/to/test_dataset \
  -n 0 \
  -d held_out
```

Retain `.e.out`, `.f.out`, `.v.out`, and logs when those labels are present. `dp test` does not
produce a separate `.s.out`. Derive stress from virial and cell volume only with an explicit tensor,
sign, and unit convention, or use a separately validated analysis script. Record the tested checkpoint
hash.

## 3. Frozen DPA4/SeZM artifacts

Export behavior depends on DeePMD and PyTorch versions:

```bash
dp --pt freeze -c /path/to/run -o exported_model
find /path/to/run -maxdepth 2 -type f -name 'exported_model*' -ls
```

Graph-capable DPA4 may export an AOTInductor `.pt2` archive. Use the filename actually reported by
`dp freeze`; do not hard-code `.pth` from older examples.

Immediately smoke-test the exported artifact on a representative large frame. If it OOMs or
segfaults while the original checkpoint passes:

1. preserve the export log, runtime versions, and kernel error;
2. mark the artifact incompatible and prevent downstream use;
3. continue validation with the original checkpoint when supported;
4. do not diagnose the training weights as failed solely from the export error;
5. do not delete the failed artifact without authorization.

Typical environment symptoms include missing `GLIBCXX_*`, custom-op/PyTorch mismatch, CUDA OOM,
or AOTInductor runtime faults. Source the same environment used for training before freeze and test.

## 4. Metrics and energy offsets

Report global and grouped metrics:

```text
Energy MAE/RMSE in eV and meV/atom
Force-component MAE/RMSE in eV/A
Virial-component MAE/RMSE in eV
Stress-component MAE/RMSE in eV/A^3
frame and system counts
```

For multiple exact compositions, calculate the energy residual

```text
delta_E = E_pred - E_DFT
```

and report for each composition:

```text
mean bias
raw MAE/RMSE
MAE/RMSE after subtracting the composition mean bias
```

The centered error measures energy differences within a composition more directly. It does not
repair forces, stresses, or cross-composition thermochemistry and must not be used to conceal a
model error.

When final frames are a strict subset of all trajectory frames, report both views but state the
subset relation. They are not two independent test sets.

## 5. Mechanics validation

A mechanics model needs strained configurations with energy, force, and virial labels. Split all
strain states of one mother structure together.

Required comparisons include:

```text
DFT vs model stress at every positive and negative strain
raw and symmetry-consistent Cij
tensor asymmetry and positive definiteness
Voigt/Reuss/Hill B and G
Young's modulus and Poisson ratio
clamped-ion vs relaxed-ion behavior where relevant
strain-amplitude sensitivity
```

Use the same strain convention and stress sign for DFT and model. A low stress RMSE can coexist with
an incorrect stress derivative, so direct `Cij` comparison is mandatory.

For relaxed-ion elasticity, also validate internal-coordinate optimization tolerances. A loose force
threshold can dominate the finite-difference derivative even when every calculation exits normally.

## 6. Model card and decision

Record:

```text
model family and release source
pretraining dataset, release version/date, URL, and license
checkpoint identity, version, source, and path
DeePMD/PyTorch/CUDA versions
training dataset version and split manifest
DFT protocol fingerprint
type_map
loss and learning-rate schedule
steps, seeds, batch size, and GPU
held-out metrics by system
physics-validation results
supported elements, phases, strains, temperatures, and tasks
known failure modes and excluded regimes
```

Choose the model according to the deployment target. For relaxation or mechanics, prioritize held-out
force and stress behavior plus direct physics validation. Do not select from raw total-energy MAE
alone, and do not treat a scratch control's lower constant energy offset as proof of better forces or
elastic response.

For a scratch-versus-pretrained or LoRA-versus-full-parameter comparison, keep the dataset, grouped
split, target labels, evaluation frames, and reported metrics identical. Declare architecture,
optimizer, trainable-parameter count, learning-rate, and step differences. Train a full-data
production model only after grouped held-out validation has established the workflow; never report
full-data training error as generalization performance.
