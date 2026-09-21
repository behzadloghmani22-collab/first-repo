# Example output (dry run with the mock nTopCL)

This folder is the complete output of

```
python mock/make_demo_folder.py <folder>
python -m cage_doe run --root <folder> --mock --profile standard
```

on four synthetic variants (octet, gyroid, diamond, kelvin). It shows exactly what the
real campaign produces: `figures/`, `presentation/lattice_cage_DOE_results.pptx`,
`report/summary.html`, `data/*.csv` and, in `runs_sample/`, the files written for one
nTop run (input JSON, output JSON, log, metadata).

Every figure is watermarked **"SURROGATE DEMO - not nTop data"**: the numbers come from
textbook lattice mechanics inside `mock/mock_ntopcl.py`, not from nTop, and must not be
presented as results. Re-run on the real `.ntop` files to obtain the presentable version.
