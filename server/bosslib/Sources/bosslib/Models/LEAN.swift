//
//  LEAN.swift
//  bosslib
//
//  Created by Eric Chamberlain on 2/25/26.
//

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

/// The BusinessModel and ChangeLog are used to keep track of model changes.
///
/// The name of the model in BusinessModel directly maps to the name of the business model's `struct` name. If a model is listed in `BusinessModel`, then add the generated code to track the changes made to the model.
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
}

struct ChangeLog: Identifiable {
    let id: Int
    /// The respective business model that changed
    let businessModelId: BusinessModel
    /// The time the change was made (whatever the current time is)
    let date: Date
    /// The user who made the change
    let operatorId: User.ID
    /// Contains all of the property values that changed. This is saved as a JSON structure in the db. e.g. if the `Line.name` property was changed, the metadata would be `{"name": ["Name before", "Name after"]}`, where the first column in the array would be the value before it was changed, and the next value would be the new value.
    let metadata: [String: String]
}

// MARK: - Business Models

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
public struct Operator: Identifiable {
    public typealias ID = Int
    public let id: ID
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

// MARK: Line

/// A `Line` contains `Step`s (activities) that must be performed in order for a `WorkUnit` to be considered considered Done. A `WorkUni` starts in the `IntakeQueue`, then the `Line`'s `Step`s, then to Done.
public struct Line: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let themeId: Theme?
    public let name: String
    public let intakeQueue: IntakeQueue
    public let hopper: Hopper
    /// The order of the steps here matter.
    public let steps: [Step]
    public let output: Output
}

// MARK: Line States

/// Represents the location within a `Line` where a `WorkUnit` can be found.
public enum LineState {
    case intakeQueue(IntakeQueue.ID)
    /// hopper - `WorkUnit` is seen in a `Hopper`, but not associated to it
    case step(Step.ID)
    case output(Output.ID)
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
    /// Supplies required by this `Step` before a `WorkUnit` may move into this `Step`. From the UI, it should be possible to add the necessary supplies to the `WorkUnit` automatically. Such that, an alert is shown, the supplies are listed in a form, and the user adds the necessary supplies before moving. A user may also add the supplies, but keep it in the current `Step`.
    public let requiredSupplies: [Supply]
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
    /// The number of days a typical work unit of this type should take to complete.
    public let estimatedSizeInDays: Double
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
    /// Reference to where the `WorkUnit` can be found in the `Line`
    public let lineState: LineState
    public let supplies: [WorkUnitSupply]
    public let notificationTriggers: [WorkUnitNotificationTrigger]
    /// This value must be removed, if moved out of `Output`
    public let outputReason: OutputReason?
    /// Computed by the system on some interval. TBD: This value may not live on the `WorkUnit`.
    public let estimatedCompletionTime: Date?
    public let supply: Supply?
    
    /// The parent this `WorkUnit` is associated to, if any
    public let parentWorkUnitId: WorkUnit.ID?
    /// Child `WorkUnit`s. Used in the context of "Epics" or "sub tasks".
    public let workUnits: [WorkUnit]
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

public struct WorkUnitNotificationTrigger: Identifiable {
    public typealias ID = Int
    public let id: ID
}

// TODO: Can this be represented by the `ChangeLog`?
public struct WorkUnitStep: Identifiable {
    public typealias ID = Int
    public let id: ID
    public let name: String
    public let workUnitId: WorkUnit.ID
}
