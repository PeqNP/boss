/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

/**
 Value Stream Visualizer - A LEAN manufacturing system.
 
 ────────────────────────────────────────────────────────────────
 Domain Model Conventions – ID & Relationship Rules

 1. Every model that conforms to Identifiable defines:
    typealias ID = Int    (or UUID, String, … – but here Int)
    let id: ID

 2. Foreign-key / reference properties use the pattern:
    let xxxId: OtherModel.ID     (camelCase with 'Id' suffix)

    → This establishes a compile-time safe reference to OtherModel.id

 3. Never assign a raw Int to a xxxId field without going through
    the corresponding .ID type — this prevents mixing up different kinds of IDs.

 Follow these rules strictly when reading, writing, or generating code
 related to these models.
 
 Typically, models will contain fully related objects. Child objects refer to their respective parent models by their ID to avoid circular references. In other words, a model that "contains" children will have fully related objects. While children to a parent model will only reference their parent model's ID. This is done to make it easy to consume a model when building UIs and to make it easy to query child models, related to a parent model, from the database.
 
 An example is `Line.intakeQueues`. The `IntakeQueue.lineId` is how the respective `Line` will query for all of its `IntakeQueue`s and associate all of them to `Line.intakeQueue`s. Additionally, the order in which the respective models are placed in the array (e.g. `Line.intakeQueues`) is defined by the respective child `sortOrder` property (e.g. `IntakeQueue.sortOrder`).
 ────────────────────────────────────────────────────────────────
 Table Conventions - Creating tables, columns, and index rules
 
 All `id` columns must be serial. Use your best judgement when determining the size of the integer to use for ID columns (e.g. `INT`, `BIGINT`). If you're not sure, use `INT`. For example, records used for configuration can be `INT`. Records that are guaranteed to be in the hundreds of thousands (logs) can be a `BIGINT`, or equivalent.

 All IDs that reference another table/model, must be indexed.
 
 This system should ALWAYS RESPECT THE INDIVIDUAL! We want to provide the best value to our customers AND make the operators the best versions of themself.
 - Every kaizen performed should be done collectively to get buy in and respects an individual's expertise.
 - Monitoring of performance should be focused on:
   - Removing extra movement
   - Training
   - Improving tooling
   - etc.
 */

import SwiftUI

/// `BusinessModel` and `ChangeLog` are used to keep track changes to models over time.
///
/// The `case` name of the model, in `BusinessModel`, directly maps to the `struct` name of the business model.
///
/// If a model is listed in `BusinessModel`, then add the generated code to track the changes made to the model in the database.
///
/// There will be a single table, `change_logs`, for all model changes. This is done to (greatly) reduce the complexity of the database.
enum BusinessModel: Int {
    case IntakeQueue = 0
    case User
    case Line
    case Operator
    case Agent
    case Output
    case Station
    case Supply
    case OutputReason
    case Shift
    case Capacity
}

struct ChangeLog: Identifiable {
    let id: Int
    /// The respective business model that changed
    let businessModelId: BusinessModel
    /// The time the change was made (whatever the current time is)
    let date: Date
    /// The operator who made the change
    let operatorId: Operator.ID
    /// Contains all of the property values that changed. This is saved as a JSON structure in the db. e.g. if the `Line.name` property was changed, the metadata would be `{"name": ["Name before", "Name after"]}`, where the first column in the array would be the value before it was changed, and the next value would be the new value.
    let metadata: [String: String]
}

// MARK: - Business Models

// MARK: System & Common Models

public enum OperatorType {
    case user(Operator.ID)
    case agent(Agent.ID)
}

/// Represents an AI agent
public struct Agent: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let name: String
    /// TBD: More properties may be required such as the user/pass, configuration, etc. to interact with respective AI agent
}

/// Association betweeen a BOSS user LEAN system user.
///
/// This structure allows metadata to be associated to an Operator, without affecting the BOSS user.
public struct Operator: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let userId: User.ID
    public let shifts: [Shift]
}

/// Icons that will be provided by the system
public enum SystemIcon: Int {
    case Cat = 0
    case Dog
    /// TBD
}

/// Location where Icon can be found
public enum Icon {
    case system(SystemIcon)
    case url(URL)
}

/// Allows a business model to be identified with color and/or icon.
public struct Theme: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let strokeColor: Color?
    public let fillColor: Color?
    public let icon: Icon?
}

public enum DayOfWeek: Int, CaseIterable {
    /// Matches `Calendar.Component.weekday`
    case sunday = 1, monday, tuesday, wednesday, thursday, friday, saturday
}

/// A `Shift` can be used for any `Line`. Depending on the company, they may only have one set of shifts for the week.
///
/// `Shift`s associated to `Line`s start on Sunday at 12a. A `Shift` may overlap days and even into the next week's `Shift`s.
public struct Shift: Identifiable {
    /// `ShiftTime` is part of the `Shift`'s database record. It's modeled separately here for easier use.
    public struct Time {
        public let dayOfWeek: DayOfWeek
        public let startTime: TimeInterval
        public let endTime: TimeInterval
    }
    
    public typealias ID = Int
    public let id: ID
    public let lineId: Line.ID
    /// Start and end time of a shift
    /// Summing all shifts, for a given week = Total net production run time for a `Line`
    public let start: Shift.Time
    public let end: Shift.Time
    /// The amount of break time (lunch, etc.) an `Operator` has during this shift
    public let breaksInMinutes: TimeInterval
}

