/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

/**
 Backend Process
 Measurement (Configuration) <- Alert <- Collector <- Sensor (script ran at interval or service pushing data to collector)

 Front-end process
 A `Measurement` has sensors that are configured
 */

import Foundation

public enum AlertingLevel: Equatable, Codable {
    case debug
    case info
    case warning
    case error
    case critical
}

extension AlertingLevel {
    public var name: String {
        switch self {
        case .debug:
            return "Debug"
        case .info:
            return "Info"
        case .warning:
            return "Warning"
        case .error:
            return "Error"
        case .critical:
            return "Critical"
        }
    }

    /// Returns respective `AlertingLevel` given a health value. Returns `AlertingLevel`s greater than `warning` or `nil` if healthy.
    public static func alertingLevel(for health: Int) -> AlertingLevel? {
        // This algorithm _must_ match `ays-server/db/types.py::get_health_level_type`
        if health >= 90 {
            return nil
        }
        else if health >= 66 {
            return .warning
        }
        else if health >= 33 {
            return .error
        }
        else {
            return .critical
        }
    }
}

/// Companies typically define their own "alerting types" such as P0, P1, ..., P4, etc. What this does allow a company to associate an `AlertingLevel` to a company-based alerting term. Such that P0 would be considered a "critical" `AlertingLevel`. By default, the `AlertType`s will map directly to the `AlertingLevel` names.
public struct AlertType: Equatable, Codable {
    public var name: String
    public let level: AlertingLevel
}

public struct ThresholdAction: Equatable, Codable {
    public let contact: Contact
    public let enabled: Bool
    public var inheritedFromParentNodePath: String?
}

public enum Interval: CaseIterable, Equatable, Codable {
    case seconds(Int)
    case minutes(Int)
    case hours(Int)

    public static var allCases: [Interval] {
        return [
            .seconds(0),
            .minutes(0),
            .hours(0)
        ]
    }

    public var toString: String {
        switch self {
        case .hours(let value):
            return "\(value)h"
        case .minutes(let value):
            return "\(value)m"
        case .seconds(let value):
            return "\(value)s"
        }
    }

    public static var allValues: [String] {
        return allCases.map { (interval) -> String in
            switch interval {
            case .seconds:
                return "seconds"
            case .minutes:
                return "minutes"
            case .hours:
                return "hours"
            }
        }
    }

    public static var `default`: Interval {
        return .minutes(1)
    }
}

public typealias ThresholdID = UInt

public struct Threshold: Equatable, Codable {
    public enum Range: Equatable, Codable {
        case min(Double)
        case max(Double)
        case range(min: Double, max: Double)
        case equal(Double)
        case notEqual(Double)

        public static let `default`: Threshold.Range = .max(1)
    }

    public var id: ThresholdID?
    public var alertType: AlertType
    public var range: Range
    /// The amount of time that a measurement value must be outside of the threshold range before `action`(s) will be triggered. The default is `nil`, in that, if the value falls outside of min/max range `action`(s) will be triggered immediately rather than waiting for the elapsed interval.
    public var elapsedInterval: Interval?
    /// Actions that will take place when the threshold has been breached
    public var actions: [ThresholdAction]?
    public var enabled: Bool
    /// Defines some parts of the Threshold as read-only. Currently only `actions`.
    public var readOnly: Bool
}

extension Threshold {
    public var toShortString: String {
        var interval: String = ""
        if let elapsedInterval = elapsedInterval {
            interval = " @ \(elapsedInterval.toString)"
        }
        switch range {
        case let .min(min):
            return "Min \(min)\(interval)"
        case let .max(max):
            return "Max \(max)\(interval)"
        case let .range(min, max):
            return "Range \(min) — \(max)\(interval)"
        case let .equal(equal):
            return "Equal \(equal)"
        case let .notEqual(equal):
            return "!Equal \(equal)"
        }
    }

    public var toString: String {
        "\(toShortString), \(actions?.count ?? 0) action(s)"
    }
}

public struct ScriptSensor: Equatable, Codable {
    /// For now, `Script` will be the only type of supported `Sensor`. Eventually a `Provider` and `RequestType` may be  necessary - if it's a `ServiceSensor`. The thing is, I have no idea if push services will ever be a thing. Therefore, to keep this simple, ays will support `ScriptSensor`s for now.
    // var provider: CollectorType
    public var interval: Interval
    public var parameterValues: [ScriptParameterValue]
    // If Script.returns.single this will be `nil`. Otherwise, it will be the index of the array returned.
    public var returnValueIndex: Int?
    public var script: Script
    public var readOnly: Bool
}

