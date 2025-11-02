/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.
///
/// There are two types of ACL models
/// 1. Node ACL. It is not currently used. It is an artifact of @ys
/// 2. BOSS ACL. Actively used as a way to verify that a user has access to a resource in the OS and/or app.

import Foundation

/// NOTE: Not all object types will include all types of operations (such as `execute`)
/// There may need to be an `acl` type which restricts whether the user can perform ACL operations for a given object. For now, this operation is covered by `write` (create and update).
public struct ACLOp: OptionSet, Hashable, CaseIterable, Equatable, Codable, Sendable {
    public let rawValue: Int

    public var hashValue: Int {
        return self.rawValue
    }

    public static let read = ACLOp(rawValue: 1 << 0)
    public static let write = ACLOp(rawValue: 1 << 1)
    public static let delete = ACLOp(rawValue: 1 << 2)
    public static let execute = ACLOp(rawValue: 1 << 3)

    public static let all: [ACLOp] = [.read, .write, .delete, .execute]

    public init(rawValue: Int) {
        self.rawValue = rawValue
    }

    public static func ==(lhs: ACLOp, rhs: ACLOp) -> Bool {
        return lhs.hashValue == rhs.hashValue
    }

    public static var allCases: [ACLOp] {
        return [
            .read,
            .write,
            .delete,
            .execute
        ]
    }
}

public typealias EntityID = Int

public struct Entity: Equatable, Codable {
    public let id: EntityID
    public let name: String
    public let type: ACL.EntityType
    public let enabled: Bool
}

public struct ACL: Equatable, Codable {
    public enum EntityType: CaseIterable, Equatable, Codable {
        /// Special case that includes all users
        case all
        case individual(UserID)
        /// `group` is also used to create "teams"
        case group([UserID])
        case entities([Entity])

        public static var allCases: [EntityType] {
            return [
                .all,
                .individual(0),
                .group([]),
                .entities([])
            ]
        }
    }

    public enum ReadOnlyReason: Equatable, Codable {
        case admin
        case owner(UserID)
        case systemAssigned
    }

    /// The name of the entity. This is necessary for groups.
    /// If the `EntityType` is a `individual`, this value inherits the `User`s username as the `name`
    public let name: String
    public var operations: [ACLOp]
    public let type: EntityType
    /// Identifies this ACLEntity as being a read-only entity. It's information can _not_ be changed. Special groups, such as administrators, may fall into this read-only category of `ACLEntity`s. This information is _not_ saved when saving ACL to the server.
    public let readOnly: ReadOnlyReason?
}

public extension ACL {
    /// Common ACL used for all nodes that are created by a specific user
    static func makeOwnerACL(using user: User) -> ACL {
        .init(name: "Owner", operations: [.read, .write, .delete, .execute], type: .individual(user.id), readOnly: nil)
    }
}

public protocol ACLObject {
    var acl: [ACL] { get }
}

public extension Array where Element == ACLOp {
    static var all: [ACLOp] {
        return ACLOp.all
    }
}

/// BOSS ACL

public typealias ACLCatalogID = Int
public typealias ACLAppID = Int
public typealias ACLItemID = Int
public typealias BundleID = String
public typealias ACLFeature = String

public struct ACLCatalog: Codable, Equatable, Sendable {
    public let id: ACLCatalogID
    public let name: String
    public let apps: [ACLApp]
    
    public init(id: ACLCatalogID, name: String, apps: [ACLApp]) {
        self.id = id
        self.name = name
        self.apps = apps
    }
}

public struct ACLApp: Codable, Equatable, Sendable {
    public let id: ACLAppID?
    public let bundleId: BundleID
    public let features: Set<ACLFeature>
    
    public init(id: ACLAppID, bundleId: BundleID, features: Set<ACLFeature>) {
        self.id = id
        self.bundleId = bundleId
        self.features = features
    }
    
    public init(bundleId: BundleID, features: Set<ACLFeature>) {
        self.id = nil
        self.bundleId = bundleId
        self.features = features
    }
}

/// There are 3 types of ACL access
/// 1. The user needs to be signed in. No ACL is needed. The system/app needs a user to save information
/// 2. The app requires that a user has access to the app. All features are allowed.
/// 3. The app requries granular control over specific features within the app.

public enum ACLScope: Equatable, Sendable {
    /// A signed in user is required to access the service
    case user
    /// Used when an app only cares that the user has access to use the app
    case app(BundleID)
    /// Used when needing to provide more granular control over features within an app. Expects value to be in "FeatureName.Permission" format.
    case feature(BundleID, ACLFeature)
}

/// Represents an individual ACL item that is used to test if a user has access to a specific resource.
public struct ACLItem: Equatable {
    public let id: ACLItemID?
    public let bundleId: BundleID
    // First part of ACLFeature
    public let name: String
    // Second part of ACLFeature
    public let permission: String
    
    public init(id: ACLItemID, bundleId: BundleID, name: String, permission: String) {
        self.id = id
        self.bundleId = bundleId
        self.name = name
        self.permission = permission
    }
    
    public init(bundleId: BundleID, name: String, permission: String) {
        self.id = nil
        self.bundleId = bundleId
        self.name = name
        self.permission = permission
    }
    
    public static func require(_ bundleId: BundleID, _ name: String, _ permission: String) -> ACLItem {
        .init(bundleId: bundleId, name: name, permission: permission)
    }
}
