# Lumbar fusion cage - lattice DOE and optimisation - DOE and optimisation summary

Campaign ran 2026-09-20 19:17:13 to 2026-09-20 19:18:46. Results folder: `<root>/DOE_results`.

> **These results come from the surrogate stand-in (mock_ntopcl.py), NOT from nTop. Re-run with the real ntopcl.exe on the .ntop files to obtain presentable numbers.**

## 1. What 'optimal' means here

Each nTop run is scored with a Derringer-Suich desirability: every criterion is mapped to 0-1 (1 inside its clinical target window, 0 beyond a hard limit) and the criteria are combined with a weighted geometric mean, so a design that violates any hard limit scores 0.

| criterion | full desirability | hard limit | weight | rationale |
|---|---|---|---|---|
| Apparent modulus E_app = (F/delta) x H / A | 2.0-5.0 GPa (target 3.0 GPa) | 0.5-20.0 GPa | 0.3 | PEEK/bone-like stiffness: limits stress shielding and subsidence while supporting fusion |
| Porosity | 60%-75% | 40%-90% | 0.22 | open volume for bone in-growth and graft |
| Pore size | 500-800 um | 300-1000 um | 0.22 | vascularised osteogenesis window |
| Yield safety factor at 2000 N | >= 4.0 | >= 2.0 | 0.06 | static strength, sigma_y = 950 MPa |
| Fatigue safety factor at 1200 N | >= 2.0 | >= 1.0 | 0.12 | endurance limit 350 MPa |
| Strut / sheet thickness | >= 0.45 mm | >= 0.3 mm | 0.04 | LPBF Ti-6Al-4V printability |
| Mass | lowest in campaign | - | 0.02 | tie-breaker |
| Surface area | highest in campaign | - | 0.02 | tie-breaker (osteo-conduction) |

![Desirability functions that define 'optimal'](figures/fig00_objective_definition.png)

*Desirability functions that define 'optimal'*

## 2. Campaign design

- Factors: Cell Size 1.5-4.0 mm, Strut Thickness 0.3-0.9 mm, Shell Thickness 0.5-1.5 mm
- Phases per variant: prior runs imported -> screening (full_factorial, 3 centre points) -> response surface (ccd_face) -> 10 Latin-hypercube runs -> 2 x 3 adaptive infill runs (exploit / explore / diversify) -> verification of the top 3 predicted designs in nTop.
- Surrogates: quadratic response surface and thin-plate RBF per response; the one with the lower leave-one-out error is used, their disagreement drives exploration.
- Optimiser: differential evolution + Nelder-Mead polish on the surrogate desirability, penalised by the estimated probability that nTop fails (self-intersecting / solid lattice).
- Loads and material: design load 1200 N, peak 2000 N, E = 110.0 GPa, yield 950.0 MPa, endurance 350.0 MPa, density 4.43 g/cm^3; footprint 500.0 mm^2, height 12.0 mm.

| variant | runs_total | successful | failed | feasible |
|---|---|---|---|---|
| fusion_cage_diamond | 15 | 13 | 2 | 1 |
| fusion_cage_gyroid | 17 | 15 | 2 | 4 |
| fusion_cage_kelvin | 18 | 16 | 2 | 3 |
| fusion_cage_octet | 19 | 17 | 2 | 6 |

![Runs per variant](figures/fig01_run_summary.png)

*Runs per variant*

## 3. Ranking of the lattice types

| rank | variant | lattice | D_recommended | source | Cell Size | Strut Thickness | Shell Thickness | E_app_GPa | porosity | pore_um | sf_yield | sf_fatigue | mass_g | max_stress_MPa |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | fusion_cage_kelvin | kelvin | 0.9746 | verified | 2.083 | 0.45 | 0.5 | 5.428 | 0.6637 | 800 | 7.808 | 4.794 | 8.94 | 73 |
| 2 | fusion_cage_octet | octet | 0.9619 | verified | 2.273 | 0.45 | 0.5 | 5.988 | 0.6986 | 800 | 10.77 | 6.616 | 8.01 | 52.9 |
| 3 | fusion_cage_gyroid | gyroid | 0.6887 | verified | 2.116 | 0.3444 | 0.6395 | 11.81 | 0.5272 | 819.3 | 17.22 | 10.58 | 12.57 | 33.09 |
| 4 | fusion_cage_diamond | diamond | 0.5068 | best observed run | 2.75 | 0.9 | 1 | 11.43 | 0.4391 | 887.5 | 17.53 | 10.76 | 14.91 | 32.52 |

