/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

/// Payload provided by an agent service to indicate a heartbeat of an external service or hardware.
public struct AgentPayload: Codable {
    public enum AlertLevel: String, Codable {
        case critical
        case error
        case warning
    }

    public enum ParentProperty: String, Codable {
        case id
        case path
    }

    public struct Parent: Codable {
        let property: ParentProperty
        // The value of the parent's node ID or node path
        let value: String
    }

    public struct Property: Codable {
        let name: String
        let value: String
    }

    public enum AgentType: String, Codable {
        case machine
        case service
        case vendor
    }

    public enum RelationshipType: String, Codable {
        case child
        case parent
    }

    public struct Relationship: Codable {
        // The type of relationship.
        let type: RelationshipType
        // The name of monitor this agent will be associated to.
        let monitor_name: String
        // Used only when relationship is `child`. This will create a child node under the parent node path provided in main payload. This is a relative path respective to the parent node's path.
        let path: String?
    }

    public struct Heartbeat: Codable {
        // The timeout, in seconds. If the agent fails to report within the timeout the agent will be considered in error.
        let timeout: Int
        // The alerting level this monitor should be considered in if timeout breached.
        let level: AlertLevel
    }

    public struct OutsideThreshold: Codable {
        let min: Float
        let max: Float
    }

    public struct Threshold: Codable {
        // Trigger an alert if value is below threshold.
        public let below: Float?
        // Trigger an alert if value is above threshold.
        public let above: Float?
        // Trigger an alert if value is outside of threshold.
        public let outside: OutsideThreshold?
        // Trigger an alert if value is equal to threshold.
        public let equal: Float?
        // Trigger an alert if value is NOT equal to threshold.
        public let nequal: Float?
        // The alerting level.
        public let level: AlertLevel
    }

    public struct Value: Codable {
        // Name of return value. If templating, this must match the respective monitor's name.
        public let name: String
        // Value of return value.
        public let value: Float
        // Trigger an alert if value does not fall within threshold range.
        public let threshold: Threshold
        // Like `threshold`, this allows you to pass in a formatted threshold. A more succinct way to pass threshold configuration. Please refer to the [ays-agent docs](https://github.com/PeqNP/ays-agent/blob/main/docs/api.md) for available formatting options.
        public let threshold_format: String?
    }

    public enum HealthState: String, Codable {
        case healthy
        case warning
        case error
        case critical
    }

    public struct Status: Codable {
        // The status message. This can be used for both healthy and unhealthy states.
        public let message: String
        // The state of the agent. The `healthy` state is designed to make the node healthy again after an unhealthy state is sent.
        public let healthState: HealthState
    }

    // Perform pre-checks and raise error if payload is invalid.
    // This will slow down ingestion. Therefore, use this only for debugging.
    public let check: Bool

    // Required
    // The parent node this device is associated to
    public let parent: Parent

    // Required
    // The type of agent. The default is `machine`.
    public let type: AgentType?

    // Required
    // The org auth secret. This ensures nodes are associated to the correct org.
    public let org_secret: String

    // Required
    // How the agent should relate to the graph. Can relate to a parent or create a new node.
    public let relationship: Relationship

    // Optional
    // Self-reported properties. These values are saved as node properties.
    public let properties: [Property]?

    // Optional
    // The path to a template node this agent references.
    public let template: String?

    // Optional
    // The heartbeat configuration. This is used to determine if the agent is in error if it hasn't been heard from within the configured timeout.
    public let heartbeat: Heartbeat?

    // MARK: Values & Statuses

    // Optional
    // Reports a single value.
    public let value: Value?

    // Optional
    // Reports multiple values. This will be considered an elder monitor.
    public let values: [Value]?

    // Optional
    // Reports status of the agent. This provides detailed information about the current state of the agent. It is designed to be used by agents that do not report a `value`, or `values`, but instead report an agent's health via a webhook such as NewRelic, Datadog, etc.
    public let status: Status?

    // Optional
    // Gives full control to agent to manage node and monitors. Templates will be unlinked and monitors will deleted if the configuration changes. This is true, by default. This is ignored when the relationship type is parent.
    public let managed: Bool?
}
