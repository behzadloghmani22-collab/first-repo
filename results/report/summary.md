# Lumbar fusion cage - lattice DOE and optimisation - DOE and optimisation summary

Campaign ran 2026-09-20 19:22:44 to 2026-09-20 19:24:31. Results folder: `<root>/DOE_results`.

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
| fusion_cage_diamond | 33 | 30 | 3 | 10 |
| fusion_cage_gyroid | 33 | 31 | 2 | 11 |
| fusion_cage_kelvin | 33 | 31 | 2 | 11 |
| fusion_cage_octet | 34 | 32 | 2 | 16 |

![Runs per variant](figures/fig01_run_summary.png)

*Runs per variant*

## 3. Ranking of the lattice types

| rank | variant | lattice | D_recommended | source | Cell Size | Strut Thickness | Shell Thickness | E_app_GPa | porosity | pore_um | sf_yield | sf_fatigue | mass_g | max_stress_MPa |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | fusion_cage_diamond | diamond | 0.9793 | verified | 1.923 | 0.4497 | 0.5 | 5.183 | 0.6715 | 800 | 9.326 | 5.727 | 8.731 | 61.12 |
| 2 | fusion_cage_kelvin | kelvin | 0.9748 | verified | 2.083 | 0.45 | 0.5 | 5.428 | 0.6637 | 800 | 7.808 | 4.794 | 8.94 | 73 |
| 3 | fusion_cage_octet | octet | 0.9621 | verified | 2.273 | 0.45 | 0.5 | 5.988 | 0.6986 | 800 | 10.77 | 6.616 | 8.01 | 52.9 |
| 4 | fusion_cage_gyroid | gyroid | 0.724 | verified | 2.051 | 0.3282 | 0.5 | 11.44 | 0.5463 | 800 | 16.06 | 9.862 | 12.06 | 35.49 |

**Recommendation: fusion_cage_diamond (diamond)** with D = 0.979 (verified). Settings: Cell Size = 1.92 mm, Strut Thickness = 0.45 mm, Shell Thickness = 0.5 mm.

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
| fusion_cage_diamond | optimum | 0.9789 | 0.9793 | 5.21 | 5.183 | 0.6697 | 0.6715 | 60.8 | 61.12 |
| fusion_cage_diamond | alt1 | 0.9587 | 0.9567 | 5.208 | 5.306 | 0.6722 | 0.6711 | 61.95 | 59.7 |
| fusion_cage_diamond | alt2 | 0.9562 | 0.9572 | 6.054 | 5.996 | 0.6423 | 0.6457 | 52.92 | 52.84 |
| fusion_cage_gyroid | optimum | 0.7118 | 0.724 | 11.62 | 11.44 | 0.5378 | 0.5463 | 35.02 | 35.49 |
| fusion_cage_gyroid | alt1 | 0.6765 | 0.689 | 12.25 | 11.81 | 0.5246 | 0.5272 | 33 | 33.09 |
| fusion_cage_gyroid | alt2 | 0.6477 | 0.6565 | 12.9 | 12.64 | 0.507 | 0.5094 | 31.23 | 31.76 |
| fusion_cage_kelvin | optimum | 0.9748 | 0.9748 | 5.429 | 5.428 | 0.6637 | 0.6637 | 73 | 73 |
| fusion_cage_kelvin | alt1 | 0.951 | 0.9537 | 6.556 | 6.424 | 0.6303 | 0.639 | 60.89 | 63.01 |
| fusion_cage_kelvin | alt2 | 0.9445 | 0.9492 | 6.224 | 5.968 | 0.6455 | 0.6523 | 64.91 | 66.09 |
| fusion_cage_octet | optimum | 0.9606 | 0.9621 | 6.058 | 5.988 | 0.6983 | 0.6986 | 52.9 | 52.9 |
| fusion_cage_octet | alt1 | 0.9438 | 0.9475 | 5.72 | 5.51 | 0.7266 | 0.7284 | 55.81 | 57.5 |
| fusion_cage_octet | alt2 | 0.9383 | 0.9386 | 7.129 | 7.105 | 0.6451 | 0.6466 | 44.58 | 44.59 |

![Predicted vs verified](figures/fig08_predicted_vs_verified.png)

*Predicted vs verified*

## 5. Per-variant results

### fusion_cage_diamond (diamond)

Recommended design (verified): Cell Size = 1.92, Strut Thickness = 0.45, Shell Thickness = 0.5; D = 0.979; E_app = 5.18 GPa, porosity = 0.67, pore = 800 um (estimated from cell/strut size), SF yield = 9.33, SF fatigue = 5.73, mass = 8.73 g.

| Modulus match | Porosity | Pore size | Fatigue margin | Yield margin | Printability | Low mass | Surface area |
|---|---|---|---|---|---|---|---|
| 0.9878 | 1 | 1 | 1 | 1 | 0.998 | 0.7934 | 0.5358 |