/// The scheduled time an `Operator` is working a `Line`.
///
/// This provides the clearest signal for cycle time. The `Operator` does not need to inform the system when they are signed in or out. It is automatically determined by the `Shift` they are associated to.
///
/// This correlation is manually made when the `Operator` is introduced to the `Line`. An `Operator` may move in and out of different `Shift`s. An `Operator` may not have overlapping `Shift`s.
public struct OperatorShift: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let operatorId: Operator.ID
    public let shift: Shift
}

/// Indicates a completed shift. This is materialized to determine the amount of time an `Operator` was working on a `Line` to determine cycle time on a daily basis. In other words, the system will automatically create these records once the day is finished. This is combined with an `OperatorAbsence` to determine the actual time worked for a given `Shift`.
///
/// Some companies probably don't care about the exact start and end time if an absence occurs. For example, if someone comes in late for a doctor's appointment, but leaves later, an `OperatorAbsence` record should not be created. Otherwise, it will cause issues with the cycle time calculation.
public struct CompletedOperatorShift: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let operatorShiftId: OperatorShift.ID
    public let weekNumber: Int
}

public enum AbsenceReason {
    case sickLeave /// May be paid, depending on company policy
    case paidTimeOff /// Paid time off
    case other(String) /// Not typically paid time
}

/// Indicatates when an `Operator` will be absent from the `Line`.
///
/// This must be added (manually) to the respective week's `Shift`. If possible, it can be derived from external HR/e-mail systems. This time is overlaid on the respective `Shift`'s time to produce the actual time on the `Shift`.
public struct OperatorAbsence: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let operatorId: Operator.ID
    public let shift: Shift
    public let entireShift: Bool
    /// If not entire shift, indicate the amount of time off will be taken
    public let timeOffInMinutes: TimeInterval
    public let weekNumber: Int
    public let reason: AbsenceReason
}

// TODO: Stoppage data. Jams, waiting for parts, etc. required to determine detailed downtime

// MARK: Line

/// A `Line` contains `Station`s that must be performed in order for a `WorkUnit` to be considered considered `Done`. A `WorkUnit` starts in the `IntakeQueue`, through all `Station`s, then to `Done`.
///
/// This is considered the "model" or "reference" line. A `Line` may be copied by creating a `ReplicaLine`. When first defining how a `Line` should operate, it could also be referred to as a "pilot" line.
///
/// - Note: This should only be modifiable by an admin.
public struct Line: Identifiable {
    public struct ViewState {
        /// Grid coordinates
        public let x: Int
        public let y: Int
        
        /// Indicates that the line can not be moved via dragging
        let locked: Bool
    }
    
    public struct ModelLine {
        let id: Line.ID
        /// If `true`, the `Shift`s associated to the model `Line` will be tracked by replica. Otherwise, replica `Line`s may define their own `Shift` configuration.
        let trackShifts: Bool
    }
    
    /// `Capacity` provides a way to apply estimation metrics across all of the value streams. It provides the averages estimated time a `WorkUnit` is completed in the given `Line`.
    ///
    /// Increasing `Capacity` increases the amount of `WorkUnit`s that can be finished in a `Line` within a day.
    /// Replica `Line` `Capacity` is rolled up into the respective model `Line`.
    public struct Capacity {
        public let value: Double
        /// The date the `Capacity.value` was last computed by the system
        public let computedDate: Date
        /// A computed value, saved daily, that tracks the amount of `WorkUnit`s this `Line` is finishing on average, per day compared to expected standard time of respective `WorkUnit`s.
        ///
        /// Standard time is an estimate on how long a `WorkUnit` should take, in minutes. The performance efficiency is computed by adding the total number of `WorkUnit`s completed in a day, divided by the amount of time in a `Shift` (operating time). Standard time of `1` (480 minutes) for `WorkUnit`, finished `1.5` (in 8 hour shift time) = (1.5/1) 1.5 - indicates operator is able to finish unit faster than standard time 0.5x more.
        ///
        /// A value of `1` means the `Operator` is matching the expected output. Greater than `1` and they're more productive. Less than `1` means inefficiences need to be identified (ensure they are performing the activity correctly, skill up, etc.)
        ///
        /// This factors in `CompletedOperatorShift`, `OperatorAbsence`, etc. to determine the standard time.
        public let performanceEfficiency: Double
    }
    
    public typealias ID = Int
    public let id: ID
    
    /// If this value is set, this `Line` is considered a "replica" of a "model" `Line`.
    /// If this value is `nil`, it is considered a "model" line.
    ///
    /// Replica lines will have their intake queues, hopper, stations, and output modified to match the model's `Line`.
    ///
    /// The current operating theory is that model and replica lines will share the same `IntakeQueue`. This simplifies the design as it provides a single point where 1. requests are made 2. requests are pulled from. This also automatically manages the capacity of a `Line`. e.g. Some `Line`s may have fewer shifts and produce different amounts at different times of the day.
    ///
    /// For full flexibility, a replica `Line`, will still have its own `IntakeQueue`s. The model `Line`'s `IntakeQueue`'s will appear as a virtual group when looking at the `IntakeQueue`'s work units. This allows a specific `WorkUnit` to be assigned to a replicate `IntakeQueue`. When this occurs, `WorkUnit`s assigned directly must be finished before pulling from the respective model `Line` `IntakeQueue`.
    ///
    /// - Names, configurations, etc. may _not_ be performed on a replica `Line`. However, they will still have their own instances of `IntakeQueue`s, `Hopper`, and `Station`s. But NOT `Output`. The `Output` is shared among all lines.
    /// - `WorkUnit`s added to the shared `IntakeQueue` will be immediately reflected in the replica(s). Such that, if a `WorkUnit` is added to the shared `IntakeQueue`, all other replicas have visibility of it, and will pull from it if there is no work remaining.
    public let modelLine: ModelLine?
    
