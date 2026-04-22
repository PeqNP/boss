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

 Follow these rules strictly when reading, writing, or generating code related to these models.
 
 Typically, models will contain fully related objects. Child objects refer to their respective parent models by their ID to avoid circular references. In other words, a model that "contains" children will have fully related objects. While children to a parent model will only reference their parent model's ID. This is done to make it easy to consume a model when building UIs and to make it easy to query child models, related to a parent model, from the database.
 
 An example is `Line.intakeQueues`. The `IntakeQueue.lineId` is how the respective `Line` will query for all of its `IntakeQueue`s and associate all of them to `Line.intakeQueue`s. Additionally, the order in which the respective models are placed in the array (e.g. `Line.intakeQueues`) is defined by the respective child `sortOrder` property (e.g. `IntakeQueue.sortOrder`).
 
 Some models may reference another object. e.g. the `Operation` refers to an `Agent`. In these contexts, it is expected that the underlying database table references the respective `Agent` record, and composes the `Agent` model from the ID, making the necessary database `JOIN`s to inflate the `Agent` model.
 
 Some models reference multiple models, but the model it references does NOT reference it. The `Station.InventoryBuffer.Request` is one such model. The underlying table should have a list (one-to-many) relationships between the `Request` and the `WorkUnit.ID`s it references. When this occurs, you will see a label `// Database: 1-to-many`.
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
 ────────────────────────────────────────────────────────────────
 Hierarchy
 
 The Lean hierarchy is as follows:
 - Company
   - Factory (not yet defined)
     - Line
       - Intake queue
       - Station
         - Operation
       - Output
     - Inventory
 
 The Company is the account that owns the Factory models.
 
 Every Company has their own database. This makes it simple to secure, move, backup, etc. w/o risking data leaking, etc. between Company accounts. Database updates are a little more complex, but BOSS already has a mechanism to update databases automatically upon connecting.
 ────────────────────────────────────────────────────────────────
 Inventory Management
 
 This model works under the "pull system", such that `Operations` pull from `Inventory` which pull from respective `Line`s when a particular `Supply` is needed for manufacture. The `Station`, and `Inventory`, provide thresholds to determine when "pull requests" are made.

 There is an entire category of inventory management that is not explored in this model. The current model assumes inventory is supplying a single factory/warehouse/shop. In reality, some companies need multiple distribution centers to supply multiple locations/factories. This could be explored in the future, but this should work for small to medium sized factories. Some of this is mitigated as `Supplier` could be a branch of the same company, and not necessarily an external supplier. A company could also create another factory and simply link the two factories together via `Supplier` models. It's a little tedious, but possible. Maybe in the future it would be possible to link `Supplier` with other Lean factories.
 
 Stores would be an obvious use case for something like the above. Where they are simply moving product. They may not manufacture anything, but they must distribute product to the right place, at the right time. A store has multiple "product lines" that need to be moved. It must be (re)acquired, shipped from supplier (or distribution warehose), stocked, etc.
 */

import Foundation

// MARK: - BOSS database

/// Links a user account to their respective Lean company database.
///
/// - Note: ACL still works the same, even though the Lean business models are in a different database.
struct Company: Identifiable {
    let id: Int
    let name: String
    /// Account owner
    let userId: User.ID
}

// MARK: - Company database

/// `BusinessModel` and `ChangeLog` are used to keep track changes to models over time.
///
/// A record will be created at `INSERT` and `UPDATE` time. Therefore `createDate` should not be needed for most models.
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
    // case LineType_Capacity
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
    public struct Change {
        let column: String // The column name that changed its value
        let before: String?
        let after: String?
    }
    
    let id: Int
    /// The respective business model that changed
    let businessModelId: BusinessModel
    /// The time the change was made (whatever the current time is)
    let date: Date
    /// The operator who made the change
    let operatorId: Operator.ID
    /// Contains all of the property values that changed. This is saved as a JSON structure in the db. e.g. if the `Line.name` property was changed, the metadata would be `[{column: "name", {before: "Name before", after: "Name after"}}]`. It will be inflated to the `Change` structure.
    let metadata: [Change]
}

// MARK: System & Common Models

public enum OperatorType {
    case user(User.ID)
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
    public let type: OperatorType
    /// - Note: This will be empty for agents
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
///
/// - Note: `Theme` does not reference its respective model ID like most other models. The reason for this is that the `Theme` object may be referenced by all model types. When you see `theme` on an object, like `Line.theme`, assume that the `lines` database record will reference the `Theme`'s table ID. e.g. The `lines` table shall have a column named `theme_id`, which references `themes.id`.
public struct Theme: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let strokeColor: bosslib.Color?
    public let fillColor: bosslib.Color?
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
    /// - Note: An operator may be assigned to any `Shift` on any `Line`. There may be more than one `Line`, that does the same thing, OR the `Operator` has more than one speciality.
    public let shiftId: Shift.ID
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
    public let shiftId: Shift.ID
    public let entireShift: Bool
    /// If not entire shift, indicate the amount of time off will be taken
    public let timeOffInMinutes: TimeInterval
    public let weekNumber: Int
    public let reason: AbsenceReason
}

