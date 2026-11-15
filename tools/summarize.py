#!/usr/bin/env python3
"""Summarise a small SysML v2 textual model.

This is a deliberately lightweight reader, NOT a full SysML v2 parser. It understands the
subset used in model/wardrobe.sysml (packages, enum/part/requirement/action definitions,
usages, attribute defaults, `satisfy`) and produces:

  * a console summary of the architecture, requirements and process
  * docs/architecture.md with Mermaid diagrams and a traceability table
  * a requirement check of the example configuration (R1 space, R2 cleanliness)

Usage:  python3 tools/summarize.py [model/wardrobe.sysml] [docs/architecture.md]
Only the Python standard library is needed.
"""
import re
import sys
from pathlib import Path


# ----------------------------------------------------------------------------
# 1. Tiny block reader: turns `header { ... }` and `header;` into a tree
# ----------------------------------------------------------------------------
class Node:
    def __init__(self, header):
        self.header = header
        self.children = []

    @property
    def doc(self):
        for c in self.children:
            if c.header == "doc":
                return getattr(c, "text", "")
        return ""

    def kids(self):
        return [c for c in self.children if c.header != "doc"]


def read_blocks(text):
    text = re.sub(r"//[^\n]*", "", text)  # drop line comments
    pos = 0

    def block():
        nonlocal pos
        out, buf = [], ""
        while pos < len(text):
            if text.startswith("/*", pos):
                end = text.index("*/", pos)
                body = " ".join(text[pos + 2:end].split())
                pos = end + 2
                if buf.strip() == "doc":
                    d = Node("doc")
                    d.text = body
                    out.append(d)
                    buf = ""
                continue
            ch = text[pos]
            pos += 1
            if ch == "{":
                n = Node(" ".join(buf.split()))
                n.children = block()
                out.append(n)
                buf = ""
            elif ch == "}":
                if buf.strip():
                    out.append(Node(" ".join(buf.split())))
                return out
            elif ch == ";":
                if buf.strip():
                    out.append(Node(" ".join(buf.split())))
                buf = ""
            else:
                buf += ch
        return out

    return block()


# ----------------------------------------------------------------------------
# 2. Build a simple model dictionary
# ----------------------------------------------------------------------------
def short(name):
    """WardrobeSystem::X -> X, CleanState::clean -> clean"""
    return name.split("::")[-1].strip().strip('"')


def parse_attr(header):
    m = re.match(r"attribute\s+(\w+)\s*:\s*([\w:]+)(?:\s*=\s*(.+))?$", header)
    if m:
        return {"name": m.group(1), "type": m.group(2), "default": m.group(3)}
    m = re.match(r"attribute\s+:>>\s*(\w+)\s*=\s*(.+)$", header)  # redefinition with value
    if m:
        return {"name": m.group(1), "type": None, "default": m.group(2)}
    return None


