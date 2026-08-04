# Environment and model

Read this reference when diagnosing DPA4 availability, selecting a model, checking reproducibility, or discussing the newer official DPA4 interface.

## Required live checks

Run checks with the exact interpreter that will launch `tck`:

```bash
python - <<'PY'
import sys
import deepmd
import torch

print("python", sys.executable)
print("deepmd", deepmd.__version__, deepmd.__file__)
print("torch", torch.__version__, torch.__file__)
PY
```

Also record:

```bash
python -m deepmd --version
python -m deepmd --pt show MODEL type-map descriptor fitting-net
```

Prefer `python -m deepmd` when the `dp` executable is missing or ambiguous. Confirm that `python`, `tck`, `deepmd`, PyTorch, ASE, and `dftd3` come from the intended environment.

Check user-site leakage explicitly:

```bash
PYTHONNOUSERSITE=1 python -c 'import deepmd; print(deepmd.__file__)'
```

If this fails while a normal import succeeds, the environment is borrowing `deepmd` from the user site and is not self-contained.

## TCCKit model resolution

TCCKit resolves the model in this order:

1. `--model PATH`;
2. `DPA4_MODEL`;
3. `~/dpa4/Neo-MPtrj/model.pt`.

Report the resolved absolute path together with the model family, release version, and source when available. A filename alone is not a complete model identity.

Inspect the selected model at runtime and record its type map, model family, source, and license when available. Do not embed a host-specific environment conclusion in this reusable skill.

The default TCCKit calculator loads the model through `deepmd.calculator.DP`. Unless `--no-d3` is supplied, it adds `dftd3.ase.DFTD3(method="pbe", damping="d3bj")`. Therefore default energies, forces, and stresses belong to the combined DPA4 + PBE-D3(BJ) calculator.

## Current official DPA4 facts

The current DeePMD-kit documentation identifies DPA4 with the SeZM descriptor and aliases `DPA4`, `SeZM`, and `sezm`. It is PyTorch-only. The documented DPA4 export path uses `.pt2` AOTInductor output and model compression is not supported. A project checkpoint named `.pt` may still be consumed directly by the Python calculator; do not confuse that checkpoint with the documented exported deployment artifact.

Verify these details against the installed DeePMD-kit version because released, beta, and development builds may expose different CLI and export behavior.

Primary references:

- [DPA4/SeZM model documentation](https://docs.deepmodeling.com/projects/deepmd/en/latest/model/dpa4.html)
- [DeePMD-kit training input schema](https://docs.deepmodeling.com/projects/deepmd/en/latest/train/train-input.html)
- [DeePMD-kit model documentation](https://docs.deepmodeling.com/projects/deepmd/en/latest/model/index.html)