**Recommendation: fusion_cage_kelvin (kelvin)** with D = 0.975 (verified). Settings: Cell Size = 2.08 mm, Strut Thickness = 0.45 mm, Shell Thickness = 0.5 mm.

![Overall desirability and component scores](figures/fig02_ranking.png)

*Overall desirability and component scores*

![Clinical metrics of each recommended design](figures/fig03_compare_metrics.png)

*Clinical metrics of each recommended design*

![Desirability profile](figures/fig04_radar.png)

*Desirability profile*

![Ranking stability under weight perturbation](figures/fig05_weight_robustness.png)

*Ranking stability under weight perturbation*

![Stiffness-matching vs porosity trade-off across lattice types](figures/fig06_pareto_all_variants.png)

*Stiffness-matching vs porosity trade-off across lattice types*

![Recommended factor settings](figures/fig07_optimum_settings.png)

*Recommended factor settings*

## 4. Surrogate accuracy at the verified optima

| variant | candidate | D predicted | D nTop | E_app pred (GPa) | E_app nTop | porosity pred | porosity nTop | stress pred (MPa) | stress nTop |
|---|---|---|---|---|---|---|---|---|---|
| fusion_cage_gyroid | alt1 | 0.6794 | 0.6887 | 12.08 | 11.81 | 0.5232 | 0.5272 | 32.76 | 33.09 |
| fusion_cage_gyroid | alt2 | 0.6555 | 0.6375 | 11.81 | 12.2 | 0.5309 | 0.5252 | 33.61 | 33.5 |
| fusion_cage_kelvin | optimum | 0.9746 | 0.9746 | 5.429 | 5.428 | 0.6636 | 0.6637 | 73 | 73 |
| fusion_cage_kelvin | alt2 | 0.9475 | 0.949 | 6.059 | 5.968 | 0.6418 | 0.6523 | 65.9 | 66.09 |
| fusion_cage_octet | optimum | 0.9619 | 0.9619 | 5.99 | 5.988 | 0.6986 | 0.6986 | 52.9 | 52.9 |
| fusion_cage_octet | alt1 | 0.9446 | 0.9474 | 5.673 | 5.51 | 0.7211 | 0.7284 | 55.77 | 57.5 |

![Predicted vs verified](figures/fig08_predicted_vs_verified.png)

*Predicted vs verified*

## 5. Per-variant results

### fusion_cage_diamond (diamond)

Recommended design (best observed run): Cell Size = 2.75, Strut Thickness = 0.9, Shell Thickness = 1; D = 0.507; E_app = 11.43 GPa, porosity = 0.44, pore = 888 um (estimated from cell/strut size), SF yield = 17.53, SF fatigue = 10.76, mass = 14.91 g.

| Modulus match | Porosity | Pore size | Fatigue margin | Yield margin | Printability | Low mass | Surface area |
|---|---|---|---|---|---|---|---|
| 0.5716 | 0.1954 | 0.5625 | 1 | 1 | 1 | 0.5554 | 0.4903 |

| factor | Sobol first-order | Sobol total |
|---|---|---|
| Cell Size | 0.03176 | 0.284 |
| Strut Thickness | 0.682 | 0.9555 |
| Shell Thickness | 0 | 0.03462 |

| response | n | chosen | order | rsm_r2 | rsm_adj_r2 | loo_rmse_rel | log |
|---|---|---|---|---|---|---|---|
| lattice_volume | 13 | rbf | quadratic | 0.992 | 0.9679 | 0.6083 | False |
| mass | 13 | rbf | quadratic | 0.992 | 0.9679 | 0.6083 | False |
| surface_area | 13 | rbf | quadratic | 0.9799 | 0.9196 | 0.6954 | False |
| max_stress | 13 | rsm | quadratic | 0.9979 | 0.9918 | 0.3231 | True |
| max_displacement | 13 | rbf | quadratic | 0.9914 | 0.9657 | 0.5555 | True |
| min_thickness | 13 | rbf | quadratic | 1 | 1 | 6.115e-16 | False |

