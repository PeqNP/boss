/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

/**
 Represents a node [a system or grouping of systems] in an organization.
 */

import Foundation

public typealias NodeID = UInt
public typealias NodePath = String

public extension NodePath {
    var orgPath: String? {
        let parts = split(separator: ".")
        if parts.count < 2 {
            // TODO: https://trello.com/c/EgUMYWl4/11-simpleanalytics-swift-package
            // boss.log.w("Failed to derive Organization from NodePath (\(self))")
            return nil
        }
        let orgParts = parts[0...1]
        return orgParts.joined(separator: ".")
    }
}

public enum OSType: CaseIterable, Equatable, Codable {
    case unknown
    case ios
    case android
    case macos
    case windows
    case linux // flavor?
}

public enum SystemResourceType {
    // Unsupported resource type for this client version
    case unknown
    // Is associated to a `Script` or service that provides the sensor it's information
    case sensor
    // A special `Node` that is used only for creating measurements that are used as templates. It will typically be styled differently (dotted line) and can be hidden from view.
    case template
}

// TODO: Everything should be using this `enum` when relating to relationship types
public enum RelationshipType: Codable {
    case dependent
    case child
    case dependency
}

/**
 Represents a type of node within the organization

 These types are typically a grouping of one or more other nodes:
   - unknown (if `children` are provided)
   - client - has number of active clients
   - service - has resources
   - resource - has cluster of machines that provide resource
   - group - generic grouping

 All other types are meant to be "single", meaning they have no children. Also, not all of these types _have_ to have children. Especially when a system is first setup, there may be no children for a given node type. Instead, they are used to provide clarity as to the _type_, so that at a glance, it is easy to identify the node type.
 */
public enum NodeType: CaseIterable, Codable {
    /// Catch-all case when a new type is added, but not supported by the client.
    case unknown
    /// Represents a single client platform app. This could be an app made for iOS, Android, Windows Desktop, macOS, etc.
    case client(OSType)
    /// Represents a group of `resource`s. Typically this grouping identifies the team responsible for managing the respective resources. e.g. if there is a "Customer" team responsible for managing user state, then the grouping may be:
    /// service path: `//com.example.customer`, responsible for resources -> .login, .logout, .create, .delete, .deactivate, etc.
    case service
    /// Represents a service resource (endpoint) of a given system. This usually represents a group of `machine`s (servers) that provide the resource.
    case resource
    /// Represents a group of any type of `Node` type. Typically it is used to group together "like" systems/platforms/etc. It does _not_ represent a cluster of servers that provide a specific service. That is managed by the `service` type. It is a _generic_ grouping. e.g. a grouping might be //com.example.mobile where `mobile` is the grouping and the `mobile` group may have many `client` (iOS, Android, etc.) nodes.
    case group
    /// Represents any physical device within the organization. This could be a POS, router, server, desktop, etc. Their health is typically monitored by a custom program.
    case machine
    /// Represents an application that is installed on a machine
    case application
    /// Similar to a `monitor`, its specific in that it represents a proxy between one or more nodes -- usually between clients and servers. e.g. an iPhone app a service that logs a user in.
    case proxy
    /// Monitors (external) systems such as S3 buckets, 3rd party proxies, gateways, etc. These are necessary for systems which must still be monitored but are not managed within a company's network. It's not _limited_ to these reasons, it's simply the purpose it was created for. Typically systems of this type you monitor with a custom program to gather information about the system (such as `ping`ing the resource).
    case monitor
    /// Represents a 3rd party node. This is used to identify vendors.
    case vendor
    /// Represents a Node that can be used as a Template
    case template
    /// Represents a read-only Node that is based off a Template Node
    case virtual(parentNodeId: NodeID, parentNodePath: NodePath)

    var virtualParentNodePath: String? {
        if case let .virtual(_, path) = self {
            return path
        }
        return nil
    }

    // MARK: CaseIterable

    public typealias AllCases = [NodeType]

    public static var allCases: [NodeType] {
        return [
            .application,
            .client(.unknown),
            .vendor,
            .group,
            .machine,
            .monitor,
            .proxy,
            .resource,
            .service,
            .template,
            // .virtual, Not allowed
            .unknown
        ]
    }