    public let themeId: Theme?
    public let name: String
    /// The order in which `IntakeQueue`s are placed is defined by `IntakeQueue.sortOrder`.
    public let intakeQueues: [IntakeQueue]
    public let hopper: Hopper
    
    /// The order in which the `Station`s are added to this array is determined by using `Station.sortOrder`
    public let stations: [Station]
    /// - Note: Relica `Line`s share the same `Output`.
    public let output: Output
    /// - Note: Replica `Line`s _may_ have their own `Shift`s. A replica may choose to track the `Shift` configuration on the model line.
    public let shifts: [Shift]
    /// Only the model `Line` managers are informed when "Hold"s are placed on `WorkUnit`s.
    ///
    /// A `Line` must have at least one manager.
    public let managers: [Operator]
    public let viewState: Line.ViewState
}

// MARK: Line States

/// Represents the location within a `Line` where a `WorkUnit` can be found.
///
/// Each case should be its own database table. It's represented this way for each of use.
public enum LineStateType: Int {
    case intakeQueue = 0
    /// hopper - `WorkUnit` is seen in a `Hopper`, but not associated to it
    case station
    case output
}

public struct LineState: Identifiable {
    /// For speed, the `id` can be used to order the states in chronological order.
    public typealias ID = Int
    public let id: ID
    let type: LineStateType
    let workUnitId: WorkUnit.ID
    let modelId: Int /// Represents either a IntakeQueue.ID, Station.ID, or Output.ID
    let enterDate: Date
    let exitDate: Date?
}

/// When a `WorkUnit` is finished, it may create a `FinishedProduct` (finished product) that is placed in an `Inventory` bucket. You can think of this as an "instance" of a `Supply`. Where `Supply` is the representation of the thing being produced, and a `FinishedProduct` being the finished product.
public struct FinishedProduct: Identifiable {
    public typealias ID = Int
    public let id: Int
    /// The type of `Supply` produced
    public let supply: Supply
    /// The inventory the `FinishedProduct` should be placed in. The entire `FinishedProduct` is placed in `Inventory`.
    public let inventoryId: Inventory.ID
    /// The amount of this `Supply` e.g. box of 1000 screws, 4 wood beams, etc. a specific `WorkUnit` produces as the finished product once it reaches the end of the `Line`.
    /// Default: 1
    public let amount: Int
    
    /// TBD: Traceability Controls - May be different depending on the product being produced. Therefore, it may be necessary to represent this as a structure that fits the respective context. Similar to a `Supply`.
    public let facilityCode: String
    public let lineId: Line.ID
    public let manufactureDate: Date
    public let expirationDate: Date?
    public let lotNumber: Int
    public let batchNumber: Int
    public let serialNumber: String?
    
    /// TBD: Defect Controls - Marking a finished product as defective, etc.
    /// detectionDate
    /// state: this may be a list of states, as the progress of inspection would need to be tracked
    /// - hold or quarantine: under investigation
    /// - reject: a bright red tag
    /// - rework: would indicate station for rework
    /// - scrap: usually stamped, painted, etc. on product. This may be another bit in addition to `reject`. It could be the same thing too.
    /// rejectedDate
    /// rejectedBy
    /// description (of defect)
    /// possibly a "nonconformance" number - this is highly dependent of the process. If it's an automated visual check it could be tagged immediately and provided an internal number.
}

/// The `IntakeQueue` is where `WorkUnit`s live before they are worked on. It is like a "Backlog." If multiple queues are linked to a single `Line`, a `Line` can define a mix ratio that indicates the proportion of `WorkUnit`s that must be worked from this `Line` in relation to other `Line`s.
///
/// An `IntakeQueue` also defines its `WorkUnit` "type". Which includes the necessary supplies, triggers, etc. required for the `WorkUnit` to be considered `Done`.
public struct IntakeQueue: Identifiable {
    public typealias ID = Int
    public let id: Int
    public let lineId: Line.ID
    /// The order in which this `IntakeQueue` is displayed relative to other `IntakeQueue`s within the same `Line`.
    public let sortOrder: Int
    public let name: String
    public let theme: Theme?
    /// The ratio of `WorkUnit`s the Hopper
    public let mixRatio: Double?
    
