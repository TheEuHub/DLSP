# DLSP — Project Archive Review

Analysis of `Projects.zip` (unpacked at the repo root). Two Digital Logic Sim
projects: **`PC_EYE_OS`** (20 chips, plus 5 added in this pass) and **`REFS`** (1 chip).

Reviewed by flattening every chip to its built-in NAND leaves and simulating the
resulting netlists. All findings below are reproduced by `tools/dlsp_sim.py`.

---

## 1. What was in the archive

```
Projects.zip
├── PC_EYE_OS/                    20 custom chips as shipped (24 after this pass)
│   ├── ProjectDescription.json   project manifest (version, prefs, collections)
│   └── Chips/*.json              1 file per chip
└── REFS/                         1 custom chip, created 2026-11-18 16:28
    ├── ProjectDescription.json
    └── Chips/REFS.json
```

Both are **Digital Logic Sim** projects (`DLSVersion_LastSaved: 2.1.6`,
`EarliestCompatible: 2.0.0`). No top-level circuit is stored in this export —
the projects are purely **chip libraries**, so the deliverable artefact is the
reusable standard-cell set, not a finished machine.

---

## 2. The file format

Each chip is a JSON netlist. Structure (all fields observed in these files):

| Field | Meaning |
| --- | --- |
| `Name`, `NameLocation` | chip name + where the label is drawn |
| `ChipType` | `0` in every file (normal custom chip) |
| `Size` | body size in grid units |
| `Colour` | body tint `{r,g,b,a}` |
| `InputPins[]` / `OutputPins[]` | `Name`, `ID`, `Position`, **`BitCount`**, `Colour`, `ValueDisplayMode` |
| `SubChips[]` | placed instances: `Name`, `ID`, `Label`, `Position`, `OutputPinColourInfo`, `InternalData` |
| `Wires[]` | `SourcePinAddress` / `TargetPinAddress` = `{PinID, PinOwnerID}`, `ConnectionType`, `Points[]` |
| `Displays[]` | empty in both projects |

**Pin addressing.** A wire endpoint is `(PinOwnerID, PinID)`. `PinOwnerID` is
the *object* (a chip pin `ID`, or a subchip instance `ID`); `PinID` is the pin
inside that object. The chip's own pins are always addressed as `PinID: 0`.

**Built-in chip pin numbering** (inferred from the wiring, consistent across all
files):

| Builtin | Pins |
| --- | --- |
| `NAND` | in `0`, `1` → out `2` |
| `4-1BIT` / `8-1BIT` (splitter) | in `0` → out `1..N` |
| `1-4BIT` / `1-8BIT` (merger) | in `0..N-1` → out `N` |
| `8-4BIT` | in `0` → out `1` = high nibble, `2` = low nibble |
| `4-8BIT` | in `0` = high nibble, `1` = low nibble → out `2` |
| `BUS-n` / `BUS-TERMINUS-n` | paired through `InternalData: [peerId, 0]` |

**Bit order** (verified by exhaustive arithmetic tests): splitter output pin
`k` carries bit `N-k`; merger input pin `j` carries bit `N-1-j`. So a signal of
the same significance always sits at pin index `k` on the split side and `k-1`
on the merge side — this is why every multi-bit chip looks like it wires
`1→0, 2→1, 3→2, …`.

**Semantics.** Unconnected inputs read `0`. Every custom chip in both projects
bottoms out in `NAND` plus the bus helpers, which is what makes full flattening
and simulation possible.

---

## 3. Project `REFS` — a pinout reference card

One chip (`REFS`, 0.725 × 1.125) containing **13 built-ins and zero wires**:

* `1-4BIT`, `1-8BIT`, `4-1BIT`, `4-8BIT`, `8-1BIT` — the split/merge family
* `BUS-1`, `BUS-4`, `BUS-8` + `BUS-TERMINUS-1/4/8` — wired to each other only via `InternalData`
* `RGB DISPLAY`

with six loose pins (`IN` 1/4/8-bit, `OUT` 1/4/8-bit). Unconnected pins are
intentional here: the chip is a **lookup sheet** for built-in pin layouts, laid
out in a tidy column.

