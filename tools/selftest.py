#!/usr/bin/env python3
"""Self-test for the PC_EYE_OS machine.

    python3 tools/selftest.py [--fast]

Checks every new OS chip against its truth table, then boots the kernel and
asserts the resulting frame. Exit code is 0 only if everything passes, so this is
the regression test for the whole OS.
"""
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dlsp_sim as S
import kernel as K

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHIPS = os.path.join(ROOT, "PC_EYE_OS")

fails = []


def check(name, got, want):
    ok = got == want
    if not ok:
        fails.append((name, got, want))
    return ok


def run(p, chip, cin):
    return p.run(chip, cin)


def test_logic(p):
    check("CONST 1", run(p, "CONST 1", {}), {"OUT": 1})
    for s in range(2):
        for a in range(2):
            for b in range(2):
                got = run(p, "MUX 1", {"IN A": a, "IN B": b, "SEL": s})["OUT"]
                check("MUX 1 s=%d a=%d b=%d" % (s, a, b), got, b if s else a)


def test_mux(p):
    vals = [0x00, 0x0F, 0xF0, 0xA5, 0xFF, 0x5A]
    for sel in (0, 1):
        for a in vals:
            for b in vals:
                check("MUX 8 %02X/%02X s=%d" % (a, b, sel),
                      run(p, "MUX 8", {"IN A": a, "IN B": b, "SEL": sel})["OUT"],
                      b if sel else a)
    for sel in (0, 1):
        for a in range(16):
            for b in (0, 5, 10, 15):
                check("MUX 4 %X/%X s=%d" % (a, b, sel),
                      run(p, "MUX 4", {"IN A": a, "IN B": b, "SEL": sel})["OUT"],
                      b if sel else a)


def test_xor_isz(p):
    for a in range(0, 256, 17):
        for b in range(0, 256, 17):
            check("XOR 8 %02X^%02X" % (a, b), run(p, "XOR 8", {"IN A": a, "IN B": b})["OUT"], a ^ b)
    for a in range(256):
        check("ISZERO 8 %02X" % a, run(p, "ISZERO 8", {"IN": a})["OUT"], 1 if a == 0 else 0)


def test_decoder(p):
    for k in range(16):
        out = run(p, "DECODER 4 TO 16", {"IN": k})
        for j in range(16):
            check("DECODER %d -> O%d" % (k, j), out["O%d" % j], 1 if j == k else 0)


def test_alu(p):
    ops = {0: lambda a, b: b, 1: lambda a, b: (a + b) & 0xFF,
           2: lambda a, b: a & b, 3: lambda a, b: a ^ b}
    for op in range(4):
        for a in (0, 1, 15, 128, 200, 255):
            for b in (0, 1, 7, 100, 255):
                check("ALU 8 op%d %d,%d" % (op, a, b),
                      run(p, "ALU 8", {"IN A": a, "IN B": b, "OP0": op & 1, "OP1": op >> 1})["OUT"],
                      ops[op](a, b))


def test_registers(p):
    # REG 1 / REG 4 are master-slave: capture on the rising edge of LOAD.
    sim = p.sim("REG 4")
    sim.step({"DATA": 5, "LOAD": 0})
    sim.step({"DATA": 5, "LOAD": 1})
    sim.step({"DATA": 9, "LOAD": 0})
    check("REG 4 holds", sim.read()["MEM"], 5)


def test_cpu(p):
    """A tiny program exercising LDX / ADDX / CMPX / JZ / SETC / PIX."""
    words, _ = K.assemble("""
        SETC #0xABC
        LDX #2
    loop: PIX
        ADDX #1
        CMPX #4
        JZ  done
        JMP loop
    done: LDX #99
    """)
    p.rom = [0] * 256
    for i, w in enumerate(words):
        p.rom[i] = w
    sim = p.sim("CPU 8")
    seen = []
    for _ in range(40):
        sim.step({"CLK": 0, "POWER": 1})
        sim.step({"CLK": 1, "POWER": 1})
        r = sim.read()
        if r["WRITE"]:
            seen.append((r["ADDR"], r["R"], r["G"], r["B"]))
    check("CPU writes 2,3", [s[0] for s in seen], [2, 3])
    check("CPU colour", set((s[1], s[2], s[3]) for s in seen), {(0xA, 0xB, 0xC)})
    check("CPU reached done", sim.read()["ADDR"], 99)


def test_boot(p, fast):
    p.load_rom(os.path.join(ROOT, "tools", "kernel.hex"))
    sim = p.sim("PC_EYE 8")
    n = 400 if fast else 3400

    def tick(k):
        for _ in range(k):
            sim.step({"CLK": 0, "POWER": 1})
            sim.step({"CLK": 1, "POWER": 1})

    tick(120)
    fb = sim.framebuffer()
    check("POST is flooding", sum(1 for v in fb if (v & 0xFFF) == 0xFFF) > 0, True)

    tick(n - 120)
    fb = sim.framebuffer()
    if not fast:
        amber = sum(1 for v in fb if (v & 15, (v >> 4) & 15, (v >> 8) & 15) == (15, 8, 0))
        check("frame pixels", amber, 60)
        check("palette", {v for v in fb} <= {0x421, 0x08F, 0x0F0}, True)
        check("cursor on", fb[136], 0x0F0)
        check("settled", sim.settled, True)
    return sim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="skip the long boot assertions")
    args = ap.parse_args()
    p = S.Project(CHIPS)

    for fn in (test_logic, test_mux, test_xor_isz, test_decoder, test_alu,
               test_registers, test_cpu):
        before = len(fails)
        fn(p)
        print("%-14s %s" % (fn.__name__, "PASS" if len(fails) == before else "FAIL"))

    before = len(fails)
    sim = test_boot(p, args.fast)
    print("%-14s %s" % ("test_boot", "PASS" if len(fails) == before else "FAIL"))

    for name, got, want in fails[:20]:
        print("  %-28s got %r want %r" % (name, got, want))
    print("\n%d failure(s)" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
