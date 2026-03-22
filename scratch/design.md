# Manufacturing Plant Flow Visualizer Design Notes

## Overview

`vsv.html` is a single-file prototype for a grid-based manufacturing and workflow visualizer. It combines HTML, CSS, and JavaScript in one document and renders a set of draggable production lines, intake queues, a hopper, stations, output nodes, inventory cards, and conveyor-style connections.

The file is structured as a working UX prototype rather than a production application. Most actions currently use in-page state updates and `alert(...)` placeholders instead of forms or server calls.

## Primary UI Model

Each line is rendered as a horizontal flow made of:

1. A line header with the line name and line-level controls.
2. An `Intake Queues` group.
3. A `Hopper` card.
4. A station assembly area.
5. An optional output card.

Supporting elements:

1. Inventory cards can sit anywhere on the grid.
2. External connections can link lines to other lines or inventory to stations.
3. Internal flow across intake group, hopper, stations, and output is drawn as a single conveyor belt per line.

## Layout And Visual Decisions

### Grid And Placement

- The workspace is grid-based with `gridSize = 64`.
- Lines and inventories are absolutely positioned and snap back to the grid after dragging.
- A scaled viewport is used for zooming while preserving logical grid coordinates.

### Shared Card Language

- Cards are white by default with black or queue-colored borders.
- Action controls sit in a top-right floating `control-group`.
- Buttons use small rounded pills for consistency.
- Work-unit cards use a white background with a 2px queue-colored border.

### Section Titles

- `Intake Queues` and `Hopper` use the shared `intake-group-label` style.
- These labels are left-aligned, bold, and black.

### Station Sizing

- Stations are intentionally wider than the base component size.
- Current station width is `256px`, which is double the default component width of `128px`.

## Interaction Decisions

### Line Controls

Each line header includes:

- `Edit`
- `Insert`
- `Lock` or `Unlock`

Behavior:

- `Insert` toggles insertion mode via the `insert-enabled` class on the line.
- `Lock` toggles the `line-locked` class and disables dragging.
- Active `Insert` and `Lock` buttons invert to a dark filled style.

### Insert Controls

Insertion controls exist:

- Before the first station or intake queue.
- Between each station or intake queue.
- After the last station or intake queue.

Visual rules:

- Station insert controls are vertical with a `+` button at the top and a bar below.
- Intake queue insert controls are horizontal with a `+` button at the right.
- Insert controls are normally hidden and appear when line insert mode is enabled.
- Empty states still expose insertion affordances through `no-stations` and `no-intakes` handling.

### Intake Queues

Each intake queue card includes:

- A bold single-line queue label with ellipsis overflow.
- A `Work Units` button on the same row as the name.
- A top-right action group with `Add`, `Edit`, and `Delete`.

Behavior:

- `Delete` is only visible while insert mode is enabled.
- Mix ratio appears only when a line has multiple queues.
- Queue colors propagate into hopper and station work units through `intakeQueueId`.

### Hopper

The hopper can display a single active work unit.

Each hopper work unit includes:

- A clickable name that currently opens an alert.
- A top-right `Start` button.

Behavior:

- Clicking `Start` moves the hopper work unit into the first station.
- A replacement hopper work unit is then generated for demo purposes.
- The work-unit title is clamped to two lines.
- The `Start` button stops event propagation so it does not trigger the name click action.

### Stations

Each station includes:

- A title.
- A top-right action group with `Edit` and `Delete`.
- A work-unit toggle button showing either count or `Empty`.
- An expandable work-unit panel.

Behavior:

- `Delete` is only visible while insert mode is enabled.
- If a station has exactly one work unit, it auto-expands.
- If a station has multiple work units, the panel adds a `Collapse` button.
- Clicking a station work unit currently opens an alert.

### Station Work Units

Each station work-unit card includes:

- A top-right `Done` button.
- A two-line truncated title.
- Assignee avatars or initials.
- Elapsed time.
- An optional `Hold` pill.

Behavior:

- `Done` removes the unit from the current station.
- If a next station exists, the unit moves to that station.
- Elapsed time updates every minute.

### Inventory Cards

Inventory cards are collapsed by default.

Collapsed state shows:

- Name
- Health pill
- `Edit`
- Expand or collapse toggle

Expanded state adds:

- Cycle stock
- Buffer stock level
- Safety stock level
- Reorder point
- Estimated reorder date

Health display maps numeric values to named states:

- `1` -> `Healthy`
- `2` -> `Reorder`
- `3` -> `Low`