extension ScriptSensor {
    /// Allows an "agent sibling" sensor to be created from an agent sensor. Required when consuming from elder agent monitor.
    /// FIXME: Agent sensors may return an `unknown` sensor if no return value provided. What to do in this context? A sibling should probably not be allowed to be created from it.
    public static func makeSibling(from measurement: Measurement, sensor: AgentSensor) -> ScriptSensor {
        .init(
            interval: .default,
            parameterValues: [],
            script: .init(
                ownership: .sibling(measurementId: measurement.objectId, measurementName: measurement.name),
                parameters: [],
                returns: sensor.returns,
                language: .default,
                text: ""
            ),
            readOnly: false
        )
    }
}

public enum Sensor: Equatable, Codable {
    case agent(AgentSensor)
    case script(ScriptSensor)
    case unknown // New sensor. Requires user to select a sensor type.

    public var owner: ayslib.Script.Ownership {
        switch self {
        case let .agent(sensor):
            return sensor.ownership
        case let .script(sensor):
            return sensor.script.ownership
        case .unknown:
            // By default, an unknown sensor is owned by itself. The assumption is that this will be transformed into either an agent or script soon.
            return .owner
        }
    }

    public var isElder: Bool {
        let returns: ayslib.Script.ReturnValue
        switch self {
        case let .agent(sensor):
            returns = sensor.returns
        case let .script(sensor):
            returns = sensor.script.returns
        case .unknown:
            return false
        }
        switch returns {
        case .multiple:
            return true
        case .single, .virtualElder, .virtualNodes, .unknown:
            return false
        }
    }

    public var returns: Script.ReturnValue {
        switch self {
        case let .agent(sensor):
            return sensor.returns
        case let .script(sensor):
            return sensor.script.returns
        case .unknown:
            return .default
        }
    }

    public var readOnly: Bool {
        switch self {
        case let .agent(sensor):
            return sensor.readOnly
        case let .script(sensor):
            return sensor.readOnly
        case .unknown:
            return true
        }
    }
}

public struct AgentMessage: Equatable, Codable {
    public enum ParentNode: Equatable, Codable {
        case id(String)
        case path(String)
    }
    public struct Property: Equatable, Codable {
        public let name: String
        public let value: String
    }
    public struct Value: Equatable, Codable {
        public enum Threshold: Equatable, Codable {
            case unknown
            case above(Double)
            case below(Double)
            case equal(Double)
            case outside(min: Double, max: Double)
            case nequal(Double)
        }

        public let name: String
        public let value: Double
        public let threshold: AgentMessage.Value.Threshold?
    }
    public enum Relationship: Equatable, Codable {
        case parent(monitorName: String)
        case child(monitorName: String, relativeNodePath: String)
    }
    public struct Status: Equatable, Codable {
        public enum State: Equatable, Codable {
            case healthy
            case warning
            case error
            case critical
        }

        public let message: String
        public let state: AgentMessage.Status.State
    }
    public struct Heartbeat: Equatable, Codable {
        public let timeout: Int
        public let level: AlertingLevel
    }

    public let ts: Double
    public let parent: AgentMessage.ParentNode
    public let type: NodeType
    public let relationship: AgentMessage.Relationship
    public let orgSecret: Bool // Indicates that org secret was provided
    public let properties: [AgentMessage.Property]?
    public let template: String?
    public let value: AgentMessage.Value?
    public let values: [AgentMessage.Value]?
    public let status: AgentMessage.Status?
    public let heartbeat: AgentMessage.Heartbeat?
}

extension AgentMessage.Status.State {
    public var toString: String {
        switch self {
        case .critical:
            return "Critical"
        case .error:
            return "Error"
        case .healthy:
            return "Healthy"
        case .warning:
            return "Warning"
        }
    }
}

public struct AgentSensor: Equatable, Codable {
    public struct HeartbeatTimeout: Equatable, Codable {
        public var interval: Interval
        public var level: AlertingLevel
        public var enabled: Bool
        public var readOnly: Bool
    }

    public var ownership: Script.Ownership
    public var returns: Script.ReturnValue
    public var timeout: AgentSensor.HeartbeatTimeout?
    public var readOnly: Bool
    public var lastMessage: AgentMessage?
}

public typealias MeasurementID = String

/// Provides data for drawing measurement graphs.
public struct Measurement: ACLObject, Equatable, Codable {
    public var objectId: MeasurementID
    public var name: String
    /// The node this Measuremnt belongs to
    public let parentNode: ShallowNode

    /// NOTE: For more information on Measurement types (normal, template, and reference) refer to `ays-server/protocols/node.proto` in the `Measurement` message.
    /// I decided not to create an `enum` of the type for simplicity. This may change in the future.