    public var relationshipTypes: [RelationshipType]? {
        let parent: [RelationshipType] = [.child]
        let child: [RelationshipType] = [.dependent, .dependency]
        let all: [RelationshipType] = [.child, .dependent, .dependency]
        switch self {
        case .application:
            return child
        case .client:
            return child
        case .vendor:
            return parent
        case .group:
            return parent
        case .machine:
            return all
        case .monitor:
            return nil
        case .proxy:
            return nil
        case .resource:
            return child
        case .service:
            return parent
        case .template:
            return nil
        case .virtual:
            return nil
        case .unknown:
            return nil
        }
    }

    public func hasRelationship(of relationshipType: RelationshipType) -> Bool {
        return relationshipTypes?.contains(relationshipType) ?? false
    }

    public static var `default`: NodeType {
        return .group
    }
}

extension Node {
    /// Make an empty `Node`. For testing only.
    public static var empty: Node {
        return .init(
            id: 0,
            path: "",
            type: .service
        )
    }

    public var toShallowNode: ShallowNode {
        return .init(
            id: id,
            path: path,
            type: type,
            properties: properties,
            logo: logo,
            acl: acl
        )
    }
}

extension NodeType: Equatable {
    /// Only compares the type
    public static func ==(lhs: NodeType, rhs: NodeType) -> Bool {
        switch (lhs, rhs) {
        case (.application, .application),
             (.client, .client),
             (.vendor, .vendor),
             (.group, .group),
             (.machine, .machine),
             (.monitor, .monitor),
             (.proxy, .proxy),
             (.resource, .resource),
             (.service, .service),
             (.template, .template),
             (.virtual, .virtual),
             (.unknown, .unknown):
            return true

        case (.application, _),
             (.client, _),
             (.vendor, _),
             (.group, _),
             (.machine, _),
             (.monitor, _),
             (.proxy, _),
             (.resource, _),
             (.service, _),
             (.template, _),
             (.virtual, _),
             (.unknown, _):
            return false
        }
    }
}

/// Shallow nodes are nodes that must exist in the system.
public struct ShallowNode: ACLObject, Equatable, Codable {
    public let id: NodeID
    public let path: String
    public let type: NodeType
    public let properties: [NodeProperty]?
    public let logo: String?
    public let acl: [ACL]

    public init(
        id: NodeID,
        path: String,
        type: NodeType,
        properties: [NodeProperty]? = nil,
        logo: String? = nil,
        acl: [ACL] = []
    ) {
        self.id = id
        self.path = path
        self.type = type
        self.properties = properties
        self.logo = logo
        self.acl = acl
    }
}

/// NOTE: Middleware will be responsible for routing the end-user to the respective app to contact to the service team.
/// The `Service` could eventually be `Any`. However, that prevents us from being able to switch on the available types easily.
public enum Contact: CaseIterable, Equatable, Codable {
    case unknown
    case slack(teamId: String, channel: String)
    case phone(String)
    case email(String)
    case website(String)
    case apn(username: String, descendants: Bool)

    public static var allCases: [Contact] {
        // Order matters here. Some forms rely on the index of this array to determine if a field should be shown. The `unknown` case must always be last.
        return [
            .email(""),
            .phone(""),
            .slack(teamId: "", channel: ""),
            .website(""),
            .apn(username: "", descendants: false),
            .unknown
        ]
    }
}

public struct Node: ACLObject, Equatable, Codable {
    public struct Health: Equatable, Codable {
        // Provides context as to why the node is in an unhealthy state
        public struct Reason: Equatable, Codable {
            public struct Sample: Equatable, Codable {
                public let ts: Double
                public let value: Double
            }
            public let thresholdId: String
            public let level: AlertingLevel
            public let conditions: [String]
            public let samples: [Node.Health.Reason.Sample]
        }
        public struct Sample: Equatable, Codable {
            public var id: String // Node ID, Measurement ID
            public var name: String
            public var value: Int // 0-100
            public var reason: Node.Health.Reason?
        }
        // Identifies node as being placed in an error state manually
        public struct ManualOverride: Equatable, Codable {
            public struct Log: Equatable, Codable {
                public let ts: Double
                public let alertingLevel: AlertingLevel
                public let reason: String
            }
            public let alertingLevel: AlertingLevel
            public let reason: String
            public let logs: [Node.Health.ManualOverride.Log]
        }

        public static var empty: Node.Health {
            .init(value: 100, children: [], dependencies: [], measurements: [])
        }

