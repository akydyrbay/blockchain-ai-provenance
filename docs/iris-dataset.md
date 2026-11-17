# Iris demo: data and model record

This file documents how the preserved Iris demo files were produced. These files
are the project's end-to-end, byte-level verification example. They are not the
main workload, which is the Hugging Face lineage tree (see `docs/proposal.md`).

Check the preserved files at any time, without retraining:

```bash
python scripts/check_artifacts.py --output results/validation/artifact_check.log
```

## Source

| Item | Value |
|---|---|
| Dataset | Iris (Fisher, 1936), the copy bundled with scikit-learn: `sklearn.datasets.load_iris()` |
| scikit-learn version | 1.5.2 (pinned in `requirements.txt`, also recorded in each `metadata.json`) |
| Full dataset | 150 rows, 4 numeric features, 3 classes (50 rows each) |
| Features | sepal length, sepal width, petal length, petal width (cm) |
| Target | class index 0, 1, 2 (setosa, versicolor, virginica) |
| Network access | None. The data ships with scikit-learn |

## Split

| Item | Value |
|---|---|
| Method | `sklearn.model_selection.train_test_split` on row indices |
| Test share | 0.2 (30 rows), stratified by class |
| Random seed | `random_state=42` |
| Kept training rows | 120 (40 per class) |
| Row order in the CSV | Ascending original index (`np.sort(train_idx)`) |
| Test rows | Not saved and not evaluated. The demo reports no accuracy, so none should be quoted |

## CSV serialization (`data/iris_train.csv`)

The registry commits to the exact bytes, so the format is fixed:

- UTF-8, `\n` line endings, written with `csv.writer(lineterminator='\n')`.
- Header: `sepal length (cm),sepal width (cm),petal length (cm),petal width (cm),target`.
- Features formatted with `format(float(value), '.8g')`, so `3.0` is written as `3`. Target is written as an integer.
- 121 lines in total (header + 120 rows).
- SHA-256: `0x80c30023defb7b86f4ed81d6692c97db5fa997738010235f33cfd4a9939699b9`.

## Models

Both versions are trained **independently** on the same 120 rows. v2 is *not* a
fine-tune of v1; `parent_version` only records the version order in the registry.

| | v1 | v2 |
|---|---|---|
| Estimator | `sklearn.linear_model.LogisticRegression` | same |
| `C` (inverse regularization) | 1.0 | 0.25 |
| `solver` / `max_iter` / `random_state` | lbfgs / 1000 / 42 | same |
| File | `models/v1/model.joblib` (`joblib.dump`, `compress=3`) | `models/v2/model.joblib` |
| Artifact SHA-256 | `0x3348384082600d1c796a3c76ad6dcb52cf5ffa4fd68458e48f3bb66ff058e1b1` | `0xc4696eba4066a31624dc307ed392dca961156c4e1c91a839a99160796196f7e9` |
| Metadata SHA-256 | `0x2a37fe2125d7894da60e5d98a343530efa489e28c78e9bddf876e1b14a14ef65` | `0x4e84d3eb4988a66ebf4bcbaf6bc0a55ab2aa1898a240fe9a75aa1ccdfa697771` |

## Metadata (`models/v*/metadata.json`)

JSON with sorted keys, 2-space indent, `ensure_ascii=False`, and a trailing newline. Fields:
`name`, `version`, `parent_version`, `training_data_sha256`, `artifact_sha256`,
`training_code_sha256` (SHA-256 of `scripts/train_demo.py`:
`0xf16a8aff75c75f13d3b284d8c8c734df78734f71cf0c507c5525819bb388d7cb`), `algorithm`,
`hyperparameters`, `python_version` (3.11.13), `scikit_learn_version` (1.5.2).

## Reproducibility notes

- Use the committed files for verification. Running `python scripts/train_demo.py`
  again rewrites them; the CSV should come out the same, but the joblib bytes (and so
  the metadata hashes) can change with library or platform versions.
- Any edit to `scripts/train_demo.py`, even whitespace, changes `training_code_sha256`
  and makes the committed metadata disagree with the script. `check_artifacts.py`
  reports this.
- The hashes above are also in `results/artifact_hashes.txt`, which is what the
  check script reads.
