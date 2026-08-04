# DPA4 Fine-tuning: Environment, Data, and Training

## Contents

1. Environment preflight
2. Released-model compatibility
3. Dataset audit and splitting
4. Input configuration
5. Smoke, production, and restart commands
6. Durable execution and records

## 1. Environment preflight

Build a dedicated environment from the newest official DeePMD-kit `master` version available when
the workflow is started. Use that same environment for training, testing, freezing, and inference.
Do not combine DeePMD-kit, PyTorch, or command entry points from different Python environments.

Follow the current official installation instructions for the PyTorch backend, then verify:

```bash
export DPA4_ENV=/path/to/conda/env
export PATH="$DPA4_ENV/bin:$PATH"
export LD_LIBRARY_PATH="$DPA4_ENV/lib:${LD_LIBRARY_PATH:-}"

dp --version
dp --pt train -h
dp --pt test -h
python -c 'import torch, deepmd; print(torch.__version__, deepmd.__version__)'
nvidia-smi
```

Record the installed DeePMD-kit version, PyTorch and CUDA versions, Python executable, and
installation command. Running `dp --version` alone may not load every PyTorch custom operator, so
also run a backend command or one-frame test.

Do not start production training until the same explicit environment passes all of the following:

```text
normal dp --pt train smoke test
normal dp --pt test on a representative frame
normal tck dpa4 evaluate on a representative frame
```

A diagnostic run assembled from packages in different Python locations does not establish a
reproducible production environment.

Useful thread controls for a single-GPU workstation are:

```bash
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export NUMEXPR_NUM_THREADS=4
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
```

These are starting points, not universal performance settings.

## 2. Released-model compatibility

Before fine-tuning:

1. record the checkpoint family, release version, source, license, and path;
2. identify the full family, variant, pretraining dataset, release version/date, and release URL;
3. inspect its `type_map`, descriptor, fitting net, ZBL bridge, precision, and compile settings;
4. confirm all downstream elements are represented;
5. retain the release-provided input/template and license information.

AIR, NEO, and Mini differ in capacity and cost. Do not select only from the name: run a
production-size inference smoke and estimate batch memory. A smaller model is a useful speed
control; a larger model is not automatically more accurate after downstream fine-tuning.

DPA4/SeZM configuration fields are version-sensitive. A validated release input can include fields
such as `type: SeZM`, SO(2)/SO(3) descriptor controls, a ZBL bridge, AMP, TF32, HybridMuon, EMA,
and WSD learning rates. Do not copy individual fields into another release without validating the
whole configuration.

## 3. Dataset audit and splitting

For every DeepMD system, verify:

```text
type.raw and type_map.raw
set.*/coord.npy and box.npy
set.*/energy.npy and force.npy
set.*/virial.npy when stress is trained
finite arrays and matching frame counts
minimum interatomic distance
DFT method fingerprint
source task/trajectory identity
```

Use `tck deepmd report` and `tck dpdata overlap` where their input contracts apply. A format-level
audit does not replace source-task provenance.

Split by a manifest grouping column, for example:

```text
task_id
trajectory_id
mother_key
configuration_family
```

The test set should include structures relevant to deployment but absent from training. For a
mechanics potential, reserve complete mother structures and all their strain states together.

When datasets have very different frame counts, configure dataset sampling intentionally. A small
strain or defect dataset can be numerically overwhelmed by a large relaxation dataset even when it
is scientifically essential.

## 4. Input configuration

Use the full DPA4 model block from a compatible release or validated run. Modify only fields whose
effect is understood. The experiment-specific sections normally include:

```json
{
  "learning_rate": {
    "type": "wsd",
    "start_lr": 0.0001,
    "stop_lr": 0.000001,
    "warmup_ratio": 0.01,
    "decay_phase_ratio": 0.65,
    "decay_type": "cosine"
  },
  "loss": {
    "type": "ener",
    "loss_func": "mae",
    "f_use_norm": true,
    "start_pref_e": 20,
    "limit_pref_e": 20,
    "start_pref_f": 20,
    "limit_pref_f": 20,
    "start_pref_v": 5,
    "limit_pref_v": 5
  },
  "training": {
    "training_data": {
      "systems": "/path/to/train",
      "batch_size": 1
    },
    "validation_data": {
      "systems": "/path/to/validation",
      "batch_size": 1
    },
    "numb_steps": 200000,
    "gradient_max_norm": 5,
    "save_freq": 5000,
    "save_dir": "./models",
    "enable_ema": true,
    "disp_file": "lcurve.out",
    "disp_freq": 500,
    "seed": 20260803
  }
}
```

This fragment is not a complete DPA4 input. Merge it with the exact compatible `model` and
`optimizer` blocks. Loss weights and steps are experiment choices, not universal defaults.

The current DeePMD-kit `master` interface accepts `training/save_dir`, creates it recursively, and
leaves latest-checkpoint symlinks in the run directory. Query `dp --pt doc-train-input` in the actual
training environment before use in case the latest interface has changed.

Use `batch_size: 1` for the first production-size smoke. Increase only after measured memory leaves
safe headroom. DPA4 training and testing can approach the full memory of a 24 GB GPU for a few
hundred atoms per frame.

## 5. Smoke, production, and restart

Create separate run directories:

```text
smoke_v1/
finetune_v1/
scratch_control_v1/
```

Full-parameter fine-tune:

```bash
dp --pt train input.json \
  --finetune /path/to/released_dpa4.pt
```

LoRA fine-tune is a DPA4-specific parameter-efficient option for a smaller downstream dataset,
limited trainable-parameter budget, or an explicit comparison with full-parameter adaptation. Use
the exact DPA4 example shipped with the installed DeePMD-kit version. A typical model fragment is:

```json
{
  "model": {
    "type": "dpa4",
    "lora": {
      "rank": 16,
      "alpha": 16.0
    }
  }
}
```

Run it with:

```bash
dp --pt train lora_ft.json --finetune /path/to/released_dpa4.pt
```

The values above reproduce the official example, not universal defaults. Confirm compatibility with
the exact pretrained architecture and installed DPA4 implementation before training. Keep LoRA and
full-parameter runs in separate directories with identical data splits when comparing them.

If neighbor statistics have already been audited and recomputation is intentionally disabled:

```bash
dp --pt train input.json \
  --finetune /path/to/released_dpa4.pt \
  --skip-neighbor-stat
```

`--skip-neighbor-stat` also disables selection checking and automatic selection. Do not use it to
bypass an unknown or failing neighbor-list configuration.

Resume:

```bash
dp --pt train input.json --restart /path/to/model.ckpt.pt
```

Check the installed `dp --pt train -h`; some versions expect a checkpoint prefix or expose short
options. Never guess across DeePMD versions.

## 6. Durable execution and records

Use the site's scheduler or an approved persistent user service. A robust runner should:

1. source the exact environment;
2. change to the run directory;
3. refuse to overwrite a `COMPLETED` run;
4. restart from an existing valid checkpoint when explicitly requested;
5. pipe stdout/stderr to `train.log`;
6. create `COMPLETED` only after `dp train` exits successfully;
7. record PID/job ID, command, start/end timestamps, and GPU identity.

Do not infer completion from a checkpoint filename alone. Verify the final `lcurve.out` step and
load the checkpoint in a one-frame test.
