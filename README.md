# SysML v2 wardrobe: a small model-based systems engineering example

A compact example of describing a system with **SysML v2 textual notation**: its structure, its
requirements, one process, and the traceability between them. The system is a wardrobe that stores
garments.

I built it while learning MBSE after the free Ansys course
[Introduction to SysML v2](https://innovationspace.ansys.com/product/introduction-to-sysml-v2).

## The system

| Element | What it models |
|---------|----------------|
| `Wardrobe` (part) | Main part. Has a capacity, used volume, derived free volume, and 0..* garments. |
| `Garment` (part) | A piece of clothing with a name, a volume, and a clean/dirty state. |
| `R1 SufficientSpace` | The wardrobe shall have enough free volume for the garment being stored. |
| `R2 CleanGarmentOnly` | Only clean garments shall be stored. |
| `StoreGarment` (action) | `start -> checkClean -> checkSpace -> place -> done` |
| `satisfy` | R1 is satisfied by the wardrobe, R2 by the garment being stored. |

The model is in [`model/wardrobe.sysml`](model/wardrobe.sysml). It includes an example configuration
with a clean t-shirt and a dirty pair of jeans.

## Architecture summary

[`tools/summarize.py`](tools/summarize.py) reads the model and writes
[`docs/architecture.md`](docs/architecture.md): a class diagram of the structure, a flowchart of the
process (both Mermaid, rendered by GitHub), a requirements table, a traceability table, and a check of
the example configuration against R1 and R2.

```bash
python3 tools/summarize.py                         # prints the summary and writes docs/architecture.md
python3 tools/summarize.py model/wardrobe.sysml out.md
```

Expected result for the example configuration:

```
myWardrobe.tShirt: ALLOWED
myWardrobe.jeans: REJECTED  (R2 fails: garment is dirty)
```

Only the Python standard library is needed.

## Limits, stated plainly

- The `.sysml` file was written by hand and has **not** been validated with a SysML v2 tool. If you
  open it in a SysML v2 environment and something fails to parse, please open an issue.
- `summarize.py` is a lightweight reader for the subset of the language used here, **not** a full
  SysML v2 parser. The requirement check is specific to R1 and R2; it does not evaluate arbitrary
  constraint expressions.
- Behaviour is a straight sequence. A fuller model would branch on the checks (decision nodes) and
  bind the action inputs to concrete parts.

## Ideas for next steps

- Validate the model with the SysML v2 pilot implementation and fix whatever it reports.
- Add decision nodes: dirty garment goes to a laundry step, full wardrobe rejects the garment.
- Extend the structure with sections or shelves and per-section capacity.
