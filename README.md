# Lattice fusion-cage DOE & optimisation through nTopCL

> ## ⚠ READ `HANDOFF.md` FIRST — it is the entry point to this project
>
> **No nTop run has ever been executed here.** Everything in `results/` was produced by
> `mock/mock_ntopcl.py`, a Python stand-in, because the session that built this repository ran
> in a cloud container with no access to nTop, no nTopCL and no `.ntop` files. Those numbers
> are fabricated and must never be presented.
>
> nTop lives on a separate Windows PC reached over SSH. Several engineering quantities are
> also computed in Python inside `cage_doe/objectives.py` (apparent modulus, porosity, mass,
> safety factors, pore size) that **nTop must compute instead**.
>
> `HANDOFF.md` explains the whole problem from scratch — the implant, the lattices, the
> machines, the defect list and the plan. Start there.
>
> **Rule for all future work: if something can be done in nTop through nTopCL, doing it in
> anything else is unacceptable.**

`cage_doe` runs a complete design-of-experiments (DOE) and optimisation campaign on
lattice lumbar interbody fusion cages modelled in nTop. It drives `ntopcl.exe`
directly, sweeps the exposed input parameters of every `.ntop` variant found in a
folder (one variant per lattice type), scores each design against a clinically
motivated definition of *optimal*, verifies the predicted optimum in nTop, ranks the
lattice types and writes presentation-ready figures, a report and a PowerPoint deck.

Everything below was developed and tested against a physics-based stand-in for
nTopCL (`mock/mock_ntopcl.py`), because nTop only runs on Windows with a licence.
The pipeline is ready to run on the real files; see **Quick start**.

---

## Quick start (Windows, PowerShell)

```powershell
# 1. Python 3.10+ and the dependencies
pip install -r requirements.txt

# 2. Point the tool at the folder with the four .ntop variants
cd <this repository>
python -m cage_doe init --root "C:\Users\Moein Salehi\Desktop\moein new files"

# 3. Check what was found (no nTop runs yet): variants, input templates, matched names
python -m cage_doe discover --root "C:\Users\Moein Salehi\Desktop\moein new files"

# 4. Dry run of the whole pipeline in ~3 minutes with the stand-in (no licence needed)
python -m cage_doe run --root "C:\Users\Moein Salehi\Desktop\moein new files" --mock --results-dirname DOE_dryrun

# 5. The real campaign (nTopCL is auto-detected, or pass --ntopcl "C:\Program Files\nTopology\nTopology\ntopcl.exe")
python -m cage_doe run --root "C:\Users\Moein Salehi\Desktop\moein new files" --profile standard
```