    /// The node this measurement templates from
    public let templateNode: ShallowNode?
    /// The node this measurement references from. This usually indicates that this is a virtual node referencing another node's configuration.
    public let referenceNode: ShallowNode?

    /// The thresholds that will overlay the graph to indicate where the `values` reside within the thresholds.
    public var thresholds: [Threshold]
    /// The sensor that will generate the data for this `Measurement`
    public var sensor: Sensor
    /// Entities that can access this `Measurement`. ACL is derived from the respective `Node` that this `Measurement` belongs to. NOT the template, but the instance of this specific `Measurement`.
    public let acl: [ACL]
    public var enabled: Bool
    @IgnoreEquatable
    public var graph: MeasurementGraph? // TODO: Not sure if this is the right way
    public var runbookUrl: URL?

    public var isReadOnly: Bool {
        if referenceNode != nil {
            return true
        }
        switch sensor.owner {
        case .reference,
             .siblingReference:
            return true
        case .unknown,
             .owner,
             .sibling:
            return false
        }
    }

    public var isReference: Bool {
        referenceNode != nil
    }

    public var properties: [NodeProperty] {
        return parentNode.properties ?? []
    }

    public var isValueProducer: Bool {
        switch sensor.owner {
        case .owner:
            switch sensor.returns {
            case .multiple, .virtualElder, .virtualNodes:
                return true
            case .single, .unknown:
                return false
            }
        case .reference, .sibling, .siblingReference, .unknown:
            return false
        }
    }

    public var isAgent: Bool {
        switch sensor {
        case .agent:
            return true
        case .script, .unknown:
            return false
        }
    }
}

/// A simple relationship between an Measurement and its current respective AlertingLevel
public struct MeasurementAlertingLevel: Codable {
    public let id: String
    public let alertingLevel: AlertingLevel
    public let thresholds: [ThresholdAlertingLevel]
}

public struct ThresholdAlertingLevel: Codable {
    public let id: String
    public let alertingLevel: AlertingLevel
    public let isTriggered: Bool
}

public struct MeasurementGraph: Codable {
    public struct Sample: Codable {
        public let value: Double?
        public let ts: TimeInterval
        public let error: String?
        public let message: String?
    }
    public struct Threshold: Codable {
        public let alertType: AlertType
        public let range: ayslib.Threshold.Range
    }

    public let measurementId: String
    // Derived from `Measurement.name`
    public let name: String
    // Values are distributed (not evenly) along the X axis. Where Y is the value plotted.
    public var samples: [Sample]
    // Although `increments` may not be precise, the `Interval` is provided as a hint as to how future values will be plotted.
    public let interval: Interval
    public var thresholds: [MeasurementGraph.Threshold]

    public let node: ShallowNode
    public let templateNode: ShallowNode?
    public let runbookUrl: URL?

    public let enabled: Bool
}

public struct MeasurementGraphUpdate {
    public let measurementId: String
    public let samples: [MeasurementGraph.Sample]
}

extension MeasurementGraph {
    public static func makeEmpty() -> MeasurementGraph {
        return .init(
            measurementId: "",
            name: "Title",
            samples: [],
            interval: .seconds(15),
            thresholds: [],
            node: .init(id: 0, path: "", type: .group),
            templateNode: nil,
            runbookUrl: nil,
            enabled: true
        )
    }

    public var toShallowMeasurement: ShallowMeasurement {
        return .init(node: node, templateNode: templateNode, objectId: measurementId, name: name)
    }
}

extension Measurement {
    public static func makeEmpty(for node: ShallowNode) -> Measurement {
        return .init(
            objectId: "",
            name: "",
            parentNode: .init(
                id: node.id,
                path: node.path,
                type: node.type,
                properties: node.properties
            ),
            templateNode: nil,
            referenceNode: nil,
            thresholds: [],
            sensor: .unknown,
            acl: [],
            enabled: true,
            graph: nil
        )
    }

    public var toShallowMeasurement: ShallowMeasurement {
        return .init(
            node: parentNode,
            templateNode: templateNode,
            objectId: objectId,
            name: name
        )
    }
}

extension Threshold {
    public static func makeEmpty() -> Threshold {
        return .init(
            id: nil,
            alertType: .init(name: "", level: .debug),
            range: .max(10),
            elapsedInterval: nil,
            actions: nil,
            enabled: true, // Do not change this. It is required when creating new Thresholds.
            readOnly: false
        )
    }
}

public struct ShallowMeasurement {
    public let node: ShallowNode
    public let templateNode: ShallowNode?
    public let objectId: String
    public let name: String
}
