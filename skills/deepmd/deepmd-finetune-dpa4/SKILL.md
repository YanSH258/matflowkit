---
name: deepmd-finetune-dpa4
description: Fine-tune, train from scratch, apply LoRA, resume, compare, and validate DPA4/SeZM interatomic potentials with the DeePMD-kit PyTorch backend. Use for provenance-identified DPA4 checkpoints such as AIR, NEO, or Mini; DeepMD NPY datasets with energy, force, and optional virial labels; DPA4 input.json preparation; GPU smoke and production training; checkpoint testing and export; scratch-versus-pretrained comparison; and force, stress, or mechanics validation. Do not use for ordinary DPA4 structure relaxation without model training.
---

# DPA4 Fine-tuning

Adapt a released or self-trained DPA4 model to a downstream atomistic dataset. Treat data
integrity, model compatibility, held-out validation, and deployment checks as separate gates.

## Scope

Use this skill for:

- fine-tuning a DPA4/SeZM checkpoint on `deepmd/npy` or another DeePMD-supported format;
- training DPA4 from scratch or applying DPA4 LoRA adapters;
- resuming interrupted DPA4 training;
- comparing pretrained initialization with scratch training;
- testing checkpoints on held-out structures, trajectories, strains, or compositions;
- deciding whether a model is suitable for relaxation, MD, stress, or elastic calculations.

Use MatFlowKit's `dpa4` skill for inference-only `relax`, `batch-relax`, `evaluate`, and
`neb` work. Keep DPA4 scratch training and LoRA in this skill. When comparing DPA4 with
DPA3 or `se_e2_a`, consult the current official documentation for every candidate until a
version-current model-selection skill is available; do not route DPA4 work to the legacy
`deepmd-train` skill.

## First Checks

Before writing `input.json`, establish these facts from files and the live environment:

```text
DeePMD-kit version and PyTorch backend
pretrained checkpoint identity, source, and path
released model family, pretraining dataset, release URL, license, and exact architecture
pretrained type_map and downstream element coverage
dataset format, systems, frames, labels, and DFT fingerprint
trajectory/mother/configuration grouping for leakage-safe splits
GPU model, memory, and expected atom count per frame
target use: relaxation, MD, energy ranking, stress, or elasticity
```

Do not infer the descriptor or fitting-network definition from the model name. DPA4 is evolving;
use the release-provided training script, a compatible `out.json`, or a configuration already
validated with the exact checkpoint and installed DeePMD version.

For environment, full-parameter training, LoRA, and restart details, read
[references/training.md](references/training.md).
For testing, frozen-model compatibility, and scientific acceptance, read
[references/validation.md](references/validation.md).

## Workflow

### 1. Audit and split data

Require finite energy and force labels. Require virial when stress or mechanics is a target.
Keep one electronic-structure protocol per dataset version. Preserve the exact `type_map` order.

Split before training by the highest leakage unit:

```text
same relaxation/MD trajectory -> one split
same mother configuration and its strains -> one split
same structure represented in several formats -> one split
```

Never randomly split ionic frames from the same trajectory. If final frames are contained in an
all-frame dataset, do not count or sample them twice.

### 2. Freeze the experiment contract

Create a new run directory. Record:

```text
input.json and resolved out.json
environment activation file
pretrained model identity and source
dataset manifest and version
split manifest
random seeds
training and validation systems
GPU/runtime information
```

Do not overwrite a completed or partially completed run. Fine-tuning, scratch controls, and
ablations belong in separate directories.

### 3. Run a smoke test

Use the same model architecture, labels, and representative production-size frames as the intended
workflow, but with a short schedule and a new output directory. Confirm:

- custom DeePMD/PyTorch operators load;
- neighbor statistics and `sel` are valid;
- GPU memory remains below the device limit;
- energy, force, and virial losses are finite;
- a checkpoint is written and can be reloaded;
- one held-out frame can be evaluated.

Passing a tiny or low-atom-count smoke test is insufficient when production frames are much larger.

### 4. Select the adaptation mode, train, and resume

Use full-parameter fine-tuning when the downstream dataset is sufficiently broad and updating the
whole model is acceptable. Consider LoRA for smaller datasets, limited memory, or a controlled
parameter-efficient comparison. Obtain LoRA settings from the exact release configuration and the
installed DeePMD DPA4 example; do not invent a universal rank or alpha.

Fine-tune with the command supported by the installed DeePMD version, normally:

```bash
dp --pt train input.json --finetune /path/to/pretrained.pt
```

Use `--use-pretrain-script` only after confirming that the DPA4 release embeds a compatible script
and the current runtime supports it. Otherwise provide the full validated model configuration.

Resume only from the latest valid checkpoint in the same experiment:

```bash
dp --pt train input.json --restart /path/to/model.ckpt.pt
```

Do not use `--restart` to change the dataset, architecture, loss definition, or optimizer. Such a
change is a new experiment or a documented fine-tuning stage.

### 5. Monitor

Inspect `lcurve.out`, `train.log`, checkpoints, GPU use, and process state. A scheduler or service
completion state proves only that the process exited; require the intended final step, finite recent
losses, a readable checkpoint, and an explicit completion record.

### 6. Test before freezing

Test the original checkpoint first:

```bash
dp --pt test -m /path/to/model.ckpt-STEP.pt -s /path/to/test_data -n 1 -d smoke
dp --pt test -m /path/to/model.ckpt-STEP.pt -s /path/to/test_data -n 0 -d full_test
```

The one-frame command is a runtime smoke test; `-n 0` evaluates all frames. Use held-out data for
generalization claims.

### 7. Freeze and deploy only after validation

Run `dp freeze` only after direct checkpoint testing succeeds. Inspect the actual generated suffix;
DPA4/SeZM may export an AOTInductor `.pt2` archive even when an older command example suggests
`.pth`. Smoke-test the frozen artifact on a production-size frame before using it in MD or sharing it.

If a frozen artifact fails but the original checkpoint passes, record a runtime/export compatibility
failure. Do not call it a failed training model and do not silently substitute the artifact.

## Required validation

Use the metric, energy-offset, mechanics, deployment, model-card, and scratch-control requirements in
[references/validation.md](references/validation.md). Keep checkpoint loading, held-out numerical
accuracy, target-property validation, and deployment stability as separate conclusions.

## Stop Conditions

Stop and diagnose before continuing when any of these occurs:

- downstream elements are absent from the pretrained `type_map`;
- DFT protocols or energy references are mixed without separation;
- trajectory or mother-configuration leakage is present;
- `libstdc++`, PyTorch, CUDA, or custom-op loading fails;
- loss becomes NaN or checkpoints cannot reload;
- production-size inference OOMs or segfaults;
- virial labels are absent while elastic predictions are claimed;
- no held-out physics validation exists for the intended deployment.

## Sources and authorship

Copyright 2026 YanSH258. Original MatFlowKit skill based on practical DPA4 fine-tuning workflows
and current DeePMD-kit DPA4/SeZM documentation. No text was copied from the older DeePMD-kit DPA3
skills. Use the newest official DeePMD-kit `master` version available when building the environment
and validate the commands against that installed version.

Primary sources:

- [DPA4/SeZM documentation](https://docs.deepmodeling.com/projects/deepmd/en/latest/model/dpa4.html)
- [DeePMD-kit training input schema](https://docs.deepmodeling.com/projects/deepmd/en/latest/train/train-input.html)
- [DeePMD-kit fine-tuning documentation](https://docs.deepmodeling.com/projects/deepmd/en/latest/train/finetuning.html)

Record the actual model release page and license in each experiment manifest; a checkpoint filename
alone is not sufficient provenance.