Results appear in `<root>\DOE_results\` (figures, report, presentation, data, one
folder per nTop run). The campaign can be stopped at any time and re-launched with the
same command: finished runs are reused, nothing is recomputed.

Useful variants of step 5:

| command | effect |
|---|---|
| `--profile quick` | ~17 nTop runs per variant instead of ~36 |
| `--profile thorough` | ~52 runs per variant, 4 infill rounds |
| `--budget 25` | hard cap on new nTop runs per variant |
| `--analyze-only` | no new nTop runs: refit, re-optimise, redraw everything from the cached runs (use after editing weights or targets in `doe_config.json`) |
| `--phases prior,screen,rsm,lhs` | run only some phases (e.g. gather data today, optimise tomorrow) |
| `--no-pptx` | skip the PowerPoint deck |

---

## Preparing the nTop notebooks

Each `.ntop` file must expose its parameters in nTop's **Automate** panel:

**Inputs** (swept by the DOE; names are matched case-insensitively, with many aliases,
against `doe_config.json` - the `discover` command shows the match table):

| factor in `doe_config.json` | typical nTop input names | default range |
|---|---|---|
| Cell Size | Cell Size, Unit Cell Size, Cell | 1.5 - 4.0 mm |
| Strut Thickness | Strut Thickness, Thickness, Beam Thickness, Sheet Thickness | 0.3 - 0.9 mm |
| Shell Thickness | Shell Thickness, Rim Thickness, Wall Thickness | 0.5 - 1.5 mm |

Add, remove or rename factors freely in the `factors` list (any number of factors works;
designs adapt automatically). Inputs that are not factors keep their template values.

**Outputs** (read after every run; each is optional, but the more the better):

| output | used for |
|---|---|
| Volume of the final lattice body (mm^3) | porosity, mass |
| Envelope / design-space volume (mm^3) | porosity (else `geometry.footprint_area_mm2 x height_mm`) |
| Surface area (mm^2) | osteo-conduction tie-breaker |
| Max von Mises stress (MPa) from the static FE at the design load | yield and fatigue safety factors |
| Max displacement (mm) from the same FE | axial stiffness and apparent modulus |
| Pore size / max inscribed sphere (mm or um) | pore-size criterion (else estimated as `kappa x cell - strut`; flagged in the report) |
| Mass, minimum thickness, contact area, relative density | used when present |

Units are converted automatically when the JSON carries a `units` field (kg, cm^3, Pa,
um ... are all fine). Keep the FE load equal to `physics.design_load_N` (1200 N by
default) or change that value.

**Input JSON template.** Put the nTopCL input JSON you already used for the octet run
next to each `.ntop` file (export it from the Automate panel for the other three). The
tool mutates that template - it never invents a JSON layout - so whatever key layout your
nTop version exported (`values` vs `value`, units, descriptions) is preserved. If no
template exists, the documented layout is generated and a warning is printed.

The folder is scanned recursively, so `octet\cage.ntop`, `gyroid\cage.ntop` ... or four
files in one folder both work. Any existing `*output*.json` next to a variant is imported
as a prior run (the octet run you already made is used as data, not repeated).

---

## What "optimal" means (and how to change it)

Every run is scored with a Derringer-Suich desirability: each criterion is mapped to 0-1
(1 inside its clinical target window, 0 beyond a hard limit), and the criteria are
combined by a weighted geometric mean, so a design that violates any hard limit scores 0.

| criterion | full desirability | hard limit | weight | why |
|---|---|---|---|---|
| Apparent modulus E = (F/d)·H/A | 2 - 5 GPa (target 3) | 0.5 - 20 GPa | 0.30 | PEEK/bone-like stiffness limits stress shielding and subsidence while still supporting fusion |
| Porosity | 60 - 75 % | 40 - 90 % | 0.22 | open volume for bone in-growth |
| Pore size | 500 - 800 um | 300 - 1000 um | 0.22 | vascularised osteogenesis window |
| Fatigue safety factor at 1200 N (walking) | >= 2 | >= 1 | 0.12 | endurance limit 350 MPa (LPBF Ti-6Al-4V) |
| Yield safety factor at 2000 N (lifting) | >= 4 | >= 2 | 0.06 | ASTM F2077-style static strength, yield 950 MPa |
| Strut / sheet thickness | >= 0.45 mm | >= 0.30 mm | 0.04 | LPBF printability |
| Mass / surface area | best in campaign | - | 0.02 each | tie-breakers |

All of it lives in the `objectives`, `physics` and `geometry` sections of
`doe_config.json`. After changing weights or windows run with `--analyze-only`: the
ranking, figures and deck are rebuilt from the cached nTop runs in a couple of minutes.
The figure `fig05_weight_robustness.png` shows how stable the ranking is when the weights
are perturbed randomly, so the choice of weights can be defended in the presentation.

---

## The campaign (per variant)

1. **Prior runs** already in the folder are imported.
2. **Screening**: 2-level full factorial (fractional, resolution IV, above 4 factors) + centre points.
3. **Response surface**: face-centred central composite design (or Box-Behnken).
4. **Space filling**: Latin-hypercube runs.
5. **Surrogates**: for every nTop response a quadratic response-surface model and a
   thin-plate RBF are fitted in coded space (log-transform for stress and displacement);
   the one with the lower leave-one-out error is used, their disagreement drives exploration.
   A k-NN model of *failed* runs (self-intersecting or solid lattices) penalises regions
   where nTop cannot build the geometry.
6. **Adaptive infill** (several rounds): the surrogate optimum (exploit), the point of
   largest model disagreement (explore) and a maximin point among the top decile (diversify)
   are run in nTop and the models are refitted.
7. **Optimisation**: differential evolution + Nelder-Mead polish of the desirability;
   the top-N predicted designs are **verified with real nTop runs**, and the verified
   optimum is what gets ranked and reported.
8. **Analysis**: Sobol sensitivity indices, one-factor effects and interactions around the
   optimum, response surfaces over the two most influential factors, Pareto fronts
   (stiffness-matching vs fatigue strength, porosity vs fatigue strength), ranking and
   its robustness to the weights.

Run counts for three factors: quick ~17, standard ~36, thorough ~52 per variant. At a
typical 3-8 min per nTop lattice + FE run that is roughly 3-10 h (quick) or 7-20 h
(standard) for four variants; leave it running overnight, it is restartable.

---

## Output folder `DOE_results\`

```
figures\        fig00 - fig08: objective definition, run summary, ranking, metric comparison,
                radar, weight robustness, Pareto fronts of all variants, recommended settings,
                predicted-vs-verified; <variant>_fig10 - fig17: sampled designs, main effects,
                interactions, response surfaces, Pareto fronts, sensitivity, convergence, model fit
presentation\   lattice_cage_DOE_results.pptx - all of the above as a 16:9 deck with a recommendation slide
report\         summary.html / summary.md (tables + figures), discovery.md (what was found and matched)
data\           runs_all.csv (every run: inputs, nTop outputs, derived metrics, desirabilities),
                ranking.csv, optima.csv, model_diagnostics.csv, sensitivity_sobol.csv,
                <variant>_surrogate_cloud.csv, campaign_summary.json
runs\<variant>\<run_id>\   input.json, output.json, ntopcl.log, run_meta.json of every nTop run
campaign.log
```

`results/` in this repository holds the complete output of a dry run on
four synthetic variants (octet, gyroid, diamond, kelvin) so the deliverable can be
inspected before spending licence time. Those figures are watermarked
"SURROGATE DEMO - not nTop data" and must not be presented as results.

---

## Repository layout

```
cage_doe/       the package: config, discover, ntopcl (runner), design, surrogate, objectives,
                optimize, pipeline, plots, report, pptx_export, cli
mock/           mock_ntopcl.py (CLI-compatible stand-in), make_demo_folder.py
tests/          pytest suite incl. an end-to-end run with the mock  ->  python -m pytest tests
doe_config.example.json   the default configuration with every knob documented
```

## Caveats worth knowing

* The apparent modulus uses `geometry.footprint_area_mm2` and `height_mm`; set them to the
  real cage envelope, or expose a contact-area output.
* If nTop does not output a pore size, the pore criterion uses `kappa x cell - strut`
  (`geometry.pore_kappa` per lattice). Prefer a real pore measurement in the notebook.
* Stress at the 2000 N peak load is scaled linearly from the design-load FE (linear static).
* nTopCL uses one licence seat; keep `project.workers` at 1. If nTop reports a licence
  error, close the nTop GUI while the campaign runs.
* Reports never mix data sources: mock results are watermarked everywhere.