| factor | Sobol first-order | Sobol total |
|---|---|---|
| Cell Size | 0.02432 | 0.3158 |
| Strut Thickness | 0.7205 | 1 |
| Shell Thickness | 0.00417 | 0.01214 |

| response | n | chosen | order | rsm_r2 | rsm_adj_r2 | loo_rmse_rel | log |
|---|---|---|---|---|---|---|---|
| lattice_volume | 30 | rbf | quadratic | 0.9894 | 0.9846 | 0.1717 | False |
| mass | 30 | rbf | quadratic | 0.9894 | 0.9846 | 0.1717 | False |
| surface_area | 30 | rbf | quadratic | 0.9798 | 0.9707 | 0.1833 | False |
| max_stress | 30 | rbf | quadratic | 0.9884 | 0.9832 | 0.1777 | True |
| max_displacement | 30 | rbf | quadratic | 0.9786 | 0.969 | 0.197 | True |
| min_thickness | 30 | rbf | quadratic | 1 | 1 | 6.952e-16 | False |

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

Recommended design (verified): Cell Size = 2.05, Strut Thickness = 0.328, Shell Thickness = 0.5; D = 0.724; E_app = 11.44 GPa, porosity = 0.55, pore = 800 um, SF yield = 16.06, SF fatigue = 9.86, mass = 12.06 g.

| Modulus match | Porosity | Pore size | Fatigue margin | Yield margin | Printability | Low mass | Surface area |
|---|---|---|---|---|---|---|---|
| 0.5707 | 0.7315 | 1 | 1 | 1 | 0.188 | 0.6737 | 0.5723 |

| factor | Sobol first-order | Sobol total |
|---|---|---|
| Cell Size | 0 | 0.4528 |
| Strut Thickness | 0.6233 | 1 |
| Shell Thickness | 0.006723 | 0.05332 |

| response | n | chosen | order | rsm_r2 | rsm_adj_r2 | loo_rmse_rel | log |
|---|---|---|---|---|---|---|---|
| lattice_volume | 31 | rbf | quadratic | 0.9908 | 0.9869 | 0.1847 | False |
| mass | 31 | rbf | quadratic | 0.9908 | 0.9869 | 0.1847 | False |
| surface_area | 31 | rsm | quadratic | 0.9927 | 0.9896 | 0.1501 | False |
| max_stress | 31 | rsm | quadratic | 0.9971 | 0.9959 | 0.09595 | True |
| max_displacement | 31 | rsm | quadratic | 0.9944 | 0.9919 | 0.1244 | True |
| pore_size | 31 | rsm | quadratic | 1 | 1 | 5.301e-05 | False |
| min_thickness | 31 | rbf | quadratic | 1 | 1 | 8.233e-16 | False |

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
| 0.9714 | 1 | 1 | 1 | 1 | 1 | 0.7859 | 0.5486 |

| factor | Sobol first-order | Sobol total |
|---|---|---|
| Cell Size | 0 | 0.3947 |
| Strut Thickness | 0.6086 | 1 |
| Shell Thickness | 0.003662 | 0.006072 |

| response | n | chosen | order | rsm_r2 | rsm_adj_r2 | loo_rmse_rel | log |
|---|---|---|---|---|---|---|---|
| lattice_volume | 31 | rbf | quadratic | 0.9851 | 0.9787 | 0.2126 | False |
| mass | 31 | rbf | quadratic | 0.9851 | 0.9787 | 0.2127 | False |
| surface_area | 31 | rbf | quadratic | 0.9789 | 0.9699 | 0.1988 | False |
| max_stress | 31 | rbf | quadratic | 0.9716 | 0.9594 | 0.2171 | True |
| max_displacement | 31 | rbf | quadratic | 0.9812 | 0.9731 | 0.2254 | True |
| min_thickness | 31 | rbf | quadratic | 1 | 1 | 6.609e-16 | False |

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
| 0.9341 | 1 | 1 | 1 | 1 | 1 | 0.8193 | 0.4911 |

| factor | Sobol first-order | Sobol total |
|---|---|---|
| Cell Size | 0 | 0.3542 |
| Strut Thickness | 0.6528 | 1 |
| Shell Thickness | 0 | 0.01666 |

| response | n | chosen | order | rsm_r2 | rsm_adj_r2 | loo_rmse_rel | log |
|---|---|---|---|---|---|---|---|
| lattice_volume | 32 | rsm | quadratic | 0.9858 | 0.98 | 0.2363 | False |
| mass | 32 | rsm | quadratic | 0.9858 | 0.98 | 0.2362 | False |
| surface_area | 32 | rbf | quadratic | 0.9746 | 0.9643 | 0.2746 | False |
| max_stress | 32 | rbf | quadratic | 0.9906 | 0.9868 | 0.1524 | True |
| max_displacement | 32 | rbf | quadratic | 0.9936 | 0.991 | 0.1725 | True |
| min_thickness | 32 | rbf | quadratic | 1 | 1 | 8.081e-16 | False |

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