![fusion_cage_diamond: Response surfaces](figures/fusion_cage_diamond_fig13_response_surfaces.png)

*fusion_cage_diamond: Response surfaces*

![fusion_cage_diamond: Main effects](figures/fusion_cage_diamond_fig11_main_effects.png)

*fusion_cage_diamond: Main effects*

![fusion_cage_diamond: Interactions](figures/fusion_cage_diamond_fig12_interactions.png)

*fusion_cage_diamond: Interactions*

![fusion_cage_diamond: Pareto front](figures/fusion_cage_diamond_fig14_pareto.png)

*fusion_cage_diamond: Pareto front*

![fusion_cage_diamond: Sensitivity](figures/fusion_cage_diamond_fig15_sensitivity.png)

*fusion_cage_diamond: Sensitivity*

![fusion_cage_diamond: Sampled designs](figures/fusion_cage_diamond_fig10_design_space.png)

*fusion_cage_diamond: Sampled designs*

![fusion_cage_diamond: Convergence](figures/fusion_cage_diamond_fig16_convergence.png)

*fusion_cage_diamond: Convergence*

![fusion_cage_diamond: Surrogate fit](figures/fusion_cage_diamond_fig17_model_fit.png)

*fusion_cage_diamond: Surrogate fit*

nTop outputs used: `Lattice Volume` -> lattice_volume, `Envelope Volume` -> envelope_volume, `Mass` -> mass, `Surface Area` -> surface_area, `Max von Mises Stress` -> max_stress, `Max Displacement` -> max_displacement, `Minimum Thickness` -> min_thickness

### fusion_cage_gyroid (gyroid)

Recommended design (verified): Cell Size = 2.12, Strut Thickness = 0.344, Shell Thickness = 0.639; D = 0.689; E_app = 11.81 GPa, porosity = 0.53, pore = 819 um, SF yield = 17.22, SF fatigue = 10.58, mass = 12.57 g.

| Modulus match | Porosity | Pore size | Fatigue margin | Yield margin | Printability | Low mass | Surface area |
|---|---|---|---|---|---|---|---|
| 0.546 | 0.6361 | 0.9035 | 1 | 1 | 0.296 | 0.6428 | 0.5502 |

| factor | Sobol first-order | Sobol total |
|---|---|---|
| Cell Size | 0 | 0.4631 |
| Strut Thickness | 0.6199 | 1 |
| Shell Thickness | 0.007446 | 0.05977 |

| response | n | chosen | order | rsm_r2 | rsm_adj_r2 | loo_rmse_rel | log |
|---|---|---|---|---|---|---|---|
| lattice_volume | 15 | rsm | quadratic | 0.9956 | 0.9877 | 0.3009 | False |
| mass | 15 | rsm | quadratic | 0.9956 | 0.9877 | 0.301 | False |
| surface_area | 15 | rbf | quadratic | 0.9969 | 0.9914 | 0.2667 | False |
| max_stress | 15 | rsm | quadratic | 0.9998 | 0.9993 | 0.0609 | True |
| max_displacement | 15 | rsm | quadratic | 0.9987 | 0.9964 | 0.1275 | True |
| pore_size | 15 | rbf | quadratic | 1 | 1 | 3.215e-05 | False |
| min_thickness | 15 | rbf | quadratic | 1 | 1 | 4.919e-16 | False |

![fusion_cage_gyroid: Response surfaces](figures/fusion_cage_gyroid_fig13_response_surfaces.png)

*fusion_cage_gyroid: Response surfaces*

![fusion_cage_gyroid: Main effects](figures/fusion_cage_gyroid_fig11_main_effects.png)

*fusion_cage_gyroid: Main effects*

![fusion_cage_gyroid: Interactions](figures/fusion_cage_gyroid_fig12_interactions.png)

*fusion_cage_gyroid: Interactions*