Supporting evidence that it is a scratch project: grid, snapping and straight
wires are all **off** (`Prefs_GridDisplayMode/Snapping/StraightWires: 0`), and
`AllCustomChipNames` contains only `REFS` — it is deliberately kept separate
from the working library.

---

## 4. Project `PC_EYE_OS` — the logic library

**Intent.** The name ("PC" + "EYE" + "OS") points at a computer with a display;
the contents are the bottom-up standard-cell library that such a machine would
be built from. `ChipCollections` groups the library into
`BASIC / IN-OUT / MERGE-SPLIT / BUS / DISPLAY / MEMORY / OTHER`, and the author
has starred 20 of them for quick access.

### 4.1 Layer cake

```
L0  NAND (builtin)  ─────────────────────────────────────────────┐
L1  NOT, OND(AND), NOND(NAND)        1 NAND each (OND uses 2)    │
L2  OR, NOR, XOR, XNOR               3–5 NANDs, pure NAND nets    │
    ── 1-bit datapath ──                                          │
L2  HALF ADDER, FULL ADDER           6 / 15 NANDs                 │
L3  4BIT FULL ADDER                  ripple of 4 full adders     │
L4  8BIT FULL ADDER                  ripple of 2 4-bit adders    │
    ── storage ──                                                │
L2  D FLIP FLOP (gated D latch)      NOR latch + load gates      │
L3  4BIT / 8BIT D FLIP FLOP          parallel latches            │
L5  8BIT REG                         master/slave = edge-triggered
L2  T FLIP FLOP                      toggling bistable            │
    ── masking + display ──                                      │
L2  1/4/8 PIN LOCK                   AND-mask gated buffers      │
L3  RGB SCREEN                       RGB DISPLAY + power lamp    │
    ── HDMI link ──                                             │
L3  HDMI TYPE A                      19-pin connector + receivers│
L4  TMDS 9B ENCODER / DECODER        8b<->9b transition coding   │
L5  HDMI DISPLAY                     connector → decode → screen │
```

### 4.2 Chip inventory (verified behaviour)

| Chip | In → Out | Built from | NAND leaves | Verdict |
| --- | --- | --- | --- | --- |
| `NOT` | 1 → 1 | NAND | 1 | ✅ truth table |
| `OND` (AND) | 2 → 1 | 2×NAND | 2 | ✅ truth table |
| `NOND` (NAND) | 2 → 1 | NAND | 1 | ✅ truth table |
| `OR` | 2 → 1 | 3×NAND (De Morgan) | 3 | ✅ truth table |
| `NOR` | 2 → 1 | OR + inverter | 4 | ✅ truth table |
| `XOR` | 2 → 1 | 4×NAND | 4 | ✅ truth table |
| `XNOR` | 2 → 1 | XOR + inverter | 5 | ✅ truth table |
| `HALF ADDER` | A,B → SUM,C OUT | XOR + AND | 6 | ✅ all 4 cases |
| `FULL ADDER` | A,B,C IN → SUM,C OUT | 2×XOR, 2×AND, OR | 15 | ✅ all 8 cases |
| `4BIT FULL ADDER` | A,B[4],C IN → SUM[4],C OUT | 4× full adder + splitters | 60 | ✅ all 512 cases |
| `8BIT FULL ADDER` | A,B[8] → SUM[8],OF | 2× 4-bit adder | 120 | ✅ all 65 536 cases |
| `D FLIP FLOP` | DATA,LOAD → MEM,-MEM | NOR latch + load gates | 13 | ✅ latch: transparent at LOAD=1, holds at LOAD=0 |
| `4BIT D FLIP FLOP` | DATA[4],LOAD → MEM[4],-MEM[4] | 4× D latch | 52 | ✅ holds, -MEM = ~MEM |
| `8BIT D FLIP FLOP` | DATA[8],LOAD → MEM[8],-MEM[8] | 2× 4-bit DFF | 104 | ✅ holds, -MEM = ~MEM |
| `8BIT REG` | DATA[8],LOAD → MEM[8],-MEM[8] | 2× 8-bit DFF (master/slave) | 209 | ✅ captures on LOAD rising edge |
| `T FLIP FLOP` | IN → OUT,-OUT | 8×NAND + 2×NOT | 10 | ✅ toggles on every IN rising edge, holds on falling |
| `1 PIN LOCK` | IN,UNLOCK → OUT | AND mask | 2 | ✅ OUT = IN ∧ UNLOCK |
| `4 PIN LOCK` | IN[4],UNLOCK → OUT[4] | 4× AND + split/merge | 8 | ❌ **OUT pin never wired** |
| `8 PIN LOCK` | IN[8],UNLOCK → OUT[8] | 8× AND + split/merge | 16 | ✅ OUT = IN ∧ UNLOCK |
| `RGB SCREEN` | ADDR[8],R[4],G[4],B[4],WRITE,CLOCK,ON → R/G/B OUT[4] | RGB DISPLAY + 2 masking gates + LED | 4 | ✅ new, replaces `DISP` |
| `HDMI TYPE A` | 19 connector pins → D0/D1/D2[8], CLK, LINK | 6 splitters, 24 XOR + 23 AND | 150 | ✅ 19-pin pinout, link detect |
| `TMDS 9B ENCODER` | D[8],DE → Q[8],Q8 | XOR/XNOR chain + popcount adder tree | 353 | ✅ matches HDMI 1.4 §5.4.2 stage 1, all 256 bytes |
| `TMDS 9B DECODER` | Q[8] → D[8] | XOR/XNOR chain | 113 | ✅ round-trips all 256 bytes |
| `HDMI DISPLAY` | 19 HDMI pins + ADDR/WRITE/CLOCK/ON | connector → 3 decoders → screen | 493 | ✅ wired, compiles |