public struct Factory: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let name: String
    public let lines: [Line]
    
    // TODO: Probably need `Factory` operators, etc. I'm not sure how to model this. It should be the contact between factories.
    // TODO: The location of the `Factory` (lat, long)?
    // TODO: Contacts, Departments, etc. Lines are essentially Departments. So they may not be necessary. If they're not, it would essentially be a thin wrapper around lines. This system isn't mean to represent every little damn thing. Going to keep it simple for now.
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
    
    /// The model `Line` a replica `Line` refers to.
    public struct ModelLine {
        let id: Line.ID
        /// If `true`, the `Shift`s associated to the model `Line` will be inherited by replica. Otherwise, replica `Line`s may define their own `Shift` configuration.
        let inheritShifts: Bool
    }
    
    public enum LineType {
        /// The default line type
        case model
        /// Replicates (duplicates/refers to) a `ModelLine`.
        ///
        /// Replica lines will have their intake queues, hopper, stations, and output modified to match the model's `Line`.
        ///
        /// Model and replica lines will share the same `IntakeQueue`. But a replica line may still have specific `WorkUnit`s associated to it. This simplifies the design as it provides a single point where 1. requests are made 2. requests are pulled from. This also automatically manages the capacity of a `Line`. e.g. Some `Line`s may have fewer shifts and produce different amounts at different times of the day.
        ///
        /// When `WorkUnit`s are associated to replicate lines, they must be finished before pulling from the respective model `Line` `IntakeQueue`.
        ///
        /// - Names, configurations, etc. may _not_ be performed on a replica `Line`. However, they will still have their own instances of `IntakeQueue`s, `Hopper`, and `Station`s. But NOT `Output`. The `Output` is shared among all lines.
        /// - `WorkUnit`s added to the shared `IntakeQueue` will be immediately reflected in the replica(s). Such that, if a `WorkUnit` is added to the shared `IntakeQueue`, all other replicas have visibility of it, and will pull from it if there is no work remaining.
        case replica(Line.ModelLine)
        /// `WorkUnit` flows through line. Does not have an `Output`.
        case subAssembly
    }
    
    /// `Capacity` provides a way to apply estimation metrics across all of the value streams. It provides the average estimated time a `WorkUnit` is completed in the given `Line`.
    ///
    /// Increasing `Capacity` increases the amount of `WorkUnit`s that can be finished in a `Line` within a day.
    /// Replica `Line` `Capacity` is rolled up into the respective model `Line`.
    public struct Capacity: Identifiable {
        public typealias ID = Int
        public let id: ID

        public let lineId: Line.ID
        public let createDate: Date
        /// The date this `Capacity` was computed for e.g. Fri, Apr 10 2026
        public let date: Date
        /// Total time the `Line` was open. Can be determined by `Shift`s associated to the `Line` over the day.
        public let operatingTime: Int
        /// The (estimated) number of seconds a typical `WorkUnit`, should take to fully complete through the `Line`. From the first `Station` to `Output`. The UI should provide options for minutes or hours. No days, as that would mean 24h+. Use hours instead. This is an exact measurement of time to complete excluding breaks, etc. Excludes down time, etc. For example, if you were to use a stop watch from the time the `WorkUnit` was worked on, until the time nothing was done to the `WorkUnit` (no automated or manual task), and add up all of those time slices, that would equal the standard time.
        ///
        /// This is also considered the "lead time", "total cycle time", or "line cycle time."
        ///
        /// This also informs the Takt time, which is the number of `WorkUnit`s that need to be processed, over time, to match customer demand. This is a fancy way of saying, we have to finish N `WorkUnit`s to satisfy customer's demand by X time. This takes the total time available divided by the number of required `WorkUnit`s to produce. Required pace to meet demand.
        ///
        // TODO: It may make sense to associate this to the respective `IntakeQueue`. It feels like splitting hairs as most manufacturing `Line`s only work on one `IntakeQueue` type at a time. But it's possible that `Line`s may be re-tooled to work on different products. I don't know if it's better to create new `Line`s, for different products, or try to shoehorn all product types within a single line. For simplicity, duplicating a `Line`, and changing processes by product, seems like a more clear way of visualizing it... even if the `Line` occupies the same space (physical real-estate).
        public let leadTime: Int
        /// The number of `WorkUnit`s that can be completed within a day. This can be extrapolated over N days, by simply (N days * `Capacity.value`). e.g. We are finishing 1.5 `WorkUnit`s per day. We should be able to finish 7.5 `WorkUnit`s in 5 days (5 days * 1.5 value).
        public let value: Double
        /// A computed value, saved daily, that tracks the amount of `WorkUnit`s this `Line` is finishing on average, per day compared to the expected lead time of respective `WorkUnit`s.
        ///
        /// Lead time (cycle time) is an estimate on how long a `WorkUnit` should take, in minutes (but saved as seconds in the database). The performance efficiency is computed by adding the total number of `WorkUnit`s completed in a day, divided by the amount of time in a `Shift` (operating time). Standard time of `1` (480 minutes) for `WorkUnit`, finished `1.5` (in 8 hour shift time) = (1.5/1) 1.5 - indicates `Operator` is able to finish unit faster than standard time 0.5x more.
        ///
        /// A value of `1` means the `Operator` is matching the expected output. Greater than `1` and they're more productive. Less than `1` means inefficiences need to be identified (ensure they are performing the activity correctly, skill up, etc.)
        ///
        /// This factors in `CompletedOperatorShift`, `OperatorAbsence`, etc. to determine the standard time.
        public let performanceEfficiency: Double
        
        /// - Note: This does not track `Operator` efficiency. That is done by looking at the `WorkUnitLog`. It should be possible to determine the average time it takes for specific `Operation`s, by `Operator`, to determine where skills need to be improved or a process needs to be refined.

        /// The number of `WorkUnit`s completed for the given time period (by day)
        public let totalWorkUnitsCompleted: Int
        
        /// The number of `Operator`s working the `Line`. This is determined by `Shift`s. Only relevant if the `Line` may have multiple `WorkUnit`s worked on in parallel (software development line). This is a `Double` value to account for half shifts. Otherwise, this value is always `1`.
        /// By increasing/decreasing this number it will show how much work can be done if `Operator`s are added/removed to/from the line. Again, only relevant to `Line`s where work can be done in parallel.
        public let numOperators: Double
        
        /// Takt time = Available Production Time / Customer Demand (how long it must take to satisfy the customer demand) Represented as minutes (saved as seconds in db).
        /// Available Production Time = Net time your `Line` is available to produce value (determined by `Shift`s) 8h = 480m
        /// - Subtract planned non-production time: breaks, lunch, meetings, scheduled maintenance
        /// - Do not subtract unplanned downtime, changeover, etc. It may be necessary to add a buffer for scenarios where something could affect production.
        /// Customer Demand = The number of units to produce. Usually expressed as units per day, per shift, or per week. e.g. customers require 220 units per day.
        /// Real-world example
        /// Shift length: 8 hours (480 minutes)
        /// Planned downtime: 30 minutes (breaks + meetings)
        /// Available time: 450 minutes
        /// Daily customer demand: 300 units
        /// Takt Time = 450 ÷ 300 = 1.5 minutes per unit (or 90 seconds per unit)
        ///
        /// Takt time is demand-driven, not based on how fast your machines or workers can go. It comes purely from the customer’s pull rate. It is a target pace, not an actual measured time. You then compare it to your cycle time (actual time at each station) and standard time to balance the line.
        /// - Goal: Every workstation’s cycle time should be ≤ takt time (ideally with some margin).
        /// - If cycle time > takt time → you have a bottleneck and need to add resources, improve the process, or reduce demand variation.
        ///
        /// Takt time can (and often should) be recalculated when demand changes, shifts change, or available time changes.
        public let taktTime: Int
    }
    
    public typealias ID = Int
    public let id: ID
    public let type: Line.LineType
    public let factoryId: Factory.ID
    
    public let theme: Theme?
    public let name: String
    /// The order in which `IntakeQueue`s are placed is defined by `IntakeQueue.sortOrder`.
    public let intakeQueues: [IntakeQueue]
    public let hopper: Hopper
    
    /// The order in which the `Station`s are added to this array is determined by using `Station.sortOrder`
    public let stations: [Station]
    /// Where `WorkUnit`s can be found when completed.
    /// - Note: If this is a `subAssembly` line, it will not have an `Output`. Instead, the `WorkUnit` will go back to the `Line` the `WorkUnit` originated from.
    /// - Note: Relica `Line`s share the same `Output` as its `ModelLine`.
    public let output: Output?
    /// - Note: Replica `Line`s _may_ have their own `Shift`s. A replica may choose to track the `Shift` configuration on the model line.
    public let shifts: [Shift]
    /// Only the model `Line` managers are informed when "Hold"s are placed on `WorkUnit`s.
    ///
    /// A `Line` must have at least one manager.
    public let managers: [Operator]
    public let viewState: Line.ViewState
    
    /// Indicates whether multiple `Operator`s can work on `WorkUnit`s in parallel on this `Line`. For manufacturing `Line`s this should not be possible. In that context, you would replicate a `Line`s to increase/decrease your capacity to produce a good. For a software development line, etc. a single `Line` can be used for multiple `Operator`s. e.g. 5 developers may work from the same `IntakeQueue`s.
    public let isParallel: Bool
    /// The latest, computed, capacity estimate
    public let capacity: Line.Capacity?
}