        public var value: Int // 0-100
        public var manualOverride: Node.Health.ManualOverride?
        public var children: [Node.Health.Sample]
        public var dependencies: [Node.Health.Sample]
        public var measurements: [Node.Health.Sample]
    }

    public struct AlertingConfig: Equatable, Codable {
        public var actions: [ThresholdAction]
        public var children: AlertingLevel?
        public var dependencies: AlertingLevel?
        public var measurements: AlertingLevel?

        public static var empty: Node.AlertingConfig {
            .init(
                actions: [],
                children: nil,
                dependencies: nil,
                measurements: nil
            )
        }
    }

    @IgnoreEquatable
    public var id: NodeID
    public var path: String
    public var type: NodeType
    public var logo: String? // Custom image used by the team to identify themselves
    public var description: String?

    /// Graph
    public let dependencies: [Node]? // Treated as a single group in the view
    public let children: [Node]?
    public let dependents: [Node]?

    /// A value between 0-100, 0 being in danger, 100 being nominal. Health is a value computed from one or more team measurements. Therefore, there may be N measurements that determine the health of the node. The team that is currently viewing the node is the measuremet that is provided.
    /// If meausurements are not configured, this node may have no health
    public var health: Node.Health
    public var contacts: [Contact]?
    public var acl: [ACL]
    public var properties: [NodeProperty]?
    public var alertingConfig: AlertingConfig?

    public func makeShortPath(limit: Int) -> String {
        bosslib.makeShortPath(for: path, limit: limit)
    }

    public init(
        id: NodeID,
        path: String,
        type: NodeType,
        logo: String? = nil,
        description: String? = nil,
        dependencies: [Node]? = nil,
        children: [Node]? = nil,
        dependents: [Node]? = nil,
        health: Node.Health = .empty,
        contacts: [Contact]? = nil,
        acl: [ACL] = [], // TODO: This should never be empty. There should always be an owner to a `Node`
        properties: [NodeProperty]? = nil,
        alertingConfig: Node.AlertingConfig? = nil
    ) {
        self.id = id
        self.path = path
        self.type = type
        self.logo = logo
        self.description = description
        self.dependencies = dependencies
        self.children = children
        self.dependents = dependents
        self.health = health
        self.contacts = contacts
        self.acl = acl
        self.properties = properties
        self.alertingConfig = alertingConfig
    }

    public var name: String {
        String(path.split(separator: ".").last ?? "")
    }

    /// Is top-level domain
    public var isTld: Bool {
        path.split(separator: ".").count == 1
    }

    public var isTemplate: Bool {
        switch type {
        case .unknown,
             .client,
             .service,
             .resource,
             .group,
             .machine,
             .application,
             .proxy,
             .monitor,
             .vendor,
             .virtual:
            return false
        case .template:
            return true
        }
    }

    public var isVirtual: Bool {
        switch type {
        case .unknown,
             .client,
             .service,
             .resource,
             .group,
             .machine,
             .application,
             .proxy,
             .monitor,
             .vendor,
             .template:
            return false
        case .virtual:
            return true
        }
    }

    public var orgPath: String? {
        path.orgPath
    }

    public var isOrg: Bool {
        return path == orgPath
    }

    public func rename(to name: String) -> Node {
        var path = path
        var paths = path.components(separatedBy: ".")

        guard paths.last != name else {
            return self
        }

        _ = paths.popLast()
        paths.append(name)
        path = paths.joined(separator: ".")

        let node = with(self) { o in
            o.path = path
        }

        return node
    }
}

public struct TemplateReferenceStats {
    let numPublicNodes: Int
    let numPrivateNodes: Int
    let nodes: [Node]
}

/// Convert a long path name to a condensed form with a `*` separating the first and last parts of the path.
/// Example: If String is `com.bithead.mobile.ios` and `limit` is `5` this will shorten the name to be `com.b*e.ios`
public func makeShortPath(for path: String, limit: Int) -> String {
    if path.count > limit {
        let halfOfLength = Int(floor(Float(limit) / Float(2)))
        let firstPart = path.substring(to: halfOfLength - 1) // - 1 to start 0 index
        let lastPart = path.substring(from: path.count - halfOfLength)
        return "\(firstPart)*\(lastPart)"
    }
    else {
        return path
    }
}