![fusion_cage_gyroid: Pareto front](figures/fusion_cage_gyroid_fig14_pareto.png)

*fusion_cage_gyroid: Pareto front*

![fusion_cage_gyroid: Sensitivity](figures/fusion_cage_gyroid_fig15_sensitivity.png)

*fusion_cage_gyroid: Sensitivity*

![fusion_cage_gyroid: Sampled designs](figures/fusion_cage_gyroid_fig10_design_space.png)

*fusion_cage_gyroid: Sampled designs*

![fusion_cage_gyroid: Convergence](figures/fusion_cage_gyroid_fig16_convergence.png)

*fusion_cage_gyroid: Convergence*

![fusion_cage_gyroid: Surrogate fit](figures/fusion_cage_gyroid_fig17_model_fit.png)

*fusion_cage_gyroid: Surrogate fit*

nTop outputs used: `Lattice Volume` -> lattice_volume, `Envelope Volume` -> envelope_volume, `Mass` -> mass, `Surface Area` -> surface_area, `Max von Mises Stress` -> max_stress, `Max Displacement` -> max_displacement, `Pore Diameter` -> pore_size, `Minimum Thickness` -> min_thickness

### fusion_cage_kelvin (kelvin)

Recommended design (verified): Cell Size = 2.08, Strut Thickness = 0.45, Shell Thickness = 0.5; D = 0.975; E_app = 5.43 GPa, porosity = 0.66, pore = 800 um (estimated from cell/strut size), SF yield = 7.81, SF fatigue = 4.79, mass = 8.94 g.

| Modulus match | Porosity | Pore size | Fatigue margin | Yield margin | Printability | Low mass | Surface area |
|---|---|---|---|---|---|---|---|
| 0.9714 | 1 | 1 | 1 | 1 | 1 | 0.778 | 0.5486 |

| factor | Sobol first-order | Sobol total |
|---|---|---|
| Cell Size | 0 | 0.3783 |
| Strut Thickness | 0.4885 | 1 |
| Shell Thickness | 0.005573 | 0.05133 |

| response | n | chosen | order | rsm_r2 | rsm_adj_r2 | loo_rmse_rel | log |
|---|---|---|---|---|---|---|---|
| lattice_volume | 16 | rbf | quadratic | 0.9844 | 0.9609 | 0.5828 | False |
| mass | 16 | rbf | quadratic | 0.9844 | 0.9609 | 0.5828 | False |
| surface_area | 16 | rbf | quadratic | 0.9805 | 0.9512 | 0.6404 | False |
| max_stress | 16 | rbf | quadratic | 0.9957 | 0.9892 | 0.412 | True |
| max_displacement | 16 | rbf | quadratic | 0.9851 | 0.9627 | 0.5751 | True |
| min_thickness | 16 | rbf | quadratic | 1 | 1 | 4.361e-16 | False |

![fusion_cage_kelvin: Response surfaces](figures/fusion_cage_kelvin_fig13_response_surfaces.png)

*fusion_cage_kelvin: Response surfaces*

![fusion_cage_kelvin: Main effects](figures/fusion_cage_kelvin_fig11_main_effects.png)

*fusion_cage_kelvin: Main effects*

![fusion_cage_kelvin: Interactions](figures/fusion_cage_kelvin_fig12_interactions.png)

*fusion_cage_kelvin: Interactions*

![fusion_cage_kelvin: Pareto front](figures/fusion_cage_kelvin_fig14_pareto.png)

*fusion_cage_kelvin: Pareto front*

![fusion_cage_kelvin: Sensitivity](figures/fusion_cage_kelvin_fig15_sensitivity.png)

*fusion_cage_kelvin: Sensitivity*

![fusion_cage_kelvin: Sampled designs](figures/fusion_cage_kelvin_fig10_design_space.png)

*fusion_cage_kelvin: Sampled designs*

![fusion_cage_kelvin: Convergence](figures/fusion_cage_kelvin_fig16_convergence.png)

*fusion_cage_kelvin: Convergence*

![fusion_cage_kelvin: Surrogate fit](figures/fusion_cage_kelvin_fig17_model_fit.png)

*fusion_cage_kelvin: Surrogate fit*