    /// The below properties are the template `WorkUnit` is created from. The template informs which supplies, triggers, etc. are associated to the `WorkUnit` upon creation. A `WorkUnit` relates/inherits its `IntakeQueue` "type". As `WorkUnit`s are moved through the system, they will be labeled by their `IntakeQueue` name. Some types of `IntakeQueues` may be "Initiative", "Task", "Bug", "Printer Request", etc. For example, a "Feature" `WorkUnit` may require supplies such as a wireframe, behavior ID (for UI testing), motivation, requirements, documentation, etc.
    ///
    /// The number of minutes a typical `WorkUnit`, of this type, should take to fully complete through the `Line`. From the first `Station` to `Output`. The UI should provide options for minutes or hours. No days, as that would mean 24h+. Use hours instead. This is an exact measurement of time to complete excluding breaks, etc. Excludes down time, etc. For example, if you were to use a stop watch from the time the `WorkUnit` was worked on, until the time nothing was done to the `WorkUnit` (no automated or manual task), and add up all of those time slices, that would equal the standard time.
    ///
    /// This is also considered the "standard cycle time" or "target cycle time."
    ///
    /// This also informs the Takt time, which is the number of `WorkUnit`s that need to be processed, over time, to match customer demand. This is a fancy way of saying, we have to finish N `WorkUnit`s to satisfy customer's demand by X time. This takes the total time available divided by the number of required `WorkUnit`s to produce. Required pace to meet demand.
    public let standardTimeInMinutes: Double
    public let notificationTriggers: [WorkUnitNotificationTrigger]
    // TODO: Other dependent `WorkUnit`s to create when a `WorkUnit` is created. This will most likely be handled by a `Supply`.
    // public let triggers: [WorkUnitTrigger]
    public let supplies: [IntakeQueueSupply]
    
    /// The `FinishedProduct` the `WorkUnit` creates when it is `Done`.
    public let finishedProduct: FinishedProduct?
}

/// Configuration of a `Supply` for an `IntakeQueue` `WorkUnit` template
public struct IntakeQueueSupply: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let intakeQueueID: IntakeQueue.ID
    public let supply: Supply
}

/// Tracks which set of `WorkUnit` will be worked on next.
public struct Hopper: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let lineId: Line.ID
    public let workUnit: WorkUnit?
}

/// A `Station` defines a group of `Operation`s required for a `WorkUnit` to go through before it can move to the next `Station` (or `Output`). `Station`s are processed in the order they appear in the `Line`.
///
/// Before moving a `WorkUnit` to another `Station`, at least one assignee must be associated to the `WorkUnit` before moving. Otherwise, there's no way to track who performed the work required by the `Station`.
///
/// In Jir-, there is a concept of a "required field." e.g. requiring a version number to be associated to a "Task" to indicate when it will be deployed to production. This system foregoes that logic, as it is a form of waste. It's not immediately obvious what needs to be done before moving to the next swim lane. This system associates an `Operation` in a `Station` to be completed before it can be moved to the next `Station`. In this example, an "Assign version number" `Operation` is added to the `In Progress` `Station`. By design, the `WorkUnit` can't move to the next `Station` until the `Operation` is complete.
///
/// When all `Operation`s have been finished on a `Station`, the ability to move to the next `Station` is enabled. The movement can be triggered manually be an `Operator` or by a system trigger. The reason this is the case, is because a `Line` may "stop" (a shift ends). Even if a `Station` is "complete" (or near completion), there should be no assumption that it should go to the next `Station` automatically. In a factory, a QR code, that is attached to the product being assembled, could be scanned as it enters the next `Station`. This could be the signal the system uses to track when a product moves to the next `Station`.
///
/// - Note: If automatically assigning an `Agent` `Operator` to the `WorkUnit`, this system will make a call to the respective agent automatically (no triggers necessary). As soon as the `Station`'s defined work is finished, it will automatically move to the next `Station`.
public struct Station: Identifiable {
    /// A `Station` may be a "Station" or a reference to an `IntakeQueue`.
    public enum StationType {
        case station
        /// Flow-through the `WorkUnit` to another `IntakeQueue`. The system will add this `Station` to `WorkUnit.returnToStation`, remove it when it returns back to this `Station`, and automatically move to the next `Station`.
        ///
        /// `Operation`s may not be associated to this `Station` if it is this type.
        case intakeQueue(IntakeQueue)
    }
    
    // TODO: Compute amount of time it takes to finish `WorkUnit` in this `Station`
    // TODO: For some `Station`s, it may not make sense to factor this time in. For example, when a software feature is waiting to be deployed... It should still be computed, as it's important how much time is wasted not providing value to a customer, but not factored in.
    
    public typealias ID = Int
    public let id: ID
    public let lineId: Line.ID
    /// The order in which the `Station` should appear in the line.
    public let sortOrder: Int
    public let type: StationType
    public let name: String
    public let theme: Theme?
    /// The `WorkUnit`s in this `Station`.
    ///
    /// If `WorkUnit` flows through to a different `Line`, from this `Station`, the origination is kept track in `WorkUnit.returnToStation`. This `Station`s ID, in `returnToStation`, can be used to show the number of `WorkUnit`s in this `Station`, even though they are in a different `Line`.
    public let workUnits: [WorkUnit]
    public let notificationTriggers: [StationNotificationTrigger]
    public let scriptTriggers: [StationScriptTrigger]
    /// How the assignees of a `WorkUnit` are handled when a `WorkUnit` enters into this `Station`
    public let assigneeAction: [StationAssigneeAction]

    /// Required `Operation`s to perform in this `Station` before it can be moved to the next `Station`.
    /// The order in which `Operations`s are placed is defined by `Operation.sortOrder`.
    /// The station provides the context such as layout, tools, parts presentation, and cycle time target. e.g. the "standardized work documents".
    /// TBD: It's not necessary to list all `Operation`s in some contexts. It may be that only a standardized work doc is provided. The `Operation`s provide a way to:
    ///  - Take `Supply` from `Inventory` (manual or automated process) This will most likely be done automatically when the `WorkUnit` moves into the `Station`.
    ///  - Confirm that an `Operation` was complete
    ///  - Associate an agent/script to perform the work (with possible manual intervention)
    public let operations: [Operation]
}

