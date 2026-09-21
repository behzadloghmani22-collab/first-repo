# HANDOFF — lattice lumbar fusion cage optimisation

**You are the third session on this project. Read this whole file before doing anything.**

You know nothing about this project yet. This file tells you what the engineering problem is,
what the user wants, what machines are involved, what code already exists, what is wrong with
that code, and exactly what to do. It assumes no prior knowledge of spinal implants, of nTop,
or of anything the previous sessions did.

| | |
|---|---|
| **Written** | 2026-09-21 |
| **Written by** | a Claude session in a cloud Linux container, with no access to any of the user's machines |
| **Written for** | a Claude Code session running on the user's PC `FaraGostar`, which can reach the nTop PC over SSH |
| **User** | Moein |
| **Repository** | `https://github.com/behzadloghmani22-collab/first-repo`, branch `claude/modest-brahmagupta-c6tqku` |
| **Supersedes** | the previous version of this file, which assumed nTop ran on the same PC as the session |

---

## 1. The engineering problem, from zero

### 1.1 What a lumbar interbody fusion cage is

When a spinal disc in the lower back is damaged beyond repair, a surgeon removes it and puts a
small implant — a **cage** — into the empty space between the two vertebrae. The cage does two
jobs. It holds the vertebrae apart at the right height so nerves are not pinched, and it acts
as a scaffold through which new bone grows, until the two vertebrae fuse into one solid piece
of bone. That fusion is the cure; the cage is the scaffold that makes it possible.

A cage of this kind is roughly the size of the last joint of your thumb. It sits under
substantial load: about 1000–1500 N during ordinary walking at the L4–L5 level, and 2000 N or
more when lifting.

### 1.2 Why the material is a problem

Two materials dominate, and each fails in a different way.

**Solid titanium** integrates beautifully with bone — bone cells like the surface, and the
implant becomes biologically anchored. But titanium alloy has a Young's modulus of about
110 GPa, while the vertebral bone around it is between 0.1 and 2 GPa (the spongy interior) and
15–20 GPa (the dense outer shell). The implant is therefore 50 to 1000 times stiffer than the
bone it sits against. It takes nearly all the load. The bone beside it, no longer loaded,
does what unloaded bone always does and **resorbs** — this is called **stress shielding**.
Weakened bone then lets the hard implant sink into the vertebral body, which is called
**subsidence**, and the disc height the surgery restored is lost again.

**PEEK**, a structural polymer, has a modulus around 3.6 GPa, which is close to bone. It does
not cause stress shielding. But bone does not bond to it; a fibrous layer forms at the
interface instead, and fusion is slower and less reliable.

### 1.3 Why a lattice solves it

Modern additive manufacturing lets you print titanium as a **lattice** — a repeating
three-dimensional scaffold of thin struts or curved sheets, mostly empty space, instead of a
solid block. This changes everything, because a lattice's stiffness is not the material's
stiffness. It is governed by how much material there is and how it is arranged, and it can be
tuned across orders of magnitude by changing the size of the repeating cell and the thickness
of its members.

So a lattice titanium cage can have **PEEK-like stiffness with titanium's biology**, and the
empty space inside is not wasted: it is where new bone grows. The pores also let blood vessels
in, which is what makes the new bone living tissue rather than scar.

This is the design the user is optimising.

### 1.4 The lattice types

There are many lattice topologies, and they behave differently at the same density:

- **Strut-based** lattices (octet truss, body-centred cubic, diamond, Kelvin) are networks of
  beams meeting at nodes. Some are *stretch-dominated* (octet), meaning the struts carry axial
  load and the lattice is stiff and strong for its weight. Others are *bending-dominated* (BCC),
  meaning struts bend under load, giving a more compliant, more forgiving structure.
- **Sheet-based / TPMS** lattices (gyroid, Schwarz diamond, Schwarz primitive) are smooth
  curved surfaces with no sharp nodes. They tend to have better fatigue behaviour, because
  fatigue cracks start at stress concentrations and TPMS surfaces have few of them, and they
  usually print with fewer defects.

