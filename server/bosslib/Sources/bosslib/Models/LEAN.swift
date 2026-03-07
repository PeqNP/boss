/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

/**
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
 ────────────────────────────────────────────────────────────────
 Table Conventions - Creating tables, columns, and index rules
 
 All `id` columns must be serial. Use your best judgement when determining the size of the integer to use for ID columns (e.g. `INT`, `BIGINT`). If you're not sure, use `INT`. For example, records used for configuration can be `INT`. Records that are guaranteed to be in the hundreds of thousands (logs) can be a `BIGINT`, or equivalent.

 All IDs that reference another table/model, must be indexed.
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
    case Step
    case Supply
    case OutputReason
    case Shift
    case Capacity
    case WorkUnitTemplate
}

struct ChangeLog: Identifiable {
    let id: Int
    /// The respective business model that changed
    let businessModelId: BusinessModel
    /// The time the change was made (whatever the current time is)
    let date: Date
    /// The user who made the change
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
/// `Shift`s associated to `Line`s start on Sunday at 12a. A `Shift` may overlap days and even into the next week's shifts.
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
/// This provides the clearest signal for cylce time. The `Operator` does not need to inform the system when they are signed in or out. It is automatically determined by the shift they are associated to.
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

/// Indicatates when an `Operator` will be absent from the `Line`. It could be related to sick leave, PTO, doctor's appointment, etc.
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

/// A `Line` contains `Step`s (activities) that must be performed in order for a `WorkUnit` to be considered considered Done. A `WorkUni` starts in the `IntakeQueue`, then the `Line`'s `Step`s, then to Done.
public struct Line: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let themeId: Theme?
    public let name: String
    public let intakeQueue: IntakeQueue
    public let hopper: Hopper
    /// The order in which the `Step`s are added to this array is determined by using `Step.sortOrder`
    public let steps: [Step]
    public let output: Output
    public let capacity: [Capacity]
    public let shifts: [Shift]
    /// Line managers are informed when "Hold"s are placed on work units.
    public let managers: [User]
}

/// `Capacity` provides a way to apply estimation metrics across all of the value streams. It provides the averages estimated time an `Operator` can complete a `WorkUnit` in a single day for the given `Line`.
///
/// `Capacity` is associated to a `Line`. Increasing `Capacity` increases the amount of `WorkUnit`s that can be finished in a `Line` within a day. `Capacity` can also be thought of as a "Thread." Threads indicate work that can be done in parallel within the same `Line`.
public struct Capacity: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let lineId: Line.ID
    public let `operator`: Operator
    /// The date the `Capacity.value` was last computed by the system
    public let computedDate: Date
    /// A computed value, saved daily, that tracks the amount of `WorkUnit`s the `Operator` is finishing on average, per day compared to expected standard time of respective `WorkUnit`s.
    ///
    /// Standard time is an estimate on how long a `WorkUnit` should take, in minutes. The performance efficiency is computed by adding the total number of `WorkUnit`s completed in a day, divided by the amount of time in a `Shift` (operating time). Standard time of `1` (480 minutes) for `WorkUnit`, finished `1.5` (in 8 hour shift time) = (1.5/1) 1.5 - indicates operator is able to finish unit faster than standard time 0.5x more.
    ///
    /// A value of `1` means the `Operator` is matching the expected output. Greater than `1` and they're more productive. Less than `1` means inefficiences need to be identified (ensure they are performing the activity correctly, skill up, etc.)
    public let performanceEfficiency: Double
}

// MARK: Line States

/// Represents the location within a `Line` where a `WorkUnit` can be found.
///
/// Each case should be its own database table. It's represented this way for each of use.
public enum LineStateType: Int {
    case intakeQueue = 0
    /// hopper - `WorkUnit` is seen in a `Hopper`, but not associated to it
    case step
    case output
}

public struct LineState: Identifiable {
    /// For speed, the `id` can be used to order the states in chronological order.
    public typealias ID = Int
    public let id: ID
    let type: LineStateType
    let workUnitId: WorkUnit.ID
    let modelId: Int /// Represents either a IntakeQueue.ID, Step.ID, or Output.ID
    let enterDate: Date
    let exitDate: Date?
}

/// The `IntakeQueue` is where `WorkUnit`s live before they are worked on. It is like a "Backlog." If multiple queues are linked to a single `Line`, a `Line` can define a mix ratio that indicates the proportion of `WorkUnit`s that must be worked from this `Line` in relation to other `Line`s.
///
/// An `IntakeQueue` must define its `WorkUnit`. This is done by associating an `IntakeQueue` with a `WorkUnitTemplate`. The template is how the `IntakeQueue` defines the necessary supplies, triggers, etc. required for the `WorkUnit` to be considered `Done`.
///
/// Technically, the `WorkUnitTemplate` and `IntakeQueue` do not need to be separate records. I did this to make the two models more lean. That being said, there will only ever be a one to one relationship between a `WorkUnitTemplate` and an `IntakeQueue`.
public struct IntakeQueue: Identifiable {
    public typealias ID = Int
    public let id: Int
    public let lineId: Line.ID
    public let name: String
    public let theme: Theme?
    public let workUnitTemplate: WorkUnitTemplate.ID
    /// The ratio of `WorkUnit`s the Hopper
    public let mixRatio: Double?
}

/// Tracks which set of `WorkUnit`s will be worked on next.
public struct Hopper: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let lineId: Line.ID
    /// TBD: Needs to contain the next `WorkUnit` to work on and any other supporting state values to ensure it is pulling the correct `WorkUnit` based on the `IntakeQueue`s associated to a `Line`.
}

/// A step defines an activity required for a `WorkUnit` to go through before it can move to the next `Step` (or `Output`). `Step`s are processed in the order they appear in the `Line`.
///
/// `Activity` and `Step` refer to the same thing.
///
/// Before moving a `WorkUnit` to another `Step`, at least one assignee must be associated to the `WorkUnit` before moving. Otherwise, there's no way to track who performed the work required by the `Step`.
///
/// - Note: If automatically assigning an `Agent` `Operator` to the `WorkUnit`, this system will make a call to the respective agent automatically (no triggers necessary). As soon as the `Step`'s defined work is finished, it will automatically move to the next `Step`.
public struct Step: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let lineId: Line.ID
    /// The order in which the step should appear in the line.
    public let sortOrder: Int
    public let name: String
    public let theme: Theme?
    /// The `WorkUnit`s in this step
    public let workUnits: [WorkUnit]
    /// Supplies required by this `Step` before a `WorkUnit` may move into this `Step`. In the UI, an `Operator` will be presented with all of the necessary supplies. A `Supply` may be added at this time. Such that, an alert is shown, the `Supply`(ies) are listed in a table, and the user adds the necessary `Supply`(ies), and values, before moving into the `Step`.
    public let requiredSupplies: [RequiredStepSupply]
    public let notificationTriggers: [StepNotificationTrigger]
    public let supplyTriggers: [StepSupplyTrigger]
    public let scriptTriggers: [StepScriptTrigger]
    /// How the assignees of a `WorkUnit` are handled when a `WorkUnit` enters into this `Step`
    public let assigneeAction: [StepAssigneeAction]
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

/// A trigger invokes an automatic system action. This includes notifying a `Operator` that a `WorkUnit` has been moved to a respective `Step`, running a Python script, creating a Work Unit, etc.
///
/// The trigger types are not a database model. They only need to be assigned an ID. When a trigger is associated to a `Step`, it will reference the hard-coded ID.
///
/// Triggers may trigger more than once. For example, if a `WorkUnit` triggers an event on a specific `Line` `Step`, every time the `WorkUnit` moves into that `Step`, it will be triggered.

public enum WorkUnitTriggerEvent {
    /// Trigger on `WorkUnit` creation
    case onCreate
    /// Trigger when `WorkUnit` moves into any `Step`
    case onStep
    /// Triggered on specific `Line` `Step`
    case onMove(Line.ID, Step.ID)
}

/// Trigger a notification when `WorkUnit` is created or moves to a specific `Step`. Some `WorkUnit`s are created by outside teams and need to know the status of tasks in order to update their respective systems.
public struct WorkUnitNotificationTrigger: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let workUnitId: WorkUnit.ID
    public let operators: [Operator]
    public let event: WorkUnitTriggerEvent
    /// The message sent to the `Operator`(s). A message has access to the following values:
    /// - `Line.name`
    /// - `Step.name`
    /// - `WorkUnit.name`
    /// These values can be interpolated into the message. e.g. `Task {WorkUnit.name} has moved to line {Line.name} step {Step.name}.`
    public let message: String
}

public enum StepTriggerEvent {
    case onEnter
    case onExit
}

/// Trigger notification when `Step` has a `WorkUnit` moved into, or out of, itself.
public struct StepNotificationTrigger: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let stepId: Step.ID
    public let operators: [Operator]
    public let event: StepTriggerEvent
    /// Message sent to `Operator`(s). Uses the same rules as `WorkUnitNotificationTrigger.message`,
    public let message: String
}

/// Automatically add a `Supply` to a `WorkUnit` that moves into it.
///
/// If the respective `Supply` already exists on the `WorkUnit` it will _not_ be added. This condition may occur if the `WorkUnit` has moved in/out of the `Step` more than once, added manually, or work of the `WorkUnitTemplate` config.
///
/// This always trigger `StepTriggerEvent.onEnter`
public struct StepSupplyTrigger: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let stepId: Step.ID
    public let supplies: [Supply]
}

/// Execute a Python script when `WorkUnit` moves in/out of a step.
public struct StepScriptTrigger: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let stepId: Step.ID
    public let event: StepTriggerEvent
    /// Python script to execute when triggered
    public let script: String
}

// MARK: Step Dependencies

/// Associates `Step` to a required `Supply`.
public struct RequiredStepSupply: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let stepId: Step.ID
    public let supplyId: Supply.ID
}

/// Action to take when a `WorkUnit` enters into a `Step`.
public enum StepAssigneeAction {
    /// Removes all assignees from the `WorkUnit`
    case remove
    /// Retain all existing assignees
    case retain
    /// Replace assignees with respective `Operator`s
    case replace([Operator])
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

/// List of supply field types.
/// TODO: Create a table for each of these types. Consist if ID and the respective value type it saves. This may include indexes that reference other tables (such as the `supply` case). When saving values, there may also need to be a table that contains the saved value and also references the respective table(s) it references.
public enum SupplyFieldType {
    case text
    case textArea
    case number // Allows fractional values
    case url
    case photo
    case file
    /// Select one option (radio) e.g. `Yes`, `No`, `Maybe`
    case radio([SupplyFieldOption])
    /// Select one or more options (checkbox) e.g. `1`, `A`, `1.94.0`, etc.
    case multiSelect([SupplyFieldOption])
    /// Indicates a `Supply` that is created by a `WorkUnit`. When first creating the `Supply`, the user can select from a list of all `WorkUnitTemplate`s that produce a `WorkUnit` that create the necessary `Supply`. When the `Supply` is created, it will automatically create the respective `WorkUnit` and associate itself to the `WorkUnit` to track the progress.
    ///
    /// When adding to a `WorkUnit`, the UI will automatically open the `WorkUnitTemplate`'s form and ask them to create the task. Eventually, this may be automated... if all of the required inputs from the template can be provided. In the context of supply triggers, the wizard will show the `Operator` every `WorkUnitTemplate`, until all work has been created.
    case supply(WorkUnitTemplate.ID)
    
    /// Future consideration: Phone number, weight, price, etc. Anything that needs rule(s) around the input.
}

// MARK: Work Unit

/// Represents the configuration of a `WorkUnit`. When a new `WorkUnit` is created, it must be derived from a template. The template informs which supplies, triggers, etc. are associated to the `WorkUnit` upon creation. A `WorkUnitTemplate` defines the "type" of `WorkUnit`. But really, it's just a label. There can be "Initiative", "Work Unit", "Printer Request", etc. `WorkUnit` types. For example, a "Feature" `WorkUnit` may require supplies such as a wireframe, behavior ID (for UI testing), motivation, requirements, documentation, etc.
public struct WorkUnitTemplate: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let intakeQueueId: IntakeQueue.ID
    public let name: String
    public let theme: Theme?
    /// The number of minutes a typical `WorkUnit`, of this type, should take to fully complete through the `Line`. From the first `Step` to `Output`. The UI should provide options for minutes or hours. No days, as that would mean 24h+. Use hours instead. This is an exact measurement of time to complete excluding breaks, etc. Excludes down time, etc. For example, if you were to use a stop watch from the time the `WorkUnit` was worked on, until the time nothing was done to the `WorkUnit` (no automated or manual task), and add up all of those time slices, that would equal the standard time.
    ///
    /// This is also considered the "standard cycle time" or "target cycle time."
    ///
    /// This also informs the Takt time, which is the number of `WorkUnit`s that need to be processed, over time, to match customer demand. This is a fancy way of saying, we have to finish N `WorkUnit`s to satisfy customer's demand by X time. This takes the total time available divided by the number of required `WorkUnit`s to produce. Required pace to meet demand.
    public let standardTimeInMinutes: Double
    public let notificationTriggers: [WorkUnitNotificationTrigger]
    // TODO: Other dependent `WorkUnit`s to create when a `WorkUnit` is created. This will most likely be handled by a `Supply`.
    // public let triggers: [WorkUnitTrigger]
    public let supplies: [Supply]
    /// The supply the `WorkUnit` will create as an artifact when it is `Done`.
    public let supply: Supply?
}

public struct WorkUnitTemplateSupply: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let workUnitTemplate: WorkUnitTemplate
    public let supply: Supply
    /// Indicates that the `Supply` is required to be fulfilled. The UI will show visual indicator that allows the user to deselect a non-required supply before creating the `WorkUnit`.
    public let required: Bool
    /// Indicates that the `Supply` may be waived later on in the process.
    public let waivable: Bool
}

/// Represents the value moving through the stream. It could be a product, feature, task, bug fix, etc.
///
/// May also be referred to as `Value`, `Product` or `Task`.
///
/// The primary responsibility of a `WorkUnit` _may_ be to provide a `Supply`. e.g. There may be a "Design" `WorkUnit` that produces a URL to a wireframe used for software development.
///
/// When a `WorkUnit` moves from one `Step` to the next, the assignees will stay with the `WorkUnit`, but can be removed (or replaced) later.
public struct WorkUnit: Identifiable {
    public typealias ID = Int
    public let id: ID
    /// The template this `WorkUnit` was derived from. This also informs the user what type of `Task` it is.
    public let workUnitTemplate: WorkUnitTemplate
    /// The `Operator` who created the `WorkUnit`
    public let creator: Operator
    /// The `Operator` who reported/scheduled the `WorkUnit`. It does not necessarily need to be the user who created the `WorkUnit`
    public let reporter: Operator
    /// Current list of `Operators` working on the `WorkUnit`
    public let assignees: [Operator]
    /// Current state where `WorkUnit` is located within `Line`. This record is used to generate a list of `LineState`s that track the movement of a `WorkUnit` over time.
    public let lineState: LineState
    public let supplies: [WorkUnitSupply]
    public let notificationTriggers: [WorkUnitNotificationTrigger]
    
    /// This value must be removed, if moved out of `Output`
    public let outputReason: OutputReason?
    /// The `Supply` this `WorkUnit` produces as an artifact of being `Done`
    public let supply: Supply?
    
    /// The parent this `WorkUnit` is associated to, if any
    public let parentWorkUnitId: WorkUnit.ID?
    /// Child `WorkUnit`s. Used in the context of "Epics" or "sub tasks".
    public let workUnits: [WorkUnit]
    
    /// Indicates that the work unit is "stuck" and needs immediate attention in order to be moved through the queue. Otherwise, it runs the risk of being moved back in the line for rework.
    public let onHold: Bool
}

/// Represents the relationship between a `WorkUnit`, `Step`, and the `Operator`(s) performing the activity required by the `Step`. This is a historical record. Such that, you can see how a `WorkUnit` moved through a `Line` by looking at all of the `Step`s performed on the `WorkUnit`. This provides a chain of activities performed on the `Step`, in the order they were performed.
public struct WorkUnitStep: Identifiable {
    public typealias ID = Int
    /// The `id` is used to order the historical events in chronological order. The `createDate` can also be used, but sorting by `id` should be faster.
    public let id: ID
    public let workUnitId: WorkUnit.ID
    public let stepId: Step.ID
    /// The time the `WorkUnit` moved into the `Step`
    public let enterDate: Date
    /// The time the `WorkUnit` moved out of the `Step`
    public let exitDate: Date
    /// More than one assignee can be added to a `WorkUnit`, for a given `Step`. This is necessary for pair programming or the managing of a `WorkUnit` by a 3rd party. For example, Tom and I should be the assignees for a given `Step` in the `WorkUnit`. It is assumed that the assignee is the one who worked on the `WorkUnit` from start to finish for the given `Step`.
    public let assignees: [Operator]
}

/// Represents a relationship between a `WorkUnit` and a `Supply`. It further allows constraints to be placed on the `WorkUnit` the `Supply` is associated to. Such that, if a `Supply` is not provided, but is required by the next `Step`, the system will inform the `Operator` that a `Supply` is required before moving to the next `Step`.
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
    
    // TODO: The total time it took from the first `Step` it was placed in, to the `Output`. When showing the _actual_ time, it will factor in the "working hours" to provide a more accurate estimate of actual time worked on the ticket. Not sure if this is computed or not. Or if this is even necessary.
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
    /// The `WorkUnit` providing the respective `Supply`
    case supply(WorkUnit.ID)
}

/// The value provided by the `Operator` to fulfill the `Supply`
public struct WorkUnitSupplyFieldValue: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let workUnitSupplyId: WorkUnitSupply.ID
    public let supplyFieldId: SupplyField.ID
    public let value: SupplyFieldValue
}