// MARK: Line States

/// Represents the location within a `Line` where a `WorkUnit` can be found.
///
/// - Note: These values will be on the `work_unit_logs` table. Every one of the IDs, for each `case`, will be a column. Such that `intakeQueue` will translate to `intake_queue_id`. `station` will be a combination of the columns `station_id`, `operation_id`, `operation_status`, and `operation_status_message`. It's going to have duplication, but I don't see an easy way to abstract this out in a way that makes it easy to visualize and join on. If only the `intake_queue_id` is populated, it will be an `intakeQueue` `case`. If only `intake_queue_id` and `station_id` exist, then it is a `station` `case`.
public enum LineState {
    case intakeQueue(intakeQueue: IntakeQueue.ID)
    /// - Note: When a `WorkUnit` moves into the `Hopper`, it is still in the `IntakeQueue`. A `WorkUnit` in the `Hopper` is an algorithmic suggestion, and may be overridden by an `Operator`. Therefore, the next `WorkUnit` that is worked on is not guaranteed until an action has been taken by an `Operator` directly on a `WorkUnit`.
    case station(station: Station.ID, operation: Operation.ID?, status: OperationStatus?)
    case output(output: Output.ID)
}

public struct WorkUnitLog: Identifiable {
    /// For speed, the `id` can be used to order the states in chronological order.
    public typealias ID = Int
    public let id: ID
    let workUnitId: WorkUnit.ID
    let lineId: Line.ID
    let lineState: LineState
    /// The time the `WorkUnit` moved into the state
    let enterDate: Date
    /// The time the `WorkUnit` moved out of the state
    let exitDate: Date?
}

