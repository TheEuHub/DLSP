"""Minimal Digital Logic Sim (DLS 2.1.6) netlist simulator.

Every custom chip in these projects bottoms out in built-in NAND gates plus
built-in bus split/merge helpers, so chips can be flattened and evaluated.
Unconnected inputs read as 0 (DLS default).

Bus convention observed in these projects:
  4-1BIT / 8-1BIT  (splitter): input pin 0, output pins 1..N ; pin k = bit (N-k)
  1-4BIT / 1-8BIT  (merge):    input pins 0..N-1, output pin N ; pin j = bit (N-1-j)
  8-4BIT           (nibble split, 8 in): out pin 1 = high nibble, out pin 2 = low
  4-8BIT           (nibble merge):       in pin 0 = high nibble, in pin 1 = low
"""
import json, glob, os, collections

SPLITSRC = {"4-1BIT": 4, "8-1BIT": 8}
SPLIT    = {"1-4BIT": 4, "1-8BIT": 8}
NIBSPLIT = {"8-4BIT": 8}
NIBMERGE = {"4-8BIT": 8}
NAND_IN, NAND_OUT = (0, 1), 2


class Compiled:
    def __init__(self):
        self.nets = []          # list of net ids
        self.nand = []          # (net0, net1, netout)
        self.busops = []        # (kind, w, [nets])
        self.ins = {}           # name -> net
        self.outs = {}          # name -> net


class Project:
    def __init__(self, root):
        self.chips = {}
        for f in glob.glob(os.path.join(root, "Chips", "*.json")):
            d = json.load(open(f))
            self.chips[d["Name"]] = d
        self._cache = {}

    def compile(self, chipname):
        if chipname in self._cache:
            return self._cache[chipname]
        chip = self.chips[chipname]
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            r = x
            while parent[r] != r:
                r = parent[r]
            while parent[x] != r:
                parent[x], x = r, parent[x]
            return r

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        c = Compiled()
        nand_nodes = []
        bus_nodes = []
        boundary = []   # (kind, name, node)

        def walk(ch, path):
            top = (path == ())
            for p in ch.get("InputPins", []):
                find((path, p["ID"], 0))
                if top: boundary.append(("IN", p["Name"], (path, p["ID"], 0), p.get("BitCount", 1)))
            for p in ch.get("OutputPins", []):
                find((path, p["ID"], 0))
                if top: boundary.append(("OUT", p["Name"], (path, p["ID"], 0), p.get("BitCount", 1)))
            for s in ch.get("SubChips", []):
                iid, nm = s["ID"], s["Name"]
                sub = self.chips.get(nm)
                if nm == "NAND":
                    for pid in (0, 1, 2):
                        find((path, iid, pid))
                    nand_nodes.append((path, iid))
                elif sub is not None:
                    for p in sub.get("InputPins", []) + sub.get("OutputPins", []):
                        find((path, iid, p["ID"]))
                        union((path, iid, p["ID"]), (path + (iid,), p["ID"], 0))
                elif nm in SPLITSRC or nm in SPLIT or nm in NIBSPLIT or nm in NIBMERGE:
                    w = SPLITSRC.get(nm) or SPLIT.get(nm) or 8
                    pins = list(range(0, w + 2)) if not (nm in SPLIT or nm in SPLITSRC) else list(range(0, w + 2))
                    for pid in pins:
                        find((path, iid, pid))
                    bus_nodes.append((path, iid, nm, w))
                else:
                    bus_nodes.append((path, iid, "OPAQUE:" + nm, 1))
            for w_ in ch.get("Wires", []):
                a, b = w_["SourcePinAddress"], w_["TargetPinAddress"]
                union((path, a["PinOwnerID"], a["PinID"]), (path, b["PinOwnerID"], b["PinID"]))
            for s in ch.get("SubChips", []):
                if s["Name"] in self.chips:
                    walk(self.chips[s["Name"]], path + (s["ID"],))

        walk(chip, ())
        netid = {}
        for node in list(parent):
            r = find(node)
            if r not in netid:
                netid[r] = len(netid)
        def n(node):
            r = find(node)
            return netid.get(r, -1)

        for path, iid in nand_nodes:
            c.nand.append((n((path, iid, 0)), n((path, iid, 1)), n((path, iid, 2))))
        for path, iid, nm, w in bus_nodes:
            if nm in SPLITSRC:
                c.busops.append(("split", w, n((path, iid, 0)), [n((path, iid, k)) for k in range(1, w + 1)]))
            elif nm in SPLIT:
                c.busops.append(("merge", w, [n((path, iid, j)) for j in range(w)], n((path, iid, w))))
            elif nm in NIBSPLIT:
                c.busops.append(("nibsplit", 8, n((path, iid, 0)), [n((path, iid, 1)), n((path, iid, 2))]))
            elif nm in NIBMERGE:
                c.busops.append(("nibmerge", 8, [n((path, iid, 0)), n((path, iid, 1))], n((path, iid, 2))))
        c.nnets = len(netid)
        for kind, name, node, bits in boundary:
            if kind == "IN":
                c.ins[name] = n(node)
            else:
                c.outs[name] = n(node)
        self._cache[chipname] = c
        return c

    def sim(self, chipname):
        return Sim(self, chipname)

    def run(self, chipname, cin, sweeps=200):
        c = self.compile(chipname)
        val = [0] * c.nnets
        for k, v in c.ins.items():
            val[v] = cin.get(k, 0)
        for _ in range(sweeps):
            nv = list(val)
            for a, b, o in c.nand:
                nv[o] = 0 if (val[a] and val[b]) else 1
            for kind, w, src, dst in c.busops:
                if kind == "split":
                    v = val[src]
                    for i, d in enumerate(dst):
                        nv[d] = (v >> (w - 1 - i)) & 1
                elif kind == "merge":
                    v = 0
                    for s in src:
                        v = (v << 1) | (val[s] & 1)
                    nv[dst] = v
                elif kind == "nibsplit":
                    v = val[src]
                    nv[dst[0]] = (v >> 4) & 0xF
                    nv[dst[1]] = v & 0xF
                elif kind == "nibmerge":
                    nv[dst] = ((val[src[0]] & 0xF) << 4) | (val[src[1]] & 0xF)
            if nv == val:
                break
            val = nv
        return {k: val[v] for k, v in c.outs.items()}