**Colour convention.** The primitive layer uses pure RGB primaries (red `NOT`,
blue `OND`, magenta `NOND`, cyan `XOR`, yellow `NOR`, green `OR`, white `XNOR`);
every composite chip gets its own unique tint. **Build order** from file
timestamps: gates (Nov 5) → adders (Nov 7) → flip-flops/register (Nov 7–8) →
pin locks and `DISP` (Nov 18) — i.e. the display driver was the newest,
unfinished work. `DISP` has since been deleted and replaced by `RGB SCREEN`
plus the HDMI link chips described in §5.

---

## 5. Findings

### 🔴 B1 — `4 PIN LOCK` has no output connection

`4 PIN LOCK.json` has 13 wires where its siblings need 14. The merge chip
`1-4BIT` (id `796558869`) receives all four masked bits on pins `0..3`, but
**pin `4` is never wired to the chip's `OUT` pin** (`1960317531`).

The fix is the one wire every other member of the family has — in `8 PIN LOCK`
it is the last wire, `1-8BIT` output pin `8` → chip `OUT`:

```json
{ "SourcePinAddress": { "PinID": 8, "PinOwnerID": <1-8BIT id> },
  "TargetPinAddress": { "PinID": 0, "PinOwnerID": 1593448837 } }   // 8 PIN LOCK OUT
```

For `4 PIN LOCK` the equivalent is `PinID: 4` of the `1-4BIT` instance
(id `796558869`) → `PinID: 0` of `OUT` (id `1960317531`).

Effect: the chip returns `0` for **every** input — a silent failure, no width or
dangling-reference error. Fix: add one wire `1-4BIT(pin 4) → OUT(pin 0)`.

### ✅ `DISP` — deleted, replaced by `RGB SCREEN` + the HDMI link

The original `DISP` was dead twice over: none of its eight latch data inputs were
wired (its only input drove `UNLOCK`), and it embedded three copies of the broken
`4 PIN LOCK`. It has been removed and replaced by five new chips.

**What the built-in `RGB DISPLAY` actually is** (read out of the engine source,
`BuiltinChipCreator.CreateDisplayRGB` + `Simulator.cs`):

| Pin | Name | Width |
| --- | --- | --- |
| 0 | `ADDRESS` | 8 bits (256 pixels, 16×16) |
| 1/2/3 | `RED` / `GREEN` / `BLUE` | 4 bits each (4096 colours) |
| 4/5/6/7 | `RESET` / `WRITE` / `REFRESH` / `CLOCK` | 1 bit |
| 8/9/10 | `R OUT` / `G OUT` / `B OUT` | 4 bits (read-back) |