/// When a `WorkUnit` is finished, it may create a `FinishedProduct` (finished product) that is placed in an `Inventory` bucket. You can think of this as an "instance" of a `Supply`. Where `Supply` is the representation of the thing being produced, and a `FinishedProduct` being the finished product.
public struct FinishedProduct: Identifiable {
    public typealias ID = Int
    public let id: ID
    /// The type of `Supply` produced
    public let supply: Supply
    /// The `Inventory` the `FinishedProduct` should be placed in. The entire `FinishedProduct` is placed in `Inventory`.
    public let inventoryId: Inventory.ID
    /// Derived from the current value of `Supply.amount` e.g. box of 1000 screws, 4 wood beams, etc. a specific `WorkUnit` produces as the finished product once it reaches the end of the `Line`.
    /// Default: 1
    public let amount: Int
    
    // TODO: Traceability Controls - May be different depending on the product being produced. Therefore, it may be necessary to represent this as a structure that fits the respective context. Similar to a `Supply`. Also, it's not clear how certain values are applied, such as the lot and batch number. Those would need to be provided by an external system or algorithm. It could be applied as one of the `Operation`s in the last step.
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
    public enum WorkUnitName {
        /// This is a static name for the `WorkUnit`. Material names don't change e.g. "screw", "nail", etc.
        /// Database: Stored as `work_unit_name`. If it's `NULL`, it's an operator provided name.
        case material(name: String)
        /// This name will be provided by the `Operator` when making the `WorkUnit` e.g. a software development task feature name.
        case operatorProvided(name: String)
    }
    
    public typealias ID = Int
    public let id: ID
    public let lineId: Line.ID
    /// The order in which this `IntakeQueue` is displayed relative to other `IntakeQueue`s within the same `Line`.
    public let sortOrder: Int
    public let name: String
    public let theme: Theme?
    /// The ratio of `WorkUnit`s the Hopper.
    public let mixRatio: Double?
        
    // TODO: Other dependent `WorkUnit`s to create when a `WorkUnit` is created. This will most likely be handled by a `Supply`.
    // public let triggers: [WorkUnitTrigger]
    
    /// When a new `WorkUnit` is created, the user will either be asked a unique name or the `unique` name will be inherited by all `WorkUnit`s -- will not require user input.
    public let workUnitName: WorkUnitName

    /// This allows `Inventory` to link to an `IntakeQueue` that manufactures the respective `Supply` it needs.
    public let finishedProduct: Supply?
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
        /// A normal `Station` (the default)
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
    /// Notification triggers are used to inform others outside of the assignees. This may be a manager or someone interested in a specific `WorkUnit`.
    public let notificationTriggers: [StationNotificationTrigger]
    public let scriptTriggers: [StationScriptTrigger]
    /// Assigns respective `Operator`s to a `WorkUnit` when it enters into this `Station`. Assignees may be notified when they enter the `Station`. If human, their respective communication method(s) are respected (e-mail, Slack, etc.). If an `Agent`, they are activated with the `WorkUnit`.
    public let assigneeAction: StationAssigneeAction

