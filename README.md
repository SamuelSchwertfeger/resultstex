# resultstex

[![PyPI](https://img.shields.io/pypi/v/resultstex)](https://pypi.org/project/resultstex/) [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23271713.svg)](https://doi.org/10.5281/zenodo.23271713)

Keep every number in a LaTeX paper generated from code. Analysis scripts record values with `record()`, a build step turns them into LaTeX macros, and an audit command flags missing keys and numbers typed by hand.

## Install

```
pip install resultstex
```

It needs Python 3.10 or newer and has no runtime dependencies. The LaTeX side is one file, `latex/resultstex.sty`, which you copy from this repository (see "Using the .sty" below); pip does not install it.

For development:

```
git clone https://github.com/SamuelSchwertfeger/resultstex
cd resultstex
uv sync
uv run pytest
```

## Quickstart

The `example/` folder holds a complete run.

1. Record values in your analysis code (`example/analysis.py`). This writes `results.json` in the current directory:

   ```python
   import resultstex

   resultstex.record('auc_xgb', 0.9134, fmt='.3f')
   resultstex.record('n_samples', 48213, fmt=',')
   ```

   `record(key, value, fmt=None, unit=None, note=None, path='results.json')`. Keys match `[a-zA-Z][a-zA-Z0-9_]*`. Each entry also stores the calling script, the short git commit of its folder, and a timestamp.

2. Generate the LaTeX macros:

   ```
   resultstex build            # results.json -> results.tex
   ```

   `python -m resultstex build` does the same. Use `-o` to change the output file.

3. Use them in the paper (`example/paper.tex`):

   ```latex
   \usepackage{resultstex}
   \input{results}
   ...
   XGBoost reaches an AUC of \result{auc_xgb} on \result{n_samples} samples.
   ```

4. Audit the paper:

   ```
   resultstex audit paper.tex [--results results.json] [--strict]
   ```

   It exits 1 if a `\result{key}` is missing from `results.json`. Numbers typed directly into the text are printed as warnings (see Limitations for what the check can see); with `--strict` they also cause exit 1. Files pulled in with `\input` or `\include` are checked too.

### Hard-coded numbers that are fine

Add `% resultstex: ignore` at the end of a line to skip the hard-coded number check for that line. Missing-key checks still apply.

```latex
The corpus has 1500 files. % resultstex: ignore
```

## Using the .sty (LaTeX and Overleaf)

`latex/resultstex.sty` is the only LaTeX file you need. Copy it into the folder of your paper (on Overleaf: upload it next to `main.tex`, together with the generated `results.tex`) and load it with `\usepackage{resultstex}`. An undefined key prints a red `??key??` marker and a LaTeX warning instead of failing the build. The package requires `xcolor`.

Run `resultstex build` locally and upload or commit the new `results.tex` whenever your results change.

## Limitations

- Numbers are found with regular expressions, not a LaTeX parser. The audit can miss hard-coded numbers and can flag numbers that are not results. Four-digit years are skipped unless followed by words like "samples".
- Whole numbers below 100 are never flagged ("20 features", "10 folds", "5 seeds"), and neither are numbers written with exponents such as `10^{-3}`. Only decimals, percentages, comma-grouped numbers and whole numbers of three or more digits are checked.
- `\input` and `\include` are followed only when the file name is a plain literal.
- `results.json` is read and rewritten on every `record()` call; it is not safe for several processes writing the same file at once.
- Values are formatted when recorded, so changing a format means re-running the analysis.

## Acknowledgements

The CI setup is adapted from [DFAIR-LAB-Augusta/XSecIoT](https://github.com/DFAIR-LAB-Augusta/XSecIoT) (Seth Barrett).

## License

MIT