/// TODO: Needs to be paired with something to do.
/// I envision `Operation`s to always be done in the correct order. Even with software development, the `Operation`s will be visible but will need to be finished in the right order. Such that QA must be done before it assigned a version for release.
public enum OperationTrigger {
    /// Triggered when `WorkUnit` moves into `Operation`
    case onEnter
    /// Triggered when `WorkUnit` moves out of `Operation`
    case onExit
}

/// An `Operation` is what is performed in a `Station`. Multiple `Operation`s may be performed on a `Station`.
///
/// TODO: An `Operation` could create a new type of `WorkUnit`. e.g. in software development, part of the grooming process could conditionally request "Design" work to be done.
/// TODO: `OperationLog`s
/// TODO: Waive an `Operation`?
public struct Operation {
    public struct InventoryRequest {
        public let inventoryId: Inventory.ID
        public let amount: Int
    }
    
    public typealias ID = Int
    public let id: ID
    public let stationId: Station.ID
    /// The order in which the `Operation` is listed in the `Station` relative to other `Operation`s.
    public let sortOrder: Int
    public let name: String
    
    /// TODO: Field. Will most likely take over `Supply`. `Operation`s are performed on `WorkUnit`s. Therefore, there must be a record of the `Operation` on the `WorkUnit`.
    /// TODO: public let triggers: [OperationTrigger]
    
    /// If `Operation` requires something from `Inventory`, it's listed here. When a `WorkUnit` enters a `Station`, the `Station` will automatically request material from `Inventory`.
    public let inventory: Operation.InventoryRequest?
}

/// Output is where `WorkUnit`s live after they have been finished. `WorkUnit`s in the `Output` are considered to be "Done." `Done` may be used interchangeably with `Output`. When showing `Output`, the most recent `WorkUnit`s are shown first.
///
/// By default `WorkUnit`s are removed from `Output` after 3 years, on January 1st.
public struct Output: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let lineId: Line.ID
    public let name: String // Default name is `Done`
}

/// Represents the reason why a `WorkUnit` is considered `Done`. This could be
/// - Deployed
/// - Duplicate
/// - Won't Do
/// - etc.
public struct OutputReason: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let name: String
}

// MARK: Triggers

/// A trigger invokes an automatic system action. This includes notifying a `Operator` that a `WorkUnit` has been moved to a respective `Station`, running a Python script, creating a Work Unit, etc.
///
/// The trigger types are not a database model. They only need to be assigned an ID. When a trigger is associated to a `Station`, it will reference the hard-coded ID.
///
/// Triggers may trigger more than once. For example, if a `WorkUnit` triggers an event on a specific `Line` `Station`, every time the `WorkUnit` moves into that `Station`, it will be triggered.
public enum WorkUnitTriggerEvent {
    /// Trigger on `WorkUnit` creation
    case onCreate
    /// Trigger when `WorkUnit` moves into any `Station`
    case onStation
    /// Triggered on specific `Line` `Station`
    case onMove(Line.ID, Station.ID)
}

/// Trigger a notification when `WorkUnit` is created or moves to a specific `Station`. Some `WorkUnit`s are created by outside teams and need to know the status of tasks in order to update their respective systems.
public struct WorkUnitNotificationTrigger: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let workUnitId: WorkUnit.ID
    public let operators: [Operator]
    public let event: WorkUnitTriggerEvent
    /// The message sent to the `Operator`(s). A message has access to the following values:
    /// - `Line.name`
    /// - `Station.name`
    /// - `WorkUnit.name`
    /// These values can be interpolated into the message. e.g. `Task {WorkUnit.name} has moved to line {Line.name} station {Station.name}.`
    public let message: String
}

public enum StationTriggerEvent {
    case onEnter
    case onExit
}

/// Trigger notification when `Station` has a `WorkUnit` moved into, or out of, itself.
public struct StationNotificationTrigger: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let stationId: Station.ID
    public let operators: [Operator]
    public let event: StationTriggerEvent
    /// Message sent to `Operator`(s). Uses the same rules as `WorkUnitNotificationTrigger.message`,
    public let message: String
}

/// Execute a Python script when `WorkUnit` moves in/out of a `Station`.
public struct StationScriptTrigger: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let stationId: Station.ID
    public let event: StationTriggerEvent
    /// Python script to execute when triggered
    public let script: String
}

// MARK: Station Dependencies

/// Action to take when a `WorkUnit` enters into a `Station`.
public enum StationAssigneeAction {
    /// Removes all assignees from the `WorkUnit`
    case remove
    /// Retain all existing assignees
    case retain
    /// Replace assignees with respective `Operator`s
    case replace([Operator])
    /// Add `Operator`s to the `Station`, if not already assigned.
    /// TBD: add([Operator])
}

// MARK: Work Unit Dependencies