nTop outputs used: `Lattice Volume` -> lattice_volume, `Envelope Volume` -> envelope_volume, `Mass` -> mass, `Surface Area` -> surface_area, `Max von Mises Stress` -> max_stress, `Max Displacement` -> max_displacement, `Minimum Thickness` -> min_thickness

### fusion_cage_octet (octet)

Recommended design (verified): Cell Size = 2.27, Strut Thickness = 0.45, Shell Thickness = 0.5; D = 0.962; E_app = 5.99 GPa, porosity = 0.70, pore = 800 um (estimated from cell/strut size), SF yield = 10.77, SF fatigue = 6.62, mass = 8.01 g.

| Modulus match | Porosity | Pore size | Fatigue margin | Yield margin | Printability | Low mass | Surface area |
|---|---|---|---|---|---|---|---|
| 0.9341 | 1 | 1 | 1 | 1 | 1 | 0.8127 | 0.4911 |

| factor | Sobol first-order | Sobol total |
|---|---|---|
| Cell Size | 0 | 0.3606 |
| Strut Thickness | 0.5867 | 1 |
| Shell Thickness | 0.002732 | 0.03213 |

| response | n | chosen | order | rsm_r2 | rsm_adj_r2 | loo_rmse_rel | log |
|---|---|---|---|---|---|---|---|
| lattice_volume | 17 | rbf | quadratic | 0.9835 | 0.9624 | 0.5879 | False |
| mass | 17 | rbf | quadratic | 0.9835 | 0.9624 | 0.5878 | False |
| surface_area | 17 | rsm | quadratic | 0.9796 | 0.9533 | 0.6633 | False |
| max_stress | 17 | rbf | quadratic | 0.9967 | 0.9924 | 0.3299 | True |
| max_displacement | 17 | rsm | quadratic | 0.9955 | 0.9896 | 0.3108 | True |
| min_thickness | 17 | rbf | quadratic | 1 | 1 | 5.983e-16 | False |

![fusion_cage_octet: Response surfaces](figures/fusion_cage_octet_fig13_response_surfaces.png)

*fusion_cage_octet: Response surfaces*

![fusion_cage_octet: Main effects](figures/fusion_cage_octet_fig11_main_effects.png)

*fusion_cage_octet: Main effects*

![fusion_cage_octet: Interactions](figures/fusion_cage_octet_fig12_interactions.png)

*fusion_cage_octet: Interactions*

![fusion_cage_octet: Pareto front](figures/fusion_cage_octet_fig14_pareto.png)

*fusion_cage_octet: Pareto front*

![fusion_cage_octet: Sensitivity](figures/fusion_cage_octet_fig15_sensitivity.png)

*fusion_cage_octet: Sensitivity*

![fusion_cage_octet: Sampled designs](figures/fusion_cage_octet_fig10_design_space.png)

*fusion_cage_octet: Sampled designs*

![fusion_cage_octet: Convergence](figures/fusion_cage_octet_fig16_convergence.png)

*fusion_cage_octet: Convergence*

![fusion_cage_octet: Surrogate fit](figures/fusion_cage_octet_fig17_model_fit.png)

*fusion_cage_octet: Surrogate fit*

nTop outputs used: `Lattice Volume` -> lattice_volume, `Envelope Volume` -> envelope_volume, `Mass` -> mass, `Surface Area` -> surface_area, `Max von Mises Stress` -> max_stress, `Max Displacement` -> max_displacement, `Minimum Thickness` -> min_thickness

## 6. Files

- `data/runs_all.csv` - every run with inputs, nTop outputs, derived metrics and desirabilities
- `data/ranking.csv`, `data/optima.csv` - recommended designs
- `data/model_diagnostics.csv`, `data/sensitivity_sobol.csv`
- `data/<variant>_surrogate_cloud.csv` - 3000 surrogate evaluations per variant (Pareto clouds)
- `runs/<variant>/<run_id>/` - input.json, output.json and ntopcl.log of each nTop run
- `figures/` - all PNG figures at 200 dpi
- `presentation/` - PowerPoint deck of the figures
- `report/discovery.md` - what was found in the folder and how names were matched