def build_model(nodes):
    pkg = next(n for n in nodes if n.header.startswith("package"))
    model = {"package": pkg.header.split()[1], "doc": pkg.doc, "enums": {}, "parts": {},
             "reqs": {}, "actions": {}, "usages": {}, "action_usages": {}, "req_usages": {}, "satisfy": []}

    for n in pkg.kids():
        h = n.header

        if m := re.match(r"enum def (\w+)$", h):
            model["enums"][m.group(1)] = [c.header.split()[1] for c in n.kids() if c.header.startswith("enum ")]

        elif m := re.match(r"requirement def (?:<'(\w+)'>\s*)?(\w+)$", h):
            req = {"id": m.group(1) or "", "doc": n.doc, "attrs": [], "constraint": ""}
            for c in n.kids():
                if a := parse_attr(c.header):
                    req["attrs"].append(a)
                elif c.header == "require constraint" and c.kids():
                    req["constraint"] = c.kids()[0].header
            model["reqs"][m.group(2)] = req

        elif m := re.match(r"part def (\w+)$", h):
            part = {"doc": n.doc, "attrs": [], "parts": [], "reqs": []}
            for c in n.kids():
                if a := parse_attr(c.header):
                    part["attrs"].append(a)
                elif pm := re.match(r"part (\w+)\s*:\s*(\w+)(?:\[([^\]]+)\])?$", c.header):
                    part["parts"].append({"name": pm.group(1), "type": pm.group(2), "mult": pm.group(3) or "1"})
                elif rm := re.match(r"requirement (\w+)\s*:\s*(\w+)$", c.header):
                    part["reqs"].append({"name": rm.group(1), "type": rm.group(2)})
            model["parts"][m.group(1)] = part

        elif m := re.match(r"action def (\w+)$", h):
            act = {"doc": n.doc, "inputs": [], "steps": [], "subactions": []}
            for c in n.kids():
                if im := re.match(r"in item (\w+)\s*:\s*(\w+)$", c.header):
                    act["inputs"].append((im.group(1), im.group(2)))
                elif sm := re.match(r"(?:first|then)\s+(\w+)$", c.header):
                    act["steps"].append(sm.group(1))
                elif am := re.match(r"action (\w+)$", c.header):
                    act["subactions"].append(am.group(1))
            model["actions"][m.group(1)] = act

        elif m := re.match(r"part (\w+)\s*:\s*(\w+)$", h):
            model["usages"][m.group(1)] = usage(n, m.group(2))

        elif m := re.match(r"requirement (\w+)\s*:\s*(\w+)$", h):
            model["req_usages"][m.group(1)] = m.group(2)

        elif m := re.match(r"action (\w+)\s*:\s*(\w+)$", h):
            model["action_usages"][m.group(1)] = {"type": m.group(2)}

        elif m := re.match(r"satisfy\s+(\S+)\s+by\s+(\S+)$", h):
            model["satisfy"].append((m.group(1), m.group(2).replace("::", ".")))

    return model


def usage(node, type_name):
    u = {"type": type_name, "attrs": {}, "parts": {}}
    for c in node.kids():
        if m := re.match(r"attribute\s+:>>\s*(\w+)\s*=\s*(.+)$", c.header):
            u["attrs"][m.group(1)] = short(m.group(2))
        elif m := re.match(r"part (\w+)\s*:\s*(\w+)(?:\s*:>\s*\w+)?$", c.header):
            u["parts"][m.group(1)] = usage(c, m.group(2))
    return u


# ----------------------------------------------------------------------------
# 3. Requirement check of the example configuration
# ----------------------------------------------------------------------------
def check_configuration(model):
    """Evaluate R1 (space) and R2 (clean) for every garment of every wardrobe usage."""
    rows = []
    for wname, w in model["usages"].items():
        if w["type"] != "Wardrobe":
            continue
        free = float(w["attrs"]["capacity"]) - float(w["attrs"]["usedVolume"])
        for gname, g in w["parts"].items():
            vol = float(g["attrs"]["volume"])
            state = g["attrs"]["state"]
            r1 = free >= vol
            r2 = state == "clean"
            reasons = []
            if not r1:
                reasons.append(f"R1 fails: free {free:g} < volume {vol:g}")
            if not r2:
                reasons.append(f"R2 fails: garment is {state}")
            rows.append((wname, gname, free, vol, state, r1 and r2, "; ".join(reasons)))
    return rows