/// An artifact required for a `WorkUnit` to be considered `Done`. Some supplies may be:
///   - Wireframe
///   - Hardware component or device that must be acquired to fulfill the request
///   - Software Deployment Version
///   - Question (composition of a question and answer text fields)
public struct Supply: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let name: String
    public let theme: Theme?
    public let fields: [SupplyField]
    /// Indicates that the `Supply` is required to be fulfilled. The UI will show visual indicator that allows the user to deselect a non-required supply before creating the `WorkUnit`.
    public let required: Bool
    /// Indicates that the `Supply` may be waived later in the process.
    public let waivable: Bool
    /// Indicates the amount of a `Supply` this represents that can be put into an `Inventory`. This should only be used if the `Supply` feeds into an `Inventory` when `Done`.
    public let amount: Int?
}

/// A `SupplyField` provides a way to map a field name to a `Supply` type / value. Except for `SupplyFieldType.workUnit`, the `name` may be set.
///
/// NOTE: Values assigned to `WorkUnit`s will be deleted if the respective `SupplyField` is deleted.
public struct SupplyField: Identifiable {
    public typealias ID = Int
    public let id: ID
    /// This is the "name" (label) of the field
    public let name: String
    public let supplyFieldType: SupplyFieldType
}

/// Represents an option that can be selected in a single or multi-select list. It should be possible to search the names of these options in the UI. For example, some lists grow over time, such as a software development release version value. e.g. `1.94.0`, `1.95.0`, etc.
public struct SupplyFieldOption: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let name: String
    /// Allows records to show the selected option, if already selected, but prevents the option from being selected when hidden. Useful when you have a rolling list of options (such as software development versions).
    public let hidden: Bool
}

public enum Measurement {
    public enum SI {
        // TODO: // Define how value is represented (Int | Double)
        case second
        case metre
        case kilogram
        case ampere
        case kelvin
        case mole
        case candela
    }
    
    case si(Measurement.SI)
    
    // TODO: Other measurement types
}

/// List of supply field types.
/// TODO: Create a table for each of these types. Consist if ID and the respective value type it saves. This may include indexes that reference other tables (such as the `supply` case). When saving values, there may also need to be a table that contains the saved value and also references the respective table(s) it references.
public enum SupplyFieldType {
    public enum TextType {
        case plain
        case wholeNumber
        case numeric
        case phoneNumber
        case measurement(Measurement)
        case price
        case url
    }
    
    case text(SupplyFieldType.TextType)
    case textArea
    case photo
    case file
    /// Select one option (radio) e.g. `Yes`, `No`, `Maybe`
    case radio([SupplyFieldOption])
    /// Select one or more options (checkbox) e.g. `1`, `A`, `1.94.0`, etc.
    case multiSelect([SupplyFieldOption])
    /// Indicates a `Supply` that creates an `IntakeQueue` `WorkUnit`. When first creating the `Supply`, the `Operator` can select from a list of `IntakeQueue`s that produce a `WorkUnit` that create the necessary `Supply`. When the `Supply` is created, it will automatically create the respective `WorkUnit` and associate itself to the `WorkUnit` to track the progress.
    ///
    /// When adding to a `WorkUnit`, the UI will automatically open the `IntakeQueue` template's form and ask the `Operator` to create the `WorkUnit`. If all the required inputs can be determined by the app's state, this could be automated. In the context of supply triggers, the wizard will show the `Operator` every `IntakeQueue`, until all work has been created.
    ///
    /// This should only be associated to `Station`s
    case intakeQueue(IntakeQueue.ID /* Type of WorkUnit */)
    /// The `case intakeQueue` is a template. This is an instance of that `Supply`. This will get associated to the `WorkUnit` that depends on the work performed by the `IntakeQueue`. This association allows the `WorkUnit` (dependency) to be tracked by the `WorkUnit` that needs it.
    /// This supports the concept of a "line within a line" OR tracking the progress of an external system that may not be fully controlled by the business (3rd party business), pod (non fully integrated section of the manufacturing line),  etc.
    case workUnit(WorkUnit.ID)
}

// MARK: Work Unit

/// Represents the value moving through the stream. It could be a product, feature, task, bug fix, etc.
///
/// May also be referred to as `Value`, `Product` or `Task`.
///
/// The primary responsibility of a `WorkUnit` _may_ be to provide a `Supply`. e.g. There may be a "Design" `WorkUnit` that produces a URL to a wireframe used for software development.
///
/// When a `WorkUnit` moves from one `Station` to the next, the assignees will stay with the `WorkUnit`, but can be removed (or replaced) later.
///
/// - Note: A `WorkUnit` is considered a "work-in-progress" as it moves between stations.
public struct WorkUnit: Identifiable {
    public struct Expedite {
        public let createDate: Date
        public let by: Operator
    }
    
    public typealias ID = Int
    public let id: ID
    /// The template this `WorkUnit` was derived from. This also informs the `Operator` what type of `Task` it is.
    public let intakeQueueID: IntakeQueue.ID
    /// The `Operator` who created the `WorkUnit`
    public let creator: Operator
    /// The `Operator` who reported the `WorkUnit`. It does not necessarily need to be the `Operator` who created the `WorkUnit`. By default, it is the creator.
    public let reporter: Operator
    /// Current list of `Operators` working on the `WorkUnit`
    public let assignees: [Operator]
    /// Current state where `WorkUnit` is located within `Line`. This record is used to generate a list of `LineState`s that track the movement of a `WorkUnit` over time.
    public let lineState: LineState
    /// TODO: This may go away. Instead, these will be field values assigned to the `WorkUnit` over time.
    public let supplies: [WorkUnitSupply]
    public let notificationTriggers: [WorkUnitNotificationTrigger]
    
