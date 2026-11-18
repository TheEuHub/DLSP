# DLSP

Digital Logic Sim project archive.

| Path | What it is |
| --- | --- |
| `PC_EYE_OS/` | Main library: 20 custom chips (NAND-based gates → adders → latches → 8-bit register → display driver). DLS 2.1.6. |
| `REFS/` | Scratch reference project: one chip showing the pinout of every built-in splitter, merger, bus and the RGB display. |
| `ANALYSIS.md` | Full review: format documentation, per-chip verification, and the defects found. |
| `tools/dlsp_sim.py` | Reader/simulator for the chip format — flattens any chip to NAND leaves and evaluates it. |

Quick start:

```bash
python3 - <<'PY'
import sys; sys.path.insert(0, 'tools')
import dlsp_sim as S
p = S.Project('PC_EYE_OS')
print(p.run('8BIT FULL ADDER', {'IN A': 200, 'IN B': 100}))  # {'SUM': 44, 'OF': 1}
PY
```

Headline issues (details in `ANALYSIS.md`):

1. `4 PIN LOCK` — the merge output is never wired to the chip's `OUT` pin, so the
   chip always returns 0.
2. `DISP` — all eight latch data inputs are unconnected (only `UNLOCK` is
   driven), and it embeds three of the broken `4 PIN LOCK` chips, so it can only
   ever display black.