# ----------------------------------------------------------------------------
# 4. Output
# ----------------------------------------------------------------------------
def console_summary(model, checks):
    out = [f"Package: {model['package']}", f"  {model['doc']}", "", "STRUCTURE"]
    for name, p in model["parts"].items():
        out.append(f"  part def {name}  - {p['doc']}")
        out += [f"      attribute {a['name']} : {a['type']}" for a in p["attrs"]]
        out += [f"      part {c['name']} : {c['type']} [{c['mult']}]" for c in p["parts"]]
        out += [f"      requirement {r['name']} : {r['type']}" for r in p["reqs"]]
    out += ["", "REQUIREMENTS"]
    for name, r in model["reqs"].items():
        out.append(f"  {r['id'] or '-':3} {name}: {r['doc']}")
        out.append(f"      constraint: {r['constraint']}")
    out += ["", "PROCESS"]
    for name, a in model["actions"].items():
        out.append(f"  action def {name}: " + " -> ".join(a["steps"]))
        out.append("      inputs: " + ", ".join(f"{n}:{t}" for n, t in a["inputs"]))
    out += ["", "TRACEABILITY (satisfy)"]
    out += [f"  {req} ({model['req_usages'].get(req, '?')}) <- {part}" for req, part in model["satisfy"]]
    out += ["", "CONFIGURATION CHECK (can each garment be stored?)"]
    for wname, gname, free, vol, state, ok, why in checks:
        out.append(f"  {wname}.{gname}: {'ALLOWED' if ok else 'REJECTED'}" + (f"  ({why})" if why else ""))
    return "\n".join(out)


def mermaid_structure(model):
    L = ["classDiagram"]
    for name, vals in model["enums"].items():
        L += [f"    class {name} {{", "        <<enumeration>>"] + [f"        {v}" for v in vals] + ["    }"]
    for name, p in model["parts"].items():
        L.append(f"    class {name} {{")
        L += [f"        +{a['type']} {a['name']}" for a in p["attrs"]]
        L.append("    }")
    for name, r in model["reqs"].items():
        L += [f"    class {name} {{", "        <<requirement>>", f"        {r['id']}", "    }"]
    for name, p in model["parts"].items():
        for c in p["parts"]:
            L.append(f'    {name} "1" *-- "{c["mult"]}" {c["type"]} : {c["name"]}')
        for r in p["reqs"]:
            L.append(f"    {name} ..> {r['type']} : {r['name']}")
        for a in p["attrs"]:
            if a["type"] in model["enums"]:
                L.append(f"    {name} --> {a['type']} : {a['name']}")
    return "\n".join(L)


def mermaid_process(act_name, act):
    L = ["flowchart LR"]
    for i, s in enumerate(act["steps"]):
        shape = f"{s}(({s}))" if s in ("start", "done") else f"{s}[{s}]"
        L.append(f"    {shape}" if i == 0 else f"    {act['steps'][i - 1]} --> {shape}")
    return "\n".join(L)


def markdown(model, checks):
    md = [f"# Architecture summary: {model['package']}", "",
          "_Generated by `tools/summarize.py` from `model/wardrobe.sysml`. Do not edit by hand._", "",
          model["doc"], "", "## Structure", "", "```mermaid", mermaid_structure(model), "```", ""]
    for name, a in model["actions"].items():
        md += [f"## Process: {name}", "", a["doc"], "", "```mermaid", mermaid_process(name, a), "```", ""]
    md += ["## Requirements", "", "| ID | Name | Statement | Constraint |", "|----|------|-----------|------------|"]
    md += [f"| {r['id']} | {n} | {r['doc']} | `{r['constraint']}` |" for n, r in model["reqs"].items()]
    md += ["", "## Traceability", "", "| Requirement | Satisfied by |", "|-------------|--------------|"]
    md += [f"| {req} ({model['req_usages'].get(req, '?')}) | `{part}` |" for req, part in model["satisfy"]]
    md += ["", "## Example configuration check", "",
           "| Wardrobe | Garment | Free volume | Garment volume | State | Result |",
           "|----------|---------|-------------|----------------|-------|--------|"]
    for w, g, free, vol, state, ok, why in checks:
        md.append(f"| {w} | {g} | {free:g} | {vol:g} | {state} | {'allowed' if ok else 'rejected: ' + why} |")
    return "\n".join(md) + "\n"


def main():
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "model/wardrobe.sysml")
    dst = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/architecture.md")
    model = build_model(read_blocks(src.read_text(encoding="utf-8")))
    checks = check_configuration(model)
    print(console_summary(model, checks))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(markdown(model, checks), encoding="utf-8")
    print(f"\nWrote {dst}")


if __name__ == "__main__":
    main()