It is double-buffered: on a `CLOCK` rising edge it clears the back buffer when
`RESET` is high, otherwise stores the colour at `ADDRESS` when `WRITE` is high,
and copies back→front when `REFRESH` is high.

#### `RGB SCREEN` (replaces `DISP`)

Seven inputs, three outputs:

```
ADDR[8]  RED[4]  GREEN[4]  BLUE[4]  WRITE  CLOCK  ON   ──▶  R OUT[4] G OUT[4] B OUT[4]
```

* `ON` gates both `WRITE` and `CLOCK` with an AND, so nothing can be written
  while the screen is off.
* `REFRESH` is tied to the gated `WRITE`, so a pixel appears the moment it is
  written (write-through). Unwire that one wire if you want manual refresh.
* An **LED sits inside the chip on `ON`** — that is the on/off indicator — and
  `R/G/B OUT` read back the colour at `ADDR`.

#### `HDMI TYPE A` — the cord

All **19 pins of a Type A HDMI connector**, in physical order and with the standard
names: `1 TMDS D2+`, `2 D2 SHIELD`, `3 TMDS D2-`, … `13 CEC`, `14 RESERVED`,
`15 SCL`, `16 SDA`, `17 GND`, `18 +5V`, `19 HPD`.

It also does what a receiver front-end does: each TMDS pair is compared bit-by-bit
(XOR), the XORs are AND-reduced, and `LINK` goes high only when all three data
pairs are complementary, the clock pair is complementary, and `+5V` is present.
`D0/D1/D2` output the recovered bytes. The shields, `CEC`, `SCL`, `SDA`, `GND` and
`HPD` are deliberately unconnected reference pins.

#### `TMDS 9B ENCODER` / `TMDS 9B DECODER` — the "more than five gates" chip

This is the new building block the brief asked for: a chip that cannot be made
from a handful of gates. It implements **stage 1 of the TMDS 8b/10b link encoding
from HDMI 1.4 §5.4.2** — the transition-minimised 8b→9b mapping:

```
q_m[0] = D[0]
q_m[i] = q_m[i-1] XNOR D[i]   when D[0] = 0
q_m[i] = q_m[i-1] XOR  D[i]   when D[0] = 1
N1{D}  = number of ones in D
q_m[8] = 1 when N1 < 4, or when N1 = 4 and D[0] = 1; otherwise 0
```

`N1` is computed with a popcount tree: four half adders, three 4-bit adders.
The XOR/XNOR choice is a two-AND/one-OR multiplexer per bit. `DE` gates the output
to zero for control periods. That is **353 NAND gates** in `TMDS 9B ENCODER`
(113 in the decoder) — comfortably past "more than five".

Verified exhaustively against a reference implementation of the spec:

* encoder == reference for all 256 input bytes × `DE` ∈ {0,1} — **PASS**
* `ENCODER → DECODER` returns the original byte for all 256 values — **PASS**
* connector: complementary pairs + `+5V` → `LINK=1` and correct data; shorted
  pairs or missing `+5V` → `LINK=0` — **PASS**

#### `HDMI DISPLAY`

The assembled monitor: the 19 connector pins plus `ADDR`, `WRITE`, `CLOCK`, `ON`.
Inside, the connector feeds three decoders (channel 0 = blue, 1 = green, 2 = red,
as in HDMI), the decoded 8-bit channels are truncated to the panel's 4-bit
channels with `8-4BIT` splitters, and the result drives `RGB SCREEN`.

**Modelling caveat.** A real HDMI link serialises the 10-bit TMDS symbols at ten
times the pixel rate; DLS has no way to express a rate domain, so each lane here
carries one symbol as a parallel bus (8 data bits + separate `Q8`). The connector
pinout, the differential pairs, the channel-to-colour mapping and the encoding
arithmetic are faithful; the serializer/deserializer is out of scope, and the
running-disparity (9b→10b) stage is not modelled — `Q8` is exposed for a future
stage.