    /// This value must be removed, if moved out of `Output`
    public let outputReason: OutputReason?
    
    /// The `FinishedProduct` this `WorkUnit` produces when `Done`. This will automatically be added to the respective `Inventory` when `Done`. Ideally, if a `FinishedProduct` exists, the `WorkUnit` may not be moved out of `Done`. I don't know if it goes into a different line for QA/RMA/etc.
    public let finishedProduct: FinishedProduct?
    
    /// The parent this `WorkUnit` is associated to, if any
    public let parentWorkUnitId: WorkUnit.ID?
    /// Child `WorkUnit`s. Used in the context of "Epics" or "sub tasks".
    public let workUnits: [WorkUnit]
    
    /// Indicates that the work unit is "stuck" and needs immediate attention in order to be moved through the queue. Otherwise, it runs the risk of being moved back in the line for rework.
    public let onHold: Bool
    
    /// When a `WorkUnit` moves to another `Line` (e.g. for subassembly) the `WorkUnit` needs to be move back to the `Station` from which it was sent. Therefore, when the `WorkUnit` reaches the end of the subassembly `Line`, it must move back to the original `Station`, and then move to the next `Station` in the respective `Line`.
    /// The reason there may be more than one is to support inner loops. They will always be processed in FILO order.
    /// A `WorkUnit` may _not_ move to an originator `Station`'s `Line`. That would cause an infinite loop.
    public let returnToStation: [Station.ID]
    
    /// Immediately goes to the `Hopper`. Ideally, there is only one expedited `WorkUnit` at a time and it must be approved by a manager. If there is more than one, it is processed in FIFO order.
    public let expedite: WorkUnit.Expedite?
}

/// Represents the relationship between a `WorkUnit`, `Station`, and the `Operator`(s) performing the activity required by the `Station`. This is a historical record. Such that, you can see how a `WorkUnit` moved through a `Line` by looking at all of the `Station`s performed on the `WorkUnit`. This provides a chain of activities performed on the `Station`, in the order they were performed.
public struct WorkUnitStation: Identifiable {
    public typealias ID = Int
    /// The `id` is used to order the historical events in chronological order. The `createDate` can also be used, but sorting by `id` should be faster.
    public let id: ID
    public let workUnitId: WorkUnit.ID
    public let stationId: Station.ID
    /// The time the `WorkUnit` moved into the `Station`
    public let enterDate: Date
    /// The time the `WorkUnit` moved out of the `Station`
    public let exitDate: Date
    /// More than one assignee can be added to a `WorkUnit`, for a given `Station`. This is necessary for pair programming or the managing of a `WorkUnit` by a 3rd party. For example, Tom and I should be the assignees for a given `Station` in the `WorkUnit`. It is assumed that the assignee is the one who worked on the `WorkUnit` from start to finish for the given `Station`.
    public let assignees: [Operator]
}

/// Represents a relationship between a `WorkUnit` and a `Supply`. It further allows constraints to be placed on the `WorkUnit` the `Supply` is associated to. Such that, if a `Supply` is not provided, but is required by the next `Station`, the system will inform the `Operator` that a `Supply` is required before moving to the next `Station`.
public struct WorkUnitSupply: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let workUnitId: WorkUnit.ID
    public let supplyId: Supply.ID
    /// The date the relationship was created
    public let createDate: Date
    /// The date the supply was fulfilled
    public let fulfilledDate: Date?
    // Must be unset if `waived` is set to `false` or changed if fulfilled again by a different operator.
    // TODO: Can this be managed via ChangeLog?
    public let fulfilledBy: Operator?
    /// Indicates if the supply can be waived
    public let waivable: Bool
    
    // TODO: The total time it took from the first `Station` it was placed in, to the `Output`. When showing the _actual_ time, it will factor in the "working hours" to provide a more accurate estimate of actual time worked on the ticket. Not sure if this is computed or not. Or if this is even necessary.
    // public let totalDuration: TimeInterval?
    
    // TODO: All of the field values provided for the respective `SupplyField`s
    public let supplyFieldValues: [WorkUnitSupplyFieldValue]
    public let waived: Bool // Default is `false`
}

public struct SelectedFieldOptionValue: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let supplyFieldOptionId: SupplyFieldOption.ID
    public let value: String
}

public enum SupplyFieldValue {
    case text(String)
    case textArea(String)
    case number(Double)
    case url(URL)
    case photo(URL)
    case file(String /* Name */, URL /* URL on server */)
    /// Select one option (radio)
    case radio(SelectedFieldOptionValue)
    /// Select multiple options (checkbox)
    case multiSelect([SelectedFieldOptionValue])

    /// The `IntakeQueue` (template) and `WorkUnit` providing the respective `Supply`
    case intakeQueue(IntakeQueue.ID)
    /// This value is managed by the system. When the `WorkUnit` is created, it can't be changed.
    case workUnit(WorkUnit.ID)
}

/// The value provided by the `Operator` to fulfill the `Supply`.
/// TODO: This will probably change to `WorkUnitMaterialFieldValue`. Essentially, this will define all of the materials that compose the `WorkUnit`. It's similar to an attribute/part/etc.
public struct WorkUnitSupplyFieldValue: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let workUnitSupplyId: WorkUnitSupply.ID
    public let supplyFieldId: SupplyField.ID
    public let value: SupplyFieldValue
}