    /// Required `Operation`s to perform in this `Station` before it can be moved to the next `Station`.
    /// The order in which `Operations`s are placed is defined by `Operation.sortOrder`.
    /// The station provides the context such as layout, tools, parts presentation, and cycle time target. e.g. the "standardized work documents".
    /// TBD: It's not necessary to list all `Operation`s in some contexts. It may be that only a standardized work doc is provided. The `Operation`s provide a way to:
    ///  - Take `Supply` from `Inventory` (manual or automated process) This will most likely be done automatically when the `WorkUnit` moves into the `Station`.
    ///  - Confirm that an `Operation` was complete
    ///  - Associate an agent/script to perform the work (with possible manual intervention)
    public let operations: [Operation]
    
    /// Acts as a light-weight `Inventory` buffer for a `Station`.
    /// The `InventoryBuffer` is like a rack that exists next to a `Station`. The `InventoryTray` is a "tray" of `Supply`s on the rack. e.g. A tray of screws. Or a location where (large) parts are placed.
    ///
    /// This also indicates how many `Supply`s must be on-hand to fulfill the work necessary to finish all `Operation`s in this `Station`. When a `WorkUnit` moves into a `Station`, the BOM is determined by the `Operation`s associated to the `Station`. From there, the `Supply`s will first be fulfilled by the buffer. If the buffer dips below the `minimum` threshold, it will initiate a request to the `Line` that is capable of providing the respective `Supply`. The `InventoryBuffer` will be fulfilled with the respective `Supply`s once completed.
    ///
    /// TBD: I'm not sure this is needed. For now, the `Station` will request directly from `Inventory`.
    public struct InventoryBuffer: Identifiable {
        public struct InventoryTray {
            public let inventoryId: Inventory.ID
            public let amount: Int
        }
        
        /// `OpenRequest`s for required `Supply`s needed to finish next N `WorkUnit`s.
        public struct OpenRequest: Identifiable {
            public typealias ID = Int
            public let id: ID
            public let inventoryBufferId: Station.InventoryBuffer.ID

            let createDate: Date
            /// The time the request was fulfilled. Once a request is fulfilled, it is no longer in the list of `InventoryBuffer.requests`.
            let fulfilledDate: Date
            /// The requested `WorkUnit`s. These are created at the time the `Request` is made. Therefore, it is possible to track the progress of each `WorkUnit` that was requested.
            let workUnit: [WorkUnit] // Database: 1-to-many
        }
        
        public typealias ID = Int
        public let id: ID
        public let stationId: Station.ID
        
        /// Represents the buffer amount to support N `WorkUnit`s.
        /// e.g. If `minimum` is `2`, and `maximum` is `4`, and there are enough `Supplies` (`current`) to finish `3` `WorkUnit`s, as soon as the `Supply`s are deducted from this buffer (`current` will now be `2`), it will trigger a request to all `Line`s that manufacture the respective `Supply`s. The amount requested will be (`maximum` + `requests.count` - `current` = `2`). If there are no open `Request`s to fulfill these supplies, this will ensure at least `2` more `WorkUnit` worth of `Supply`s will be provided asap.
        public let minimum: Int
        public let maximum: Int
        /// The current number of supplies to finish N `WorkUnit`s
        public let current: Int
        /// Open `Request`s for more `Supply`s.
        public let requests: [InventoryBuffer.OpenRequest]
        /// Supplies on-hand
        public let trays: [Station.InventoryBuffer.InventoryTray]
    }
    
    /// If no `InventoryBuffer` exists, the `Inventory` is fulfilled directly from the respective `Inventory`.
    public let inventoryBuffer: Station.InventoryBuffer?
    
    /// The amount of time, in seconds, it takes for a `WorkUnit` to make its way through the station. This is computed on an interval.
    public let cycleTime: TimeInterval
}

/// TODO: Needs to be paired with something to do.
/// I envision `Operation`s to always be done in the correct order. Even with software development, the `Operation`s will be visible but will need to be finished in the right order. Such that QA must be done before it assigned a version for release.
public enum OperationTrigger {
    /// Triggered when `WorkUnit` moves into `Operation`
    case onEnter
    /// Triggered when `WorkUnit` moves out of `Operation`
    case onExit
}


/// The status of the `Operation`. The cases are in the order in which they are processed.
public enum OperationStatus {
    case waiting
    /// Provides an optional message to indicate what action is being performed. Used only by the `Agent` to provide feedback to the user.
    /// The message could potentially be a note left by a human `Operator`.
    case inProgress(message: String?)
    /// Requires immediate help in order to process the `Operation`.
    /// The `message` could eventually be turned to an enumeration. But I don't know what enumerations would make sense. Therefore, freeform for now.
    case error(message: String?)
    case finished
}