**The user has four nTop files: the same cage geometry, built with four different lattice
types.** Which four is not recorded anywhere reliable — a previous session guessed
octet / gyroid / diamond / Kelvin when generating fake demonstration data, and those names are
placeholders, not facts. **One of your first jobs is to find out what the four actually are.**

---

## 2. What the user asked for

Quoting the original request, lightly cleaned up:

> I intend to run a DOE on multiple fusion cages embedded with lattice structures in order to
> make them optimised. There are four variations of the same file but with different lattice
> structures. Your task is to run every optimisation you see fit on every input parameter that
> is available to you, in order for the final resulting lumbar fusion cage to be optimal. What
> is regarded as optimal is up to you to figure out. How you do this is via nTopCL, modifying
> the input parameters and comparing the output parameters. When you are done comparing, save
> all your results in a folder you create in the same directory. Make sure you include enough
> illustrations and figures of your comparisons, since these results are to be used in my
> presentation. A version has already been run on the octet version — you can see what happened
> there, that will give you an idea. But don't just stop there. If you feel you could tweak
> things further, feel free to do that; all the choices are yours to make.

Unpacking that into requirements:

1. **DOE** means design of experiments: vary the input parameters systematically rather than
   guessing, so that the effect of each one, and of their interactions, can actually be measured.
2. **Every input parameter that is available.** Do not assume which parameters exist. Ask
   nTopCL what the notebooks expose, and sweep all of the ones that are meaningful.
3. **Via nTopCL.** The geometry and physics must be evaluated by nTop. This became an explicit
   and emphatic rule later in the conversation; see section 5.
4. **All four lattice types**, compared against each other.
5. **Define "optimal" yourself** and defend it. Section 7 is the previous session's definition;
   it is sound and you should keep it, but you own it now.
6. **Results in a new folder in the user's own directory**, with **many figures**, because this
   is going into a presentation.
7. There is an **existing run on one variant** to learn the format from.

The user has since added, forcefully, one more requirement, which overrides everything else:

> **If something can be done with nTopCL, doing it with anything else is unacceptable.**

---

## 3. The machines, and how to reach the one that matters

This is the part that broke the two previous attempts, so it is worth being precise.

```
  ┌─────────────────────────┐        SSH (port 22)        ┌──────────────────────────────┐
  │  FaraGostar             │  ────────────────────────►  │  DESKTOP-U932EHL             │
  │  the user's own PC      │        172.27.72.195        │  172.27.72.195               │
  │  YOU RUN HERE           │                             │  Windows 10 (19045)          │
  │  172.27.78.165/22       │  ◄────────────────────────  │  nTop 5.50.2 + nTopCL        │
  │  holds the SSH key      │        scp -O               │  the .ntop files live here   │
  └─────────────────────────┘                             └──────────────────────────────┘
```

You are the session on `FaraGostar`. nTop is **not** on your machine — it is on the second PC,
and you drive it over SSH. The user verified this path by hand on 2026-09-21 and wrote it up in
a file called `howtoconnect.md`. **Ask the user for that file and read it before you touch the
network**, because it contains the exact working incantations and a list of things that look
like they should work but do not.

The essentials from it, which you should still verify yourself:

| Fact | Value |
|---|---|
| Remote IP | `172.27.72.195` — **may change on DHCP renewal; confirm with the user** |
| Remote login | `desktop-u932ehl\moein salehi` — **the username contains a space** |
| Remote profile | `C:\Users\Moein Salehi` — **also contains a space** |
| nTop | `ntopcl --version` prints `nTop 5.50.2`; `C:\Program Files\nTopology\nTopology\` is on the remote PATH |
| Private key | `C:\Users\FaraGostar\.ssh\id_ed25519_remote` on your machine |
| Open ports | 22 (SSH), 3389 (RDP), 7070 (AnyDesk). 445/135/5985 are filtered. |

Hard-won lessons, all of which cost the user time:

- **The remote SFTP subsystem is broken.** Plain `scp` fails with `Connection closed`. Use
  **`scp -O`** (capital letter O), which selects the legacy SCP protocol.
- **Do not fight the space in the username.** PowerShell 5.1 mangles `-o User="moein salehi"`
  and `moein salehi@host`. Create an SSH config alias instead and use `ssh remote-ntop ...`.
  The config file that worked:
  ```
  Host remote-ntop
    HostName 172.27.72.195
    User "moein salehi"
    IdentityFile C:/Users/FaraGostar/.ssh/id_ed25519_remote
    IdentitiesOnly yes
    BatchMode yes
    ConnectTimeout 10
  ```
- **Work in a remote folder with no spaces**, such as `C:\ntop_sweep`. Copying via `scp -O`
  into a path containing a space is untested and likely to break. To get the notebooks there,
  prefer a **remote-to-remote copy** (`ssh remote-ntop "cmd /c copy \"C:\Users\Moein Salehi\Desktop\...\" C:\ntop_sweep\..."`),
  which never involves scp at all.
- **The remote default shell over SSH is `cmd.exe`**, and `powershell` is not on the PATH in
  SSH sessions. If you need PowerShell, call its full path
  `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe` and pass the script as
  `-EncodedCommand <base64-utf16le>` so quoting cannot break.
- **Never ask for, type, or store a password.** Key authentication only; `-o BatchMode=yes`
  makes SSH fail rather than prompt.
- **Never print or copy the private key.**
- **Long jobs may die when the SSH session ends.** A single `ntopcl` run takes roughly 35–160
  seconds, which is short enough to run synchronously in one SSH call. Verify this with a real
  run before you build a campaign on the assumption. If it turns out that runs do get killed,
  the fallback is to launch them detached on the remote (via `schtasks`, or WMI
  `([wmiclass]"Win32_Process").Create(...)`) and poll a results file with short SSH calls.
- Other user profiles exist on that PC (there is a `Lion`). Do not touch anything outside the
  folders you are told to use.
- `Test-NetConnection` hangs for about two minutes. To check reachability quickly, use a
  `Net.Sockets.TcpClient` with a 4-second sleep.

**A note on Claude Code's safety classifier:** it blocks sessions from creating SSH keys or
otherwise establishing persistent remote access. Do not try to work around that. The key
already exists; if something is missing, ask the user to run the setup commands themselves.

---

## 4. nTop and nTopCL, for someone who has not met them

**nTop** (formerly nTopology) is a CAD system built on **implicit modelling** rather than the
boundary representation most CAD uses. Geometry is defined by mathematical fields, which is why
it can handle a lattice with a million struts without the mesh falling over. A model is a
**notebook** (`.ntop`), which is a visual dataflow graph of blocks.

Two block types matter here:

- **Input blocks** expose a parameter (a number, a boolean, a text string) so it can be set
  from outside. These are the DOE factors.
- **Output blocks** expose a computed result so it can be read from outside. These are the
  responses.

**nTopCL** is the headless command-line runner. It needs an **nTop Automate licence** (a
different entitlement from the GUI licence — verify the remote has one before planning a long
campaign). Its two relevant modes:

```
ntopcl -t model.ntop                             # write template input/output JSON files
ntopcl -j in.json -o out.json model.ntop         # run the notebook with those inputs
```

Exit codes observed on 5.49/5.50:

| Code | Meaning | What it implies |
|---|---|---|
| 0 | success | outputs were written |
| 1 | argument error | **your command line is wrong** — fix the campaign, not the design |
| 2 | unsupported input type | **the notebook exposes a type nTopCL cannot set** — fix the notebook |
| 72 | build error | the geometry or simulation failed — this usually means the *design* is infeasible, e.g. struts so thick they merge into a solid, or so thin the lattice disconnects. **This is information, not a bug: it maps the infeasible region.** |
| 81 | JSON parse error | your input JSON is malformed |

Input types nTopCL can set: `bool`, `integer`, `scalar`/`real`, `text`, `file_path`, `vector`,
`point`, `enum`. It **cannot** set: `real_field`, `choice`, `box`. If a notebook exposes a
parameter you need as one of those, it has to be re-exposed as a settable type.

**A critical unknown you must resolve early.** The user's notes say *"Output components carry
no names — order is the only identifier."* If that is true of the output JSON that nTop 5.50.2
writes, then the existing code in this repository, which matches outputs **by name**, will not
work. Inspect a real `output.json` from a real run before trusting any parsing code.

Two `ntopcl` instances can run concurrently for about 1.45× throughput, if licensing permits.

---

## 5. THE GOVERNING RULE

> ### If a quantity can be produced by nTop through nTopCL, it must be produced by nTop through nTopCL. Computing it any other way is unacceptable.

This is the user's explicit instruction, stated after reviewing the previous session's work and
finding it had quietly broken the rule in several places.

**Python is a launcher and a bookkeeper. nTop is the engineering authority.**

Python may: choose which parameter combinations to try; write nTopCL input JSON; launch
`ntopcl`; read the returned output JSON; fit a surrogate model and search it to decide what to
run next; draw charts and write the report.

Python may **not**: compute, estimate, scale, extrapolate or approximate any physical or
geometric property of the cage.

**Every engineering number in the final deliverable must be traceable to an nTop Output block,
in an `output.json` written by `ntopcl` on disk.** If a number cannot be traced to such a file,
it does not belong in the results. If a quantity genuinely cannot be obtained from nTop, do not
substitute a calculation — record it as "not measured" and say so.

---

## 6. What is in the repository, and what is wrong with it

Clone it:

```
git clone -b claude/modest-brahmagupta-c6tqku https://github.com/behzadloghmani22-collab/first-repo.git
```

### 6.1 Contents

```
cage_doe/          the campaign driver (Python, ~2500 lines)
  config.py        thresholds, weights, factor ranges, nTop name aliases
  discover.py      finds .ntop files and their input templates, matches names
  ntopcl.py        subprocess wrapper for ntopcl: builds input JSON, runs, parses, caches
  transport.py     local-vs-SSH execution  *** UNTESTED, see 6.3 ***
  design.py        DOE plans: factorial, face-centred CCD, Latin hypercube, maximin infill
  surrogate.py     quadratic response surface + thin-plate RBF, chosen by leave-one-out error
  objectives.py    *** CONTAINS THE VIOLATIONS — must be gutted, see 6.4 ***
  optimize.py      differential evolution, Pareto fronts, Sobol sensitivity
  pipeline.py      orchestrates the whole campaign
  plots.py         41 figures
  report.py        HTML + Markdown report
  pptx_export.py   PowerPoint deck
  cli.py           python -m cage_doe {init,discover,run}
