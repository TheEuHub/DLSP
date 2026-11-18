"""Generate the PC_EYE_OS computer: ALU, registers, decoder, CPU, machine.

Chip set (all built from the existing NAND-level library):

  CONST 1        one NAND with floating inputs -> constant 1
  MUX 8          2:1 8-bit multiplexer
  REG 4          4-bit master/slave register (edge triggered on LOAD)
  XOR 8          8-bit bitwise XOR
  ISZERO 8       8-bit zero detect
  DECODER 4 TO 16  4-bit opcode -> 16 one-hot control lines
  ALU 8          PASS B / ADD / AND / XOR
  CPU 8          program counter, X and A registers, colour registers,
                 ROM, control unit
  PC_EYE 8       the machine: CPU + RGB panel
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_hdmi import Chip, BUILTIN_OUT_PINS, load_registry, CHIPS_DIR

BUILTIN_OUT_PINS.update({"ROM 256x16": [1, 2], "8-4BIT": [1, 2], "4BIT D FLIP FLOP": None})


def pinchip(name, pinmap):
    """pin-name -> pin-id map for a chip we are about to place"""
    return pinmap


def and_n(c, reg, items):
    acc = items[0]
    for it in items[1:]:
        acc = c.gate("OND", reg, acc, it)
    return acc


def or_n(c, reg, items):
    acc = items[0]
    for it in items[1:]:
        acc = c.gate("OR", reg, acc, it)
    return acc


# ---------------------------------------------------------------- primitives
def build_const1(reg):
    c = Chip("CONST 1", {"r": 0.9, "g": 0.9, "b": 0.2, "a": 1})
    OUT = c.out("OUT")
    g = c.sub("NAND")            # both inputs left floating -> reads 1
    c.wire((g, 2), OUT)
    return c


def build_mux8(reg):
    c = Chip("MUX 8", {"r": 0.25, "g": 0.3, "b": 0.55, "a": 1})
    A, B, S = c.inp("IN A", 8), c.inp("IN B", 8), c.inp("SEL")
    O = c.out("OUT", 8)
    a, b = c.split(A, 8), c.split(B, 8)
    ns = c.inv(reg, S)
    bits = []
    for i in range(8):
        bits.append(c.gate("OR", reg, c.gate("OND", reg, a[i], ns),
                           c.gate("OND", reg, b[i], S)))
    c.wire(c.merge(8, bits), O)
    return c


def build_mux1(reg):
    c = Chip("MUX 1", {"r": 0.25, "g": 0.3, "b": 0.5, "a": 1})
    A, B, S = c.inp("IN A"), c.inp("IN B"), c.inp("SEL")
    O = c.out("OUT")
    ns = c.inv(reg, S)
    c.wire(c.gate("OR", reg, c.gate("OND", reg, A, ns),
                  c.gate("OND", reg, B, S)), O)
    return c


def build_mux4(reg):
    c = Chip("MUX 4", {"r": 0.25, "g": 0.3, "b": 0.5, "a": 1})
    A, B, S = c.inp("IN A", 4), c.inp("IN B", 4), c.inp("SEL")
    O = c.out("OUT", 4)
    a, b = c.split(A, 4), c.split(B, 4)
    ns = c.inv(reg, S)
    bits = []
    for i in range(4):
        bits.append(c.gate("OR", reg, c.gate("OND", reg, a[i], ns),
                           c.gate("OND", reg, b[i], S)))
    c.wire(c.merge(4, bits), O)
    return c


def build_reg1(reg):
    c = Chip("REG 1", {"r": 0.3, "g": 0.2, "b": 0.45, "a": 1})
    DATA, LOAD = c.inp("DATA"), c.inp("LOAD")
    MEM, NMEM = c.out("MEM"), c.out("-MEM")
    g = reg["D FLIP FLOP"]
    m, s, n = c.sub("D FLIP FLOP"), c.sub("D FLIP FLOP"), c.sub("NOT")
    c.wire(LOAD, (n, reg["NOT"]["IN"]))
    c.wire((n, reg["NOT"]["OUT"]), (m, g["LOAD"]))
    c.wire(LOAD, (s, g["LOAD"]))
    c.wire(DATA, (m, g["DATA"]))
    c.wire((m, g["MEM"]), (s, g["DATA"]))
    c.wire((s, g["MEM"]), MEM)
    c.wire((s, g["-MEM"]), NMEM)
    return c


def build_reg4(reg):
    c = Chip("REG 4", {"r": 0.3, "g": 0.2, "b": 0.45, "a": 1})
    DATA, LOAD = c.inp("DATA", 4), c.inp("LOAD")
    MEM, NMEM = c.out("MEM", 4), c.out("-MEM", 4)
    g = reg["4BIT D FLIP FLOP"]
    m, s, n = c.sub("4BIT D FLIP FLOP"), c.sub("4BIT D FLIP FLOP"), c.sub("NOT")
    c.wire(LOAD, (n, reg["NOT"]["IN"]))
    c.wire((n, reg["NOT"]["OUT"]), (m, g["LOAD"]))
    c.wire(LOAD, (s, g["LOAD"]))
    c.wire(DATA, (m, g["DATA"]))
    c.wire((m, g["MEM"]), (s, g["DATA"]))
    c.wire((s, g["MEM"]), MEM)
    c.wire((s, g["-MEM"]), NMEM)
    return c


def build_xor8(reg):
    c = Chip("XOR 8", {"r": 0.2, "g": 0.35, "b": 0.35, "a": 1})
    A, B = c.inp("IN A", 8), c.inp("IN B", 8)
    O = c.out("OUT", 8)
    a, b = c.split(A, 8), c.split(B, 8)
    c.wire(c.merge(8, [c.gate("XOR", reg, a[i], b[i]) for i in range(8)]), O)
    return c


def build_iszero8(reg):
    c = Chip("ISZERO 8", {"r": 0.2, "g": 0.35, "b": 0.2, "a": 1})
    I = c.inp("IN", 8)
    O = c.out("OUT")
    bits = c.split(I, 8)
    acc = or_n(c, reg, bits)
    c.wire(c.inv(reg, acc), O)
    return c


def build_decoder(reg):
    c = Chip("DECODER 4 TO 16", {"r": 0.35, "g": 0.25, "b": 0.2, "a": 1})
    INp = c.inp("IN", 4)
    outs = [c.out(f"O{k}") for k in range(16)]
    bits = c.split(INp, 4)
    nbits = [c.inv(reg, b) for b in bits]
    for k in range(16):
        lits = [bits[j] if (k >> j) & 1 else nbits[j] for j in range(4)]
        c.wire(and_n(c, reg, lits), outs[k])
    return c


def build_alu(reg):
    c = Chip("ALU 8", {"r": 0.25, "g": 0.4, "b": 0.3, "a": 1})
    A, B = c.inp("IN A", 8), c.inp("IN B", 8)
    OP0, OP1 = c.inp("OP0"), c.inp("OP1")
    O = c.out("OUT", 8)

    add = c.sub("8BIT FULL ADDER")
    g = reg["8BIT FULL ADDER"]
    c.wire(A, (add, g["IN A"]))
    c.wire(B, (add, g["IN B"]))
    asum = (add, g["SUM"])

    a, b = c.split(A, 8), c.split(B, 8)
    and8 = c.merge(8, [c.gate("OND", reg, a[i], b[i]) for i in range(8)])
    xor8 = c.merge(8, [c.gate("XOR", reg, a[i], b[i]) for i in range(8)])

    mg = reg["MUX 8"]
    low = c.sub("MUX 8")     # op0=0 -> B, op0=1 -> A+B
    c.wire(B, (low, mg["IN A"]))
    c.wire(asum, (low, mg["IN B"]))
    c.wire(OP0, (low, mg["SEL"]))
    high = c.sub("MUX 8")    # op0=0 -> AND, op0=1 -> XOR
    c.wire(and8, (high, mg["IN A"]))
    c.wire(xor8, (high, mg["IN B"]))
    c.wire(OP0, (high, mg["SEL"]))
    top = c.sub("MUX 8")     # op1 selects low/high group
    c.wire((low, mg["OUT"]), (top, mg["IN A"]))
    c.wire((high, mg["OUT"]), (top, mg["IN B"]))
    c.wire(OP1, (top, mg["SEL"]))
    c.wire((top, mg["OUT"]), O)
    return c


# ---------------------------------------------------------------- the CPU
def build_cpu(reg):
    """Single-cycle 8-bit CPU.

    Every state element is a master/slave register whose LOAD is the clock and
    whose data input is a 2:1 mux chain: the inner mux folds the write-enable
    in as (new value / own output), the outer mux forces 0 while POWER is low.
    Because the master captures during the low phase, the write-enable is
    sampled from exactly the instruction that is being executed.
    """
    c = Chip("CPU 8", {"r": 0.55, "g": 0.2, "b": 0.2, "a": 1})
    CLK, PWR = c.inp("CLK"), c.inp("POWER")
    ADDR = c.out("ADDR", 8)
    RO, GO, BO = c.out("R", 4), c.out("G", 4), c.out("B", 4)
    WR = c.out("WRITE")

    rom = c.sub("ROM 256x16")
    A, X, PC = c.sub("8BIT REG"), c.sub("8BIT REG"), c.sub("8BIT REG")
    Rr, Gr, Br = c.sub("REG 4"), c.sub("REG 4"), c.sub("REG 4")
    Z = c.sub("REG 1")
    alu = c.sub("ALU 8")
    xadd, padd = c.sub("8BIT FULL ADDER"), c.sub("8BIT FULL ADDER")
    muxX, muxPC = c.sub("MUX 8"), c.sub("MUX 8")
    dec = c.sub("DECODER 4 TO 16")
    xr, z0 = c.sub("XOR 8"), c.sub("ISZERO 8")
    one = c.sub("CONST 1")
    one8 = c.sub("1-8BIT")

    R8, R4, R1 = reg["8BIT REG"], reg["REG 4"], reg["REG 1"]
    RDEC, RA = reg["DECODER 4 TO 16"], reg["ALU 8"]
    RM8, RM4, RM1 = reg["MUX 8"], reg["MUX 4"], reg["MUX 1"]
    RAD = reg["8BIT FULL ADDER"]

    rst = c.inv(reg, PWR)

    def latch8(sub, r, val, we):
        """DATA = rst ? 0 : (we ? val : MEM) ; LOAD = CLK."""
        m, m2 = c.sub("MUX 8"), c.sub("MUX 8")
        c.wire(val, (m, RM8["IN A"]))
        c.wire((sub, r["MEM"]), (m, RM8["IN B"]))
        c.wire(c.inv(reg, we), (m, RM8["SEL"]))
        c.wire((m, RM8["OUT"]), (m2, RM8["IN A"]))
        c.wire(rst, (m2, RM8["SEL"]))
        c.wire((m2, RM8["OUT"]), (sub, r["DATA"]))
        c.wire(CLK, (sub, r["LOAD"]))

    def latch4(sub, r, val, we):
        m, m2 = c.sub("MUX 4"), c.sub("MUX 4")
        c.wire(val, (m, RM4["IN A"]))
        c.wire((sub, r["MEM"]), (m, RM4["IN B"]))
        c.wire(c.inv(reg, we), (m, RM4["SEL"]))
        c.wire((m, RM4["OUT"]), (m2, RM4["IN A"]))
        c.wire(rst, (m2, RM4["SEL"]))
        c.wire((m2, RM4["OUT"]), (sub, r["DATA"]))
        c.wire(CLK, (sub, r["LOAD"]))

    def latch1(sub, r, val, we):
        m, m2 = c.sub("MUX 1"), c.sub("MUX 1")
        c.wire(val, (m, RM1["IN A"]))
        c.wire((sub, r["MEM"]), (m, RM1["IN B"]))
        c.wire(c.inv(reg, we), (m, RM1["SEL"]))
        c.wire((m, RM1["OUT"]), (m2, RM1["IN A"]))
        c.wire(rst, (m2, RM1["SEL"]))
        c.wire((m2, RM1["OUT"]), (sub, r["DATA"]))
        c.wire(CLK, (sub, r["LOAD"]))

    # ---------------- fetch ----------------
    c.wire((PC, R8["MEM"]), (rom, 0))
    hi, lo = c.sub("8-4BIT"), c.sub("8-4BIT")
    c.wire((rom, 1), (hi, 0))
    c.wire((rom, 2), (lo, 0))
    opcode, op_hi = (hi, 1), (hi, 2)
    op_g, op_b = (lo, 1), (lo, 2)
    operand = (rom, 2)
    c.wire(opcode, (dec, RDEC["IN"]))
    d = {k: (dec, RDEC[f"O{k}"]) for k in range(16)}

    # ---------------- control ----------------
    we_A = or_n(c, reg, [d[1], d[9]])
    we_X = or_n(c, reg, [d[2], d[3]])
    we_C = d[5]
    we_Z = d[4]
    run = c.inv(reg, d[15])
    jump = or_n(c, reg, [d[7], c.gate("OND", reg, d[8], (Z, R1["MEM"]))])
    alu_op0 = or_n(c, reg, [d[9], d[11]])
    alu_op1 = or_n(c, reg, [d[10], d[11]])

    # ---------------- datapath ----------------
    c.wire((A, R8["MEM"]), (alu, RA["IN A"]))
    c.wire(operand, (alu, RA["IN B"]))
    c.wire(alu_op0, (alu, RA["OP0"]))
    c.wire(alu_op1, (alu, RA["OP1"]))
    latch8(A, R8, (alu, RA["OUT"]), we_A)

    c.wire((X, R8["MEM"]), (xadd, RAD["IN A"]))
    c.wire(operand, (xadd, RAD["IN B"]))
    c.wire((xadd, RAD["SUM"]), (muxX, RM8["IN A"]))
    c.wire(operand, (muxX, RM8["IN B"]))
    c.wire(d[2], (muxX, RM8["SEL"]))
    latch8(X, R8, (muxX, RM8["OUT"]), we_X)

    c.wire((one, reg["CONST 1"]["OUT"]), (one8, 7))
    c.wire((PC, R8["MEM"]), (padd, RAD["IN A"]))
    c.wire((one8, 8), (padd, RAD["IN B"]))
    c.wire((padd, RAD["SUM"]), (muxPC, RM8["IN A"]))
    c.wire(operand, (muxPC, RM8["IN B"]))
    c.wire(jump, (muxPC, RM8["SEL"]))
    latch8(PC, R8, (muxPC, RM8["OUT"]), run)

    c.wire((X, R8["MEM"]), (xr, reg["XOR 8"]["IN A"]))
    c.wire(operand, (xr, reg["XOR 8"]["IN B"]))
    c.wire((xr, reg["XOR 8"]["OUT"]), (z0, reg["ISZERO 8"]["IN"]))
    latch1(Z, R1, (z0, reg["ISZERO 8"]["OUT"]), we_Z)

    latch4(Rr, R4, op_hi, we_C)
    latch4(Gr, R4, op_g, we_C)
    latch4(Br, R4, op_b, we_C)

    c.wire((X, R8["MEM"]), ADDR)
    c.wire((Rr, R4["MEM"]), RO)
    c.wire((Gr, R4["MEM"]), GO)
    c.wire((Br, R4["MEM"]), BO)
    c.wire(d[6], WR)
    return c


def build_machine(reg):
    c = Chip("PC_EYE 8", {"r": 0.05, "g": 0.05, "b": 0.08, "a": 1})
    CLK = c.inp("CLK")
    PWR = c.inp("POWER")
    cpu = c.sub("CPU 8")
    scr = c.sub("RGB SCREEN")
    RC, RS = reg["CPU 8"], reg["RGB SCREEN"]
    c.wire(CLK, (cpu, RC["CLK"]))
    c.wire(PWR, (cpu, RC["POWER"]))
    for cpu_pin, scr_pin in (("ADDR", "ADDR"), ("R", "RED"), ("G", "GREEN"),
                             ("B", "BLUE"), ("WRITE", "WRITE")):
        c.wire((cpu, RC[cpu_pin]), (scr, RS[scr_pin]))
    c.wire(CLK, (scr, RS["CLOCK"]))
    c.wire(PWR, (scr, RS["ON"]))
    return c


ORDER = [build_const1, build_mux8, build_mux1, build_mux4, build_reg1, build_reg4, build_xor8, build_iszero8,
         build_decoder, build_alu, build_cpu, build_machine]


def main():
    reg = load_registry()
    for fn in ORDER:
        chip = fn(reg)
        d = chip.to_json(reg)
        json.dump(d, open(os.path.join(CHIPS_DIR, d["Name"] + ".json"), "w"), indent=2)
        reg[d["Name"]] = {p["Name"]: p["ID"] for p in d["InputPins"] + d["OutputPins"]}
        print(f"wrote {d['Name']:18} {len(d['InputPins']):2} in, {len(d['OutputPins']):2} out, "
              f"{len(d['SubChips']):3} subchips, {len(d['Wires']):4} wires")


if __name__ == "__main__":
    main()