/// An `Operation` is what is performed in a `Station`. Multiple `Operation`s may be performed on a `Station`.
///
/// TODO: An `Operation` could create a new type of `WorkUnit`. e.g. in software development, part of the grooming process could conditionally request "Design" work to be done.
/// TODO: `OperationLog`s
/// TODO: Waive an `Operation`?
public struct Operation: Identifiable {
    public enum SupplyRequest: Equatable {
        /// Physical `Inventory` to take `Supply` from
        case inventory(Inventory.ID, amount: Int)
        /// Used for data fields that require `Operator` input such as a "Software version", "Lot number", etc.
        case supply(Supply.ID)
        /// Create `WorkUnit`s. The `Operation.ID` is associated to the `WorkUnit` to track the progress of `WorkUnit`s in relation to this `Operation`. When the `WorkUnit`s are complete, this `Operation` is considered complete. It should be possible to do re-work in this `Operation`. Such that, if work is required to improve a design, after it was initially created (fix a defect, etc.) it can be added at this time.
        ///
        /// This will associate this parent `WorkUnit.ID` to the child. This should allow a `WorkUnit` to get more context on the work being completed.
        ///
        /// e.g. In regards to SD; When a `WorkUnit` moves into the "Design" `Station`, multiple "Design" `WorkUnit`s will be created from high-level requirements. The `Supply`s created by this `IntakeQueue` can be attached to `WorkUnit`s further along the process. There is also a possibility that another "Design" task is required later on to satisfy another SD task.
        case workUnits(IntakeQueue.ID)
    }
    
    public typealias ID = Int
    public let id: ID
    public let stationId: Station.ID
    /// The order in which the `Operation` is listed in the `Station` relative to other `Operation`s.
    public let sortOrder: Int
    public let name: String
    
    /// An `Agent` may manage `WorkUnit` that enters this `Operation`. Only an `OperatorType.agent` may be assigned to this. The `Agent` will update the `Operation.status` as it is processing the request.
    public let agent: Operator?

    /// If an `Operation` requires a `Supply`, it may request it from `Inventory`, or, if it's a data field, reference the `Supply` directly. `Supply` is associated to a `WorkUnit` when it enters a `Station`.
    public let supplyRequest: Operation.SupplyRequest?
    
    public let comments: [OperationComment]
}

/// Output is where `WorkUnit`s live after they have been finished. `WorkUnit`s in the `Output` are considered to be "Done." `Done` may be used interchangeably with `Output`. When showing `Output`, the most recent `WorkUnit`s are shown first.
///
/// By default `WorkUnit`s are removed from `Output` after 3 years, on January 1st.
public struct Output: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let lineId: Line.ID
    public let name: String // Default name is `Done`
    /// Possible reasons a `WorkUnit` may be considered `Done`.
    public let reasons: [OutputReason]
}

/// Represents the reason why a `WorkUnit` is considered `Done`. This could be:
/// - Deployed
/// - Duplicate
/// - Won't Do
/// - etc.
///
/// - Note: The system may provide defaults for common manufacturing contexts when first configuring the `Output`.
public struct OutputReason: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let outputId: Output.ID
    public let name: String
    /// Allows reasons to be changed over time without affecting `WorkUnit`s that still reference an old reason.
    public let hidden: Bool
}

// MARK: Triggers

/// Trigger a notification when `WorkUnit` is created or moves to a specific `Station`. Some `WorkUnit`s are created by outside teams and need to know the status of tasks in order to update their respective systems.
///
/// This is supposed to be a one-off. In most cases a `WorkUnit` notifies respective managers, employees, agents, etc. when the `WorkUnit` changes a state. This is only if, say, a technical support representative wants to track the progress of a product/bug/etc. so that they can provide up-to-date progress to a customer as to its completion time.
///
/// The messages sent to the `Operator`s will differ depending on the context. The system will message the formatting of the message. What will most likely happen is there will be a system Lambda that accepts the entire state of the `WorkUnit` including the `Line`, `IntakeQueue?`, `Station?`, `Operation?`, `Output?`, etc. and structure the message to make sense for the given context.
public struct WorkUnitNotificationTrigger: Identifiable {
    /// A trigger invokes an automatic system action. This includes notifying a `Operator` that a `WorkUnit` has been moved to a respective `Station`, etc.
    ///
    /// Triggers may trigger more than once. For example, if a `WorkUnit` triggers an event on a specific `Line` `Station`, every time the `WorkUnit` moves into that `Station`, it will be triggered.
    ///
    /// By default, no options are selected. However, one option must be selected in order for this trigger to be created (managed at the API level).
    public struct OnEnterEvent {
        /// Triggered when `WorkUnit` moves to a different `Line`'s `IntakeQueue` (uncommon)
        let intakeQueue: Bool
        /// Trigger when `WorkUnit` moves into any `Station`
        let station: Bool
        /// Trigger when `WorkUnit` moves int an `Operation`
        let operation: Bool
        /// Trigger when `WorkUnit` moves to `Output`
        let output: Bool
    }

