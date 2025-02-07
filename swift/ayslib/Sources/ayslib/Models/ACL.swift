/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

import Foundation

/// NOTE: Not all object types will include all types of operations (such as `execute`)
/// There may need to be an `acl` type which restricts whether the user can perform ACL operations for a given object. For now, this operation is covered by `write` (create and update).
public struct ACLOp: OptionSet, Hashable, CaseIterable, Equatable, Codable {
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
        case parentOwner(UserID, NodePath)
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
