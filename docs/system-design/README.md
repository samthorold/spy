# System Design

Design documentation for the app — our opinion about what it should do for a learner, and why. Built on the facts in [docs/learning/](../learning/) and encoded by the implementation, but distinct from both.

The design is **self-justifying**: each mechanism is described together with the reason it has that shape, including why tempting alternatives fail. No separate record of past decisions is needed.

## Purpose before structure

Order the design purpose first, structure last:

1. **Purpose.** What a learner should be able to do or experience, stated as observable behaviour over time (the analogue of reference modes).
2. **Boundary.** What the app generates itself and what the learner or the outside world supplies.
3. **Dynamic hypothesis.** The feedback loops that should produce the purpose (for example review → recall → scheduling).
4. **Rules.** The concrete mechanisms.

## Documents

None yet.

## Relationship to other layers

```
docs/learning/         Ground truth about learning.
        │
        ▼
docs/system-design/    Our opinion. What the app does, and why.
        │
        ▼
the code               Implementation. Data structures, algorithms, parameters.
```

Each layer references the one below it as foundation. No layer reaches up — domain docs never reference the app, and system design docs never prescribe data structures.