    public typealias ID = Int
    public let id: ID
    public let workUnitId: WorkUnit.ID
    public let operators: [Operator]
    public let event: WorkUnitNotificationTrigger.OnEnterEvent
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

// MARK: Supplies

/// Required for a `WorkUnit` to be considered `Done`. Some supplies may be:
/// - Wireframe
/// - Hardware component or device that must be acquired to fulfill the request
/// - Software Deployment Version
/// - Question (composition of a question and answer text fields)
///
/// A `Supply` may also be referred to as a `Material`.
public struct Supply: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let name: String
    public let theme: Theme?
    
    /// Fields are required only if input is required by the `Operator`. Many (physical) `Supply`s, such as a screw, do not need an input. They simply need to be provided to the `Operator` at a given `Station`.
    public let fields: [SupplyField]?
    /// Indicates the amount of a `Supply` this represents that will be added to the `Inventory`. e.g. A box of 100 screws. This is probably only going to be used if a `Supply` is in an `Inventory`.
    public let amount: Int?
    
    /// - Note: I have removed both `required` and `waivable` as a `Supply` should only be added to `WorkUnit` types that require them.
}

/// A `SupplyField` provides a way to map a field name to a `Supply` type / value. Except for `SupplyFieldType.workUnit`, the `name` may be set.
///
/// NOTE: Values assigned to `WorkUnit`s will be deleted if the respective `SupplyField` is deleted.
public struct SupplyField: Identifiable {
    public typealias ID = Int
    public let id: ID
    /// The icon to display for the field. This will most likely be system-generated.
    public let icon: Icon?
    /// This is the "name" (label) of the field. e.g. Figma, Software Version, etc.
    public let name: String
    public let supplyFieldType: SupplyFieldType
}

/// Represents an option that can be selected in a single or multi-select list. It should be possible to search the names of these options in the UI. For example, some lists grow over time, such as a software development release version value. e.g. `1.94.0`, `1.95.0`, etc.
public struct SupplyFieldOption: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let supplyFieldId: SupplyField.ID
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
    
    case text(SupplyFieldType.TextType, String)
    case textArea(String)
    /// Photo, video, CSV, etc.
    case file(mimeType: MIMEType, Data)
    /// Select one option (radio) e.g. `Yes`, `No`, `Maybe`
    case radio([SupplyFieldOption])
    /// Select one or more options (checkbox) e.g. `1`, `A`, `1.94.0`, etc.
    case multiSelect([SupplyFieldOption])
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
    
    /// When a `WorkUnit` has a parent, it is considered a `SubWorkUnit`. e.g. sub tasks.
    public enum ParentWorkUnit {
        /// Created by an `Operation`
        case operationWorkUnit(OperationWorkUnit)
        /// Created from `WorkUnit`
        case parentWorkUnit(WorkUnit.ID)
    }
    
    /// `WorkUnit` was created as part of an `Operation`.
    public struct OperationWorkUnit {
        /// The `Operation` that created this `WorkUnit`, if any. This is used to determine the progress of an `Operation`.
        public let operationId: Operation.ID
        /// The parent this `WorkUnit` is associated to, if any.
        public let workUnitId: WorkUnit.ID
    }
    
    // TODO: Add estimated time on `WorkUnit`, such that you should know when the `WorkUnit` will be complete. A count-down of sorts.
    
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
    /// Name or description of the `WorkUnit`
    public let name: String
    
    /// This value must be removed, if moved out of `Output`
    public let outputReason: OutputReason?
    
    /// The `FinishedProduct` this `WorkUnit` produces when `Done`. This will automatically be added to the respective `Inventory` when `Done`. If a `FinishedProduct` exists, the `WorkUnit` may not be moved out of `Done`. It could go into a different line for QA/RMA/etc. Such that, if you create a product, and it is defective, the `WorkUnit` (the finished product) may move through a different line to repair, etc. It could be a special type of `IntakeQueue` that starts at a specific `Station`. But this is currently undefined.
    public let finishedProduct: FinishedProduct?
    
    public let parent: ParentWorkUnit

    /// All `WorkUnit`s (sub tasks) associated directly to this `WorkUnit`. Not by an `Operation`.
    /// Refer to: All records that refer to this `WorkUnit`, from `ParentWorkUnit.parentWorkUnit`, will be in this array.
    public let workUnits: [WorkUnit]?

    /// Indicates that the work unit is "stuck" and needs immediate attention in order to be moved through the queue. Otherwise, it runs the risk of being moved back in the line for rework.
    public let onHold: Bool
    
    /// When a `WorkUnit` moves to another `Line` (e.g. for subassembly) the `WorkUnit` needs to be move back to the `Station` from which it was sent. Therefore, when the `WorkUnit` reaches the end of the subassembly `Line`, it must move back to the original `Station`, and then move to the next `Station` in the respective `Line`.
    /// The reason there may be more than one is to support inner loops. They will always be processed in FILO order.
    /// A `WorkUnit` may _not_ move to an originator `Station`'s `Line`. That would cause an infinite loop.
    public let returnToStation: [Station.ID]
    
    /// TBD: Not sure if this is necessary. It could just be prioritized to the top of the `IntakeQueue`
    /// Immediately goes to the `Hopper`. Ideally, there is only one expedited `WorkUnit` at a time and it must be approved by a manager. If there is more than one, it is processed in FIFO order.
    public let expedite: WorkUnit.Expedite?
    
    public let comments: [WorkUnitComment]
}

