# Production

Production guides factory operators through every step of a manufacturing process, one work unit at a time, and gives line managers a live view of the floor.

The system's input is a **work unit** — a row describing an asset. Its output is a device (e.g. a reader) configured to that asset, with a complete record of who did what, when, and with which supplies.

## Key Surfaces

- **Manufacturing Line** — The operator's surface. A full-screen window that walks an operator through each operation on a work unit: instructions and photos on the right, step list on the left, notes and `Complete` / `Fail` at the bottom. Operators pull work units off the job queue one at a time and never see two units at once.
- **Jobs** — An admin tool for creating a run: a name, scheduled dates, a production line, and a CSV of work units. Starting a job opens it to operators.
- **Active Job Dashboard** — A live view of a running job: work unit counts, throughput, and one row per operator showing their status (working, paused, stopped, left), the unit and step they are on, and the supplies they hold. Andon calls appear here as a blinking red dot.
- **Production Lines** — An admin tool for authoring the process itself. A production line is a versioned template declaring the work unit columns it needs, the supply pools it draws from, and an ordered list of operations. Each operation is built from typed sections: descriptions, images, and inputs.
- **Pools** — An admin tool for the global supplies used on the floor (test cards, printers). Each resource carries a value that can be interpolated into operation text, and is checked out exclusively to one operator at a time.

## Motivation

Manufacturing instructions usually live in a binder or a PDF that nobody updates, and the record of what actually happened lives in someone's handwriting. Production makes the process the system of record: the instructions an operator sees are generated from a versioned template, the values they capture are interpolated into later steps, and every completion, failure, pause, and andon call is timestamped against a real BOSS user.

Versioning is central. Editing a production line that a running job depends on forks a new version rather than mutating the old one, so a work unit completed last month can always be shown exactly as the operator saw it.

## Interpolation

Operation text may reference three namespaces, resolved per work unit:

```
{work_unit.Location}      the unit's CSV column value
{operation.1.serial}      a value captured on an earlier step
{pool.Test card}          the value of the supply this operator holds
```

References may only point backward, and every token is validated when the production line is saved — a token that cannot resolve is rejected before it can ever reach an operator.