mock/              *** a Python FAKE of nTopCL — quarantine it, see 6.2 ***
results/           *** 133 runs of FABRICATED data — quarantine it, see 6.2 ***
tests/             12 tests, all passing (they test the plumbing, not the physics)
doe_config.example.json
README.md
HANDOFF.md         this file
```

### 6.2 The results in this repository are fake

**No nTop run has ever been executed for this project.** Every number in `results/` was produced
by `mock/mock_ntopcl.py`, a Python script that imitates nTopCL by evaluating Gibson–Ashby
lattice scaling laws. The first session ran in a cloud Linux container with no access to nTop,
no `.ntop` files, and no Windows. It built the framework and tested it against a stand-in.

Every figure in `results/` is watermarked "SURROGATE DEMO - not nTop data" for this reason.
**None of it may appear in the presentation.** Rename the folder to
`results_FAKE_python_surrogate/` so it cannot be confused with real output, and make
`mock/mock_ntopcl.py` impossible to invoke by accident.

Its one legitimate use is as a format reference: it shows what the deliverable should look
like — the figure set, the report structure, the CSV schema, the slide layout.

### 6.3 `transport.py` is untested

I wrote it in the cloud session after the user shared the connection guide, encoding the
verified recipes (config alias, `scp -O`, no-space work folder, encoded PowerShell, remote-to-
remote copy for space-containing paths). **Not one line of it has run against a real host.**
Use it as a starting point, verify each method against the real machine, and expect to fix it.

### 6.4 Engineering that Python does and nTop must do

These are the defects. Each must move into the nTop notebooks.

| # | Quantity | What the code does now (wrong) | What must happen |
|---|---|---|---|
| **V1** | **Apparent modulus** | Hand formula in Python: `E = (F / δ_max) · H / A`, using one max-displacement number plus a footprint area and height hard-coded in a config file. | nTop computes it: either a compression simulation with a platen, reporting reaction force and platen displacement, or nTop's lattice homogenisation, which additionally gives the off-axis moduli that were never assessed. |
| **V2** | **Stress at the 2000 N peak load** | **Linearly scaled in Python** from the 1200 N result: `σ_peak = σ_design × (2000/1200)`. No second simulation was ever run. | A genuine **second load case in nTop** at 2000 N. |
| **V3** | **Safety factors** | Python division `SF = σ_yield / σ_max`, on a single global maximum stress. | nTop produces a safety-factor field; output its **minimum**. A global max-stress scalar often sits on a mesh singularity at a boundary condition and is not a trustworthy basis. |
| **V4** | **Porosity / relative density** | Python: `1 − V_lattice / V_envelope`. | Computed inside the notebook from nTop volume measurements, exposed as an Output. |
| **V5** | **Mass** | Python: `V × 4.43 g/cm³`. | nTop mass block with Ti-6Al-4V assigned. |
| **V6** | **Pore size** | **An invented formula**: `pore ≈ κ · cell_size − strut_thickness`, where κ (0.55–0.65) is a fudge factor the previous session **made up**. This is the worst offender after V1, because pore size carries 22% of the objective weight. | nTop **measures** it: build the void body (design space minus lattice), run a maximum-inscribed-sphere or thickness analysis on it, output the representative pore diameter. |
| **V7** | **Minimum feature size** | Taken to equal the strut-thickness *input*. | nTop thickness analysis on the actual built solid. The input is not the realised minimum once struts blend at nodes and meet the shell. |
| **V8** | **Envelope volume, footprint, height** | Hard-coded numbers in the config (500 mm², 12 mm). | Measured in nTop from the real body. |
| **V9** | **Endplate contact area** | **Never measured**, despite being listed as a response. | nTop measures the real bearing area. It drives subsidence risk. |
| **V10** | **Manufacturability** | Only a thickness number. No overhang analysis, no powder-evacuation check. | nTop checks overhang angles against the build direction and confirms the void space is fully connected to the outside. A cage with sealed internal voids cannot be manufactured, whatever else it scores. |

### 6.5 What is genuinely reusable

The orchestration is sound. The subprocess wrapper, the run cache that lets a campaign resume
after interruption, the DOE plans, the surrogate fitting, the optimiser, the figures and the
report are all legitimate work for Python — nTopCL has no DOE generator, no response-surface
fitting and no plotting. **The defect is not the plumbing. It is that `objectives.py` computes
physics, and that the only dataset is fake.**

---

## 7. What "optimal" means

The previous session derived this definition. It is defensible and you should keep it as the
target set, but you own it now and may argue with it. Every threshold lives in
`doe_config.json` so it can be changed and the campaign re-scored without re-running nTop.

**The scoring method is a Derringer–Suich desirability.** Each criterion maps to a score between
0 and 1 (1 = inside the clinical target window, 0 = beyond a hard limit), and the criteria
combine by a **weighted geometric mean**. The geometric mean is the right choice because it
refuses to let an excellent score on one axis compensate for a failure on another: if any
criterion scores 0, the overall score is 0.

| # | Criterion | Target (score 1) | Hard limit (score 0 outside) | Weight | Why |
|---|---|---|---|---|---|
| C1 | **Apparent axial modulus** | 2–5 GPa, target 3 | 0.5–20 GPa | 0.30 | The central point of the whole design. Match bone and PEEK, avoid stress shielding and subsidence. See 1.2. |
| C2 | **Porosity** | 60–75 % | 40–90 % | 0.22 | Open volume for bone in-growth and graft packing. Below ~40 % there is too little space for bone; above ~90 % it cannot carry load or be printed. |
| C3 | **Pore size** | 500–800 µm | 300–1000 µm | 0.22 | The window for *vascularised* bone in-growth. Below ~300 µm in-growth is hypoxic and fibrous tissue forms instead of bone; above ~1000 µm cells struggle to bridge the gap. |
| C4 | **Fatigue safety factor** at 1200 N cyclic | ≥ 2 | ≥ 1 | 0.12 | Walking at L4–L5. Assessed against ~350 MPa endurance for **as-built** LPBF Ti-6Al-4V — surface roughness dominates fatigue in printed lattices, so do not use the wrought value. ASTM F2077 runs 5 million cycles. |
| C5 | **Yield safety factor** at 2000 N peak | ≥ 4 | ≥ 2 | 0.06 | Lifting. Yield ~950 MPa for heat-treated LPBF Ti-6Al-4V. ASTM F2077 static compression. |
| C6 | **Minimum realised thickness** | ≥ 0.45 mm | ≥ 0.30 mm | 0.04 | Laser powder-bed fusion cannot reliably resolve struts below ~0.3 mm; they come out undersized, rough, and with unpredictable fatigue life. |
| C7 | **Mass** | lowest in campaign | — | 0.02 | Tie-breaker. |
| C8 | **Surface area** | highest in campaign | — | 0.02 | Tie-breaker: more surface for osteo-conduction, within the pore-size constraint. |

### Criteria that should be added if the notebooks can measure them

The previous session could not address these, and their absence is a gap, not a decision:

- **C9 — Powder evacuation.** Every void must connect to the exterior. Un-sintered powder
  sealed inside an implant is a **hard fail**, not a penalty. Treat as a binary constraint.
- **C10 — Overhang self-support.** Down-facing surfaces below roughly 45° from the build plate
  need supports that cannot be removed from inside a lattice.
- **C11 — Endplate contact area.** Larger bearing area spreads load and lowers subsidence risk.
- **C12 — Off-axis stiffness.** The cage sees flexion, extension, lateral bending and torsion,
  not pure axial compression. Homogenisation gives the full stiffness tensor at no extra cost.
- **C13 — Expulsion / shear resistance** per ASTM F2077, if the notebooks can be extended.

---

## 8. The plan

### Phase 0 — Establish contact and find out what you are actually dealing with

Do not write any campaign code until this phase is finished and reported to the user.

1. Ask the user for `howtoconnect.md` and read it.
2. Confirm the remote is reachable; confirm the IP has not changed.
3. `ssh remote-ntop whoami` and `ssh remote-ntop "ntopcl --version"`.
4. **Confirm an Automate licence is available.** Without it nothing else matters.
5. **Find the four `.ntop` files.** List the user's Desktop folder on the remote. Record their
   real filenames and, from the names or by asking the user, what the four lattice types are.
   **Do not carry the octet/gyroid/diamond/Kelvin placeholders forward.**
6. **Find the existing run.** The user said one variant has already been run. Locate its input
   and output JSON, read both, and record the exact schema — key layout, whether values sit
   under `value` or `values`, whether units are carried, and critically **whether outputs have
   names or only positions**.
7. For each of the four notebooks, run `ntopcl -t <file>.ntop` and retrieve the template JSON.
   This is the authoritative list of what each notebook exposes. Build a table: every Input
   (name, type, current value, units) and every Output (name if any, type, units), for all four.
8. **Answer the decisive question: do these notebooks run a finite-element simulation, or do
   they only build geometry?** If there is no FE, there is no stress and no stiffness, and
   criteria C1, C4 and C5 — 48 % of the objective — cannot be evaluated at all. See section 9.
9. Time a single real run, on the notebook that already has a working input JSON. This number
   sets the budget for everything that follows.
10. **Report all of this to the user before continuing.** Include the input/output tables, the
    per-run time, whether FE exists, and your recommended plan and budget.

### Phase 1 — Make the notebooks the source of every number

This is the substantial engineering work, and it is collaborative: these are the user's
notebooks. **Ask before changing them.** Show the user what you intend to add and why. Verify
block names against the installed nTop 5.50.2 rather than assuming them from memory.

Each notebook should expose, as Outputs, everything the objective needs:

| Output | How nTop produces it | Fixes |
|---|---|---|
| Solid volume of the built cage (mm³) | volume measurement on the final body | — |
| Design-space / envelope volume (mm³) | volume measurement on the design space | V8 |
| **Porosity** | computed in-notebook from the two volumes | V4 |
| **Mass** (g) | mass block with Ti-6Al-4V assigned | V5 |
| Total surface area (mm²) | area measurement | — |
| **Endplate contact area** (mm²) | area of the real bearing surfaces | V9 |
| Height and footprint | measured, not assumed | V8 |
| **Apparent axial modulus** (GPa) | compression simulation, or lattice homogenisation (preferred — it also gives C12) | **V1** |
| Max von Mises stress at **1200 N** (MPa) | static FE, load case 1 | — |
| Max von Mises stress at **2000 N** (MPa) | static FE, **a real second load case** | **V2** |
| **Minimum yield safety factor** at 2000 N | safety-factor field vs 950 MPa, output the minimum | **V3** |
| **Minimum fatigue safety factor** at 1200 N | safety-factor field vs 350 MPa, output the minimum | **V3** |
| Max displacement at 1200 N (mm) | FE result | — |
| **Pore size** (µm) | build the void body, run max-inscribed-sphere / thickness analysis on it | **V6** |
| **Minimum realised thickness** (mm) | thickness analysis on the actual solid | **V7** |
| **Void connectivity** | confirm the void is one connected region reaching the exterior; output a boolean or a count of isolated regions | **C9** |
| **Worst overhang angle** (degrees) | overhang analysis against the build direction | **C10** |

Name the Inputs **consistently across all four notebooks**, because the driver matches names
across variants when comparing them.

### Phase 2 — Strip the physics out of the Python

Rewrite `cage_doe/objectives.py` into a pure pass-through and scoring layer:

- Delete every derived-quantity formula listed in 6.4.
- Read each quantity straight from the nTop outputs, converting units only.
- If a required quantity is missing from a run's output, that run is **incomplete**: mark it,
  exclude it from scoring, report it. **Never fall back to an estimate.** Delete the
  `geometry.pore_kappa` fudge factors from the config entirely.
- Keep the desirability scoring in Python. Mapping an nTop-measured number onto a 0–1 clinical
  preference is a decision rule, not physics, and belongs in the driver.
- Add the new constraints: closed voids fail outright (C9); record overhang angle (C10),
  contact area (C11), off-axis moduli (C12).
- Adapt the output parsing if outputs turn out to be positional rather than named (section 4).
- Update the tests to assert that **a missing nTop output never silently becomes an estimate**.

### Phase 3 — Run the campaign

1. Agree the budget with the user first, from the measured per-run time.
2. **Pilot on one variant** with a small design. Inspect the outputs for physical sanity —
   porosity strictly between 0 and 1, modulus in a believable range, stress not dominated by a
   boundary-condition singularity. Show the user. Only scale up once the pilot is clearly sound.
3. Run the full campaign across all four variants. The driver caches every run on disk, so it
   survives interruption and restarts where it stopped.
4. **Failed runs are data.** A design that exits 72 marks the infeasible region — struts merged
   into a solid, or a disconnected lattice. The driver already learns from these. Do not discard
   them; do not treat them as bugs.
5. **The reported optimum for each lattice must be a verified nTop run, never a surrogate
   prediction.** The pipeline already re-runs its best candidates in nTop; confirm the `source`
   column of `ranking.csv` reads `verified` for every variant.

### Phase 4 — Analyse honestly

- Compare the four lattices on the overall score and on every individual criterion.
- Report Sobol sensitivity indices, clearly labelled as computed **on the surrogate**.
- Check surrogate accuracy against the nTop-verified points. If errors are large, say so and
  run more nTop points rather than trusting the fit.
- Show the weight-robustness analysis, so the ranking can be defended when someone challenges
  the weighting.
- State plainly which criteria could not be measured.

### Phase 5 — Deliver

Write everything into a **new folder inside the user's own directory** on the machine where it
belongs, and confirm with the user where that should be — the nTop PC's
`C:\Users\Moein Salehi\Desktop\moein new files\`, or their own PC, or both. Deliver:

- `figures/` — the full figure set; this is for a presentation, so quantity and clarity both matter
- `presentation/` — the PowerPoint deck
- `report/` — HTML and Markdown summary
- `data/` — every run with inputs, nTop outputs and scores, as CSV
- `runs/` — the input JSON, output JSON and log of every single nTop evaluation, as evidence
- `SUMMARY.md` — see section 10

---

## 9. Decision points that need the user

Do not resolve these alone.

1. **If the notebooks have no FE simulation.** Then modulus, stress and both safety factors
   cannot be measured, and 48 % of the objective is unavailable. The options are: (a) add FE to
   the notebooks, which is real work and needs the user's agreement and probably their input on
   boundary conditions; (b) use nTop's lattice homogenisation for stiffness only, which gives
   C1 but not C4/C5; (c) restrict the study to geometric criteria and state clearly that
   structural performance was not assessed. **(c) is much weaker and the user should choose it
   knowingly, not by default.**
2. **If a run takes much longer than ~160 s.** The campaign arithmetic changes. Four variants ×
   ~36 runs at 5 minutes is about 12 hours; at 20 minutes it is two days. Tell the user the
   number before starting, not after.
3. **Before modifying any `.ntop` file.** They are the user's work.
4. **If the licence is GUI-only**, with no Automate entitlement — nothing can proceed headlessly.
5. **Where the final results folder should live.**

---

## 10. Required deliverable: `SUMMARY.md`

The user asked for this specifically. It exists so that for every single thing done, they can
tell **which application did it**. It must contain:

1. **A provenance table — the most important section.** One row per task, with columns:
   *Task | Application that performed it | Evidence on disk | nTop-computed or externally derived?*
   Every engineering quantity must name the nTop Output block that produced it and point at an
   `output.json` path. Anything not produced by nTop must be flagged, with a justification for
   why nTopCL could not do it.
2. **The nTopCL command line as actually verified on the remote**, with real flags and the
   measured wall-clock time of a typical run.
3. **What each notebook was changed to expose**, block by block, and whether the user approved
   each change.
4. **Campaign statistics:** runs executed, successes, failures and their causes, total time,
   licence issues.
5. **Results:** the ranking of the four lattices, recommended settings for each, every
   criterion value, with `verified` / `predicted` clearly marked.
6. **Criteria that could not be measured**, and why, with no substitute numbers.
7. **An explicit statement of whether any engineering quantity was computed outside nTop.**
   If the answer is "none", say so plainly — that is the goal state.
8. **Honest limitations:** mesh convergence status, whether the FE was linear, whether fatigue
   was assessed by endurance limit rather than cyclic simulation, and what physical testing
   would still be needed (ASTM F2077 static, dynamic and expulsion tests on printed specimens)
   before any of this becomes a clinical claim.

---

## 11. Working rules

- **Never fabricate a number.** If something did not run, say it did not run. The single worst
  outcome here is a plausible-looking figure that came from a formula instead of from nTop —
  that is exactly what went wrong before, and it is why the first two attempts were worthless.
- Ask before modifying the user's notebooks or anything outside the folders you were given.
- Delete probe and temporary files you create on the remote.
- Commit to git as you go, on the branch `claude/modest-brahmagupta-c6tqku`.
- When reporting, lead with what nTop measured. Mark anything derived or predicted as such.
- This is going into a presentation. The figures need to be legible, labelled, and honest about
  what is measurement and what is model.