public struct WorkUnitComment: Identifiable {
    public struct Emoji: Identifiable {
        public typealias ID = Int
        public let id: ID
        public let createDate: String
        public let operatorId: Operator.ID
        /// A single emoji character. These will be grouped in the UI. Hovering over the emoji will show the user who applied it.
        public let emoji: String
    }
    
    public typealias ID = Int
    public let id: ID
    public let workUnitId: WorkUnit.ID
    /// Allows for threaded comments
    public let parentWorkUnitCommentId: WorkUnitComment.ID?
    public let createDate: Date
    public let operatorId: Operator.ID
    public let text: String
    public let emojis: [WorkUnitComment.Emoji]
}

/// Functionally, and structurally, the same as `WorkUnitComment` except that these comments refer to `Operation`s instead of `WorkUnit`s. Please refer to any implementation details on `WorkUnitComment`.
public struct OperationComment: Identifiable {
    public struct Emoji: Identifiable {
        public typealias ID = Int
        public let id: ID
        public let createDate: String
        public let operatorId: Operator.ID
        public let emoji: String
    }
    
    public typealias ID = Int
    public let id: ID
    public let operationId: Operation.ID
    public let parentWorkUnitCommentId: WorkUnitComment.ID?
    public let createDate: Date
    public let operatorId: Operator.ID
    public let text: String
    public let emojis: [WorkUnitComment.Emoji]
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
    // TODO: I don't know if this is necessary. This is part of the `Operation`.
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

public struct SupplierContact: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let name: String
    public let phoneNumber: String?
    public let faxNumber: String?
    public let email: String?
}

/// External `Supplier` of a `Supply`.
public struct Supplier: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let name: String
    public let contacts: [SupplierContact]
}

/// Every supplier will have different lead times for a different `Supply` (material). Therefore, it's necessary to track the lead time per supplier, per material.
public struct SupplierSupply: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let supplier: Supplier
    public let supply: Supply
    /// Amount of time it takes from reorder until it can arrive at line that needs it.
    public let leadTime: Int
    /// The amount of material that can be ordered at a time, per shipment. This is used to determine if more than one `Supplier` needs to be used when reordering to replenish `Inventory`.
    public let maxOrderQuantity: Int?
}

/// `Inventory` of a `Supply`. This is expected to only be used for supplies that are interchangeable/general. A `Supply` may be unique for a given `WorkUnit`, like a UI/UX design for a feature, or an interchangeable supply such as a screw -- which can be used by any `Station` and/or `Operation`.
public struct Inventory: Identifiable {
    /// Companies, individuals, internal teams (suppliers) that provide the `Supply`. The `preference` is unique across the providers. Starts at 0.
    /// When ordering a `Supply`, it will select the first preferred `Provider` using `preference`. For MVP, this will simply list the order `Providers` in the respective order. It will be a manual process of determining who can actually provide the `Supply`.
    // TODO: When is it determined that a `Provider` can not provide the `Supply`?
    public enum Provider {
        /// External `Supplier` of `Supply`
        case supplier(SupplierSupply, preference: Int)
        /// Internal supplier of `Supply`.
        /// - Note: While `Supplier` has contacts, `IntakeQueues` do not. You can find the `IntakeQueue`'s contacts by referencing its `Line.managers`.
        case intakeQueue(IntakeQueue, preference: Int)
    }
    
    public typealias ID = Int
    public let id: ID
    
    /// The providers in this array are arranged in the order of preference.
    public let provider: [Inventory.Provider]
    
    public let supply: bosslib.Supply
    /// The amount of `Supply` we have in stock.
    /// Remember, `inStock` adds the number of `Supply.amount` once it is added to `Inventory`. e.g. If `100` "Screws" (`Supply`) are manufactured, and there are currently `52` screws `inStock`, this will become `152`. This level of granularity is required for certain `Operation`s.
    /// If an entire "Unit" of a `Supply` is required (e.g. "1 box 100 screws") you would need a new `Supply` called "100 Screws" in addition to your granular level `Supply` of "Screws". I'm not even sure this is necessary. But this accommodates all use cases where you either need to request a granular level of a `Supply` or a whole "Unit" of `Supply`s.
    public let inStock: Int
    // TODO: May be algorithmic. For now, it is a static value. But this could be a percentage or predicted amount based on future demand.
    public let reorderPoint: Int
    /// Computed when `Supply` is taken out of `Inventory` (`inStock` changes)
    public let estimatedReorderPoint: Date
}