### 🟡 R1 — "D FLIP FLOP" is a latch, not a flip-flop

`D FLIP FLOP` is transparent while `LOAD = 1` and holds while `LOAD = 0`
(verified statefully). That makes `4BIT/8BIT D FLIP FLOP` level-sensitive too —
hard to reason about in a synchronous design. `8BIT REG` is the only proper
edge-triggered part (master loads on `LOAD = 0`, slave on `LOAD = 1`, so it
captures on the rising edge). Suggest renaming to `D LATCH` / keeping the
`REG` name for the edge-triggered version.

### 🟡 R2 — no reset anywhere

No chip has a `RESET`/`CLEAR` input, and the latches power up in a metastable
state (both `MEM` and `-MEM` settle equal on a cold start). A register file or
PC built from these parts would start in an undefined state. Adding a clear
input to the D latch (extra gate on the NOR latch) would fix the whole family.

### 🟡 R3 — `8BIT FULL ADDER` cannot be cascaded

`4BIT FULL ADDER` exposes `C IN`, but `8BIT FULL ADDER` drops it (the low-nibble
adder's `C IN` is simply unconnected — harmless, implicit `0`, but it blocks
chaining). Without a `C IN`/`C OUT` pair you can't build 16-bit adders, and you
can't do subtract-on-add (`A + ~B + 1`) at 8 bits either. Worth exposing
`C IN` for symmetry.

### 🔵 N1 — naming

* `OND` = AND, `NOND` = NAND, `XNOR`/`NOR` inverted — the `O`/`N` prefix scheme
  is self-consistent but non-obvious.
* `* PIN LOCK` are **not** locks/memory: each is just `IN ∧ UNLOCK`, a gated
  buffer. The name suggests latching.
* `8BIT REG` and `4BIT/8BIT D FLIP FLOP` have identical ports and pin names
  (`DATA/LOAD → MEM/-MEM`) but different timing behaviour.

---

## 6. What is still missing for a working "PC_EYE_OS"

Present: gate library, adders, latches, edge-triggered register, display stub.
Absent:

| Missing block | Note |
| --- | --- |
| Multiplexer / demux / decoder | none defined; needed for ALU op select, register select, instruction decode |
| ALU | only adders; no AND/OR/XOR/SUB selectable path |
| Program counter, instruction register, control unit | none |
| Memory in use | `ROM 256×16` and `BUS-1/4/8` are available but unused in `PC_EYE_OS` (BUS only appears in `REFS`) |
| Tri-state busing | `3-STATE BUFFER` and `BUS-*` never used in the library |
| Clock usage | `CLOCK`/`PULSE` unused; nothing is clocked |
| Reset | see R2 |
| Raster/address generator | the screen takes `ADDR`/`WRITE`/`CLOCK` from outside; nothing sweeps the 16×16 grid yet |

The natural next steps are: fix `4 PIN LOCK`, add a multiplexer/decoder layer,
add `C IN` to the 8-bit adder, then wire a control unit around `8BIT REG` and
the `ROM 256×16`.

---

## 7. Tooling added

`tools/dlsp_sim.py` — a small reader/simulator for this project format:

```bash
python3 - <<'PY'
import sys; sys.path.insert(0, 'tools')
import dlsp_sim as S
p = S.Project('PC_EYE_OS')
print(p.run('8BIT FULL ADDER', {'IN A': 200, 'IN B': 100}))   # {'SUM': 44, 'OF': 1}
print(p.run('XOR', {'IN A': 1, 'IN B': 1}))                   # {'OUT': 0}
PY
```

* `Project(root).run(chip, {inputs})` — settle a chip and read its outputs.
* `Project(root).sim(chip).step({inputs})` — state-preserving stepping, needed
  for latches/registers/toggle logic (bistables keep their value between steps).
* `Project(root).compile(chip)` — the flattened NAND/bus netlist.

Note: a plain static `run()` starts every net at `0`, so memory-holding states
look "unstable" from cold. That is a limitation of cold-start evaluation, not a
defect in the chips — use `sim()` for sequential parts.
