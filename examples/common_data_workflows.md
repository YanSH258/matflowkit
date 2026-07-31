# Common data workflows

## Audit and collect ABACUS tasks

```bash
mfk abacus audit ./tasks --expected 120 --strict
mfk abacus to-deepmd ./tasks ./dataset_v1 \
  --expected 120 \
  --type-map "Ca Mg P O H"
```

The output contains composition-resolved NPY systems, task and frame manifests,
validation summaries, and SHA256 checksums.

## Merge datasets

```bash
mfk deepmd merge relaxation_data strain_data \
  --output combined_data
```

Different compositions remain in separate systems. Exact coordinate duplicates
stop the command unless `--allow-duplicates` is explicit.

## Convert formats

```bash
mfk dpdata convert work training_data \
  --from cp2kdata/md --to deepmd/npy

mfk dpdata convert training_data train.xyz \
  --from deepmd/npy --to extxyz
```