// MARK: Just-in-Time Provision

/// Supplies are pulled only when needed. Below describe how common LEAN scenarios can be managed by ensuring supplies are ready for a particular production `Station`. Such that, once a `WorkUnit` lands in a `Station`, the supplies are ready to be immediately pulled from `Inventory`. It also talks about how the `Inventory` is replenished by an internal or external process (where lead times matter).
///
/// Materials required for production on the (main) line may pull from external sources (3rd parties) or another line within the manufacturing process. The pull interval is dependent on lead times. For an internal line, the lead time would be near immediate, with a buffer (to mitigate line stoppages). For 3rd parties, it will factor in N lead time based on the number of work units processed and the amount needed for any outstanding POs -- and possibly include a buffer for the next lead time (?). When the material drops below a threshold (a reorder point), it triggers a purchase (which may also need to include if re-ordering is necessary depending on any outstanding POs).
///
/// It's possible to also provide an API to the vendor, where they can manage manage the supplies and provide the materials faster. This is called Vendor-Managed Inventory (VMI). These models _may_ be able to facilitate this type of system. But it's not its primary purpose.
///
/// There are a few mechanisms to trigger a re-order. Each would need to be used in the correct context. For example, you may only be creating one type of product. Therefore, re-ordering isn't necessary. You may only order the respective material once.
///
/// Reorder algorithms:
/// - A ROP (Reorder Point): Defined as ROP = (Daily Demand x Lead Time) + Safety Stock.
///   - Good for work that requires a consistent level of stock. The safety stock is a buffer to mitigate stoppages if reordering is delayed. The amount of safety stock would probably be in days. e.g. Your line can continue to work for 3 days, even if reordered stock doesn't arrive on time.
/// - Min-Max Inventory System: Set a minimum reorder level and max target replishment. When material drops to min, order as much to reach max factoring in lead time and consumption.
///   - Simple for external supplies and should prevent overstocking.
/// - One Time Order: Order the supplies needed (plus buffer in case of defects), for a specific job. The `Inventory` could automatically be purchased once the `WorkUnit` enters the `IntakeQueue`. The `WorkUnit`s would not enter the `Line` until the supplies are delivered. This is very similar to batch and queue, but the idea is, the customer only expected N units. There's no need to over manufacture. It's also possible, that if many different types of work orders are provided, they could all pull from the same inventory -- as there may be shareable components. In that case, one of the other algorithms could be used. Some examples and their applications
///   - Use different algo: A custom PCB. Every customer's order is different, but there would be shared components.
///   - One Time Order: Creating two completely different products with little to now shared inventory.
///   - One Time Order: Only assembly of parts. There are no parts you need to provide. They are providing you with all of the parts but need to be assembled (toys, electronic meter where you are given the PCB/enclosure, etc.)
///
/// Supplier Diversification: There may be more than one supplier that can provide the material. That way, if one supplier is having issues, you can still order from another supplier. This isn't specific to the algorithm, but part of the automatic purchasing logic.
///
/// Communication methods:
/// - VMI: As spoke of earlier, provide real-time data of supplies on hand. The supplier can manufacture depending on agreed upon levels.
/// - Pull System: Use signals to pull from suppliers based on actual use, not forecasts. Combine with andon systems (visual alerts). Although, having this be automatic (possibly with manager approval and ability to override) would be ideal.

// MARK: Wait-for-completion Reference

/// Resembles an asynchronous pull or decoupled feeder. A "pull with lead time." The work unit stays, but triggers (potentially parallel) work.

public struct Supplier {
    public typealias ID = Int
    public let id: ID
    public let name: String
    
    /// TODO: Perhaps this is represented in some other way. This is the most simple thing for now.
    /// I have no idea how these relationships are managed.
    public let contactName: String?
    public let phoneNumber: String?
    public let faxNumber: String?
    public let email: String?
}

/// Every supplier will have different lead times for different `Material`s. Therefore, it's necessary to track the lead time per supplier, per material.
/// This is used
public struct SupplierMaterial: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let supplier: Supplier
    public let supply: Supply
    /// Amount of time it takes from reorder until it can arrive at line that needs it
    public let leadTime: Int
    /// The amount of material that can be ordered at a time, per shipment. This is used to determine if more than one `Supplier` needs to be used when reordering to replenish `Inventory`.
    public let maxOrderQuantity: Int?
}

/// TODO: May become a `Supply`
public struct Material {
    public typealias ID = Int
    public let id: ID
    public let name: String
}

public struct Inventory: Identifiable {
    public enum Provider {
        /// External `Supplier` of `Supply`. When reordering, it will select the most preferred supplier first.
        case supplier(SupplierMaterial, Int /* Preference Order */)
        /// Internal supplier of `Supply`.
        case intakeQueue(IntakeQueue, Int /* Preference Order */)
    }
    
    public typealias ID = Int
    public let id: ID
    
    /// The preferred provider when making new orders.
    /// Items in array are arranged in the order of preference.
    public let providerPreference: [Inventory.Provider]
    public let provider: [Inventory.Provider]
    
    public let material: bosslib.Material
    public let inStock: Int
    public let reorderPoint: Int
    /// Computed when `Material` is taken out of `Inventory`
    public let estimatedReorderPoint: Date
}