class Sim:
    """State-preserving evaluator: call step() repeatedly to clock a circuit.

    Bistable nets keep their previous value because the fixed-point sweep starts
    from the last settled state, matching DLS's incremental updating.
    """

    def __init__(self, proj, chipname):
        self.c = proj.compile(chipname)
        self.val = [0] * self.c.nnets

    def step(self, cin, sweeps=400):
        c = self.c
        for k, v in c.ins.items():
            self.val[v] = cin.get(k, 0)
        for _ in range(sweeps):
            old = list(self.val)
            nv = list(self.val)
            for a, b, o in c.nand:
                nv[o] = 0 if (old[a] and old[b]) else 1
            for kind, w, src, dst in c.busops:
                if kind == "split":
                    v = old[src]
                    for i, d in enumerate(dst):
                        nv[d] = (v >> (w - 1 - i)) & 1
                elif kind == "merge":
                    v = 0
                    for s_ in src:
                        v = (v << 1) | (old[s_] & 1)
                    nv[dst] = v
                elif kind == "nibsplit":
                    v = old[src]
                    nv[dst[0]] = (v >> 4) & 0xF
                    nv[dst[1]] = v & 0xF
                elif kind == "nibmerge":
                    nv[dst] = ((old[src[0]] & 0xF) << 4) | (old[src[1]] & 0xF)
            if nv == self.val:
                break
            self.val = nv
        return self.read()

    def read(self):
        return {k: self.val[v] for k, v in self.c.outs.items()}