## Rendering And State Architecture

The prototype uses global in-memory structures:

- `allLines`: rendered line instances and their DOM references.
- `allInventories`: rendered inventory instances.
- `connections`: external and internal connection definitions.
- `elapsedTimeElements`: references for live elapsed-time updates.

IDs and counters:

- `nextIntakeQueueId` is used for dynamically inserted intake queues.
- `nextStationKey` gives each station a stable identity across rerenders.

Normalization helpers convert incoming definitions into richer renderable objects:

- `normalizeIntakeQueues(...)`
- `normalizeStations(...)`
- `normalizeQueueColor(...)`
- `buildIntakeQueueColorMap(...)`

## Important Functions

### Core Construction

- `createLine(lineDefinition)`
  - Builds the line shell, header, intake group, hopper, assembly, and output.
- `createInventory(inventoryDefinition)`
  - Builds a draggable inventory card with collapsed and expanded states.

### Intake Queue Flow

- `createIntakeQueueComponent(...)`
- `updateIntakeQueueComponent(...)`
- `renderLineIntakes(lineId)`
- `insertIntakeQueueAt(lineId, insertIndex)`
- `deleteIntakeQueueAt(lineId, queueIndex)`

### Station Flow

- `createStationComponent(...)`
- `updateStationComponent(...)`
- `renderLineStations(lineId)`
- `insertStationAt(lineId, insertIndex)`
- `deleteStationAt(lineId, stationIndex)`

### Work Unit Flow

- `createHopperWorkUnitButton(...)`
- `moveHopperWorkUnitToFirstStation(lineId)`
- `addWorkUnitToHopper(lineId, workUnit)`
- `createWorkUnitCard(...)`
- `completeWorkUnit(lineId, stationIndex, workUnitIndex)`

### Interaction And Positioning

- `makeDraggable(el)`
  - Handles drag, snap-to-grid, lock checks, and drag overlay updates.
- `showDragGridPosition(...)`
  - Displays `x` and `y` grid coordinates beside the pointer while dragging a line.
- `applyZoom()`
  - Applies viewport scale while preserving grid-aligned positions.

### Connection Drawing

- `refreshInternalConnections(lineId)`
  - Rebuilds internal flow links for a line.
- `drawAllLines()`
  - Clears and redraws all belts and external connections.
- `drawConveyorBelt(pts)`
  - Uses PixiJS to render the belt body and animated chevrons.

## Connection Model

There are two connection styles:

1. Internal connections
   - Built automatically per line.
   - Drawn as one continuous conveyor-like belt from intake group to output.

2. External connections
   - Stored in `connections`.
   - Support `output`, `input`, and `inventory` connection types.
   - Can be rendered as conveyor belts when `conveyor: true` is set.

Path-routing helpers:

- `getInputPoints(...)`
- `getOutputPoints(...)`
- `getInventoryPoints(...)`

## Demo Data Seeded In The File

The prototype currently seeds these lines:

- `Design`
- `Software Development`
- `QA`
- `Tech Support`
- `Production`

It also seeds one inventory card:

- `RFID Cards`

Notable seeded behaviors in the demo:

- `Software Development` starts with a hopper work unit.
- Some stations contain preloaded work units with assignees, hold state, start times, and queue-based color mapping.
- Inventory is connected to a production station using an inventory conveyor.
- Cross-line output and input conveyors are prewired between several demo lines.

## Current Prototype Boundaries

The file is intentionally prototype-oriented and still contains placeholder behavior:

- Many edit and view actions still call `alert(...)`.
- Line creation is stubbed by an `Add line` alert.
- There is no persistence layer.
- There is no form system for editing lines, queues, stations, inventory, or work units.
- The file depends on PixiJS from a CDN for grid and conveyor rendering.

## Notable Implementation Details

- Queue color is treated as a reusable source of visual identity and is propagated into hopper and station work units.
- Stable station identity is preserved using `_stationKey` to reduce rerender churn.
- Zoom is implemented by scaling the viewport rather than recalculating the data model.
- Dragging ignores interactive child controls so buttons and work-unit interactions still behave normally.
- Internal line flow is visually simplified into one belt, even though data is managed per component.

## Current Rough Edges

- The inventory expand toggle text currently reads `Exand` in code.
- The file mixes UI rendering, state management, demo data, and drawing logic in one document.
- The prototype is suitable for iteration speed, but the next step toward production would be splitting CSS, render logic, state, and seeded data into separate modules.