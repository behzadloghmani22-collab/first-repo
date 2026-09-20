"""cage_doe - Design-of-experiments and optimisation driver for nTop (nTopCL)
lattice lumbar interbody fusion cages.

The package runs a sequential experimentation campaign on every ``.ntop``
variant found under a root folder:

1. discover variants (one ``.ntop`` per lattice type) and their nTopCL input
   templates,
2. run a screening design, a response-surface design and space-filling runs
   through ``ntopcl.exe``,
3. fit surrogates, optimise a clinically motivated desirability score,
   adaptively add infill runs and verify the predicted optimum in nTop,
4. compare the lattice types and write figures, tables, a report and a deck.
"""

__version__ = "0.1.0"
