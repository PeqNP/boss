/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

import Foundation

public typealias ACLID = Int
public typealias ACLItemID = Int
public typealias ACLFeature = String
public typealias ACLPath = String
public typealias AppLicenseID = Int
public typealias BundleID = String
public typealias ACLRoleID = Int
public typealias ACLRoleName = String

/// Provides map for an ACL path to its respective internal ACL ID. This is used when determining if a user has access to a feature. This map could potentially live inside of Reddis, etc.
public typealias ACLPathMap = [ACLPath: ACLID]

public struct ACLCatalog: Codable, Equatable, Sendable {
    var paths: ACLPathMap
}

/// This is an intermediary structure used when registering an ACL catalog.
public struct ACLApp: Codable, Equatable, Sendable {
    public let bundleId: BundleID
    public let features: Set<ACLFeature>
    /// Role label to the features it holds, as the app's routes named them.
    ///
    /// An app registering none receives a `default` role holding every feature,
    /// so an app works before it declares roles of its own.
    public let roles: [ACLRoleName: Set<ACLFeature>]
        
    public init(bundleId: BundleID, features: Set<ACLFeature>,
                roles: [ACLRoleName: Set<ACLFeature>] = [:]) {
        self.bundleId = bundleId
        self.features = features
        self.roles = roles
    }
}

/// A named set of permissions within one app.
///
/// A role is what a user is granted. The features it holds change as an app's
/// routes are retagged, and the role keeps its ID through that — so a grant is
/// made once and survives every deploy that moves a permission between roles.
public struct ACLRole: Codable, Equatable, Sendable {
    public let id: ACLRoleID
    public let createDate: Date
    /// The app this role belongs to, as an `ACLType.app` record.
    public let appAclId: ACLID
    /// The label the app declared, which is what Settings shows.
    public let name: ACLRoleName
    /// When this role stopped being named by any route. `nil` while it is.
    public let retiredDate: Date?
}

public struct ACLTree: Codable, Equatable, Sendable {
    struct Permission: Codable, Equatable, Sendable {
        let id: Int
        let name: String
    }
    struct Feature: Codable, Equatable, Sendable {
        let id: Int
        let name: String
        let permissions: [ACLTree.Permission]
    }
    /// A role, and what it holds.
    ///
    /// The permissions are shown rather than edited: what a role holds is
    /// declared by the app's routes and rebuilt on every registration.
    struct Role: Codable, Equatable, Sendable {
        let id: ACLRoleID
        let name: ACLRoleName
        /// What the role holds, by feature. Settings lists one line a feature
        /// — `Job: r, w` — beneath the role's checkbox.
        let features: [ACLTree.Feature]
    }
    struct App: Codable, Equatable, Sendable {
        let id: Int
        let name: String
        let features: [ACLTree.Feature]
        /// What a user is granted. `features` is what those roles are made of.
        let roles: [ACLTree.Role]
    }
    struct Catalog: Codable, Equatable, Sendable {
        let id: Int
        let name: String
        let apps: [ACLTree.App]
    }
    
    let catalogs: [ACLTree.Catalog]
}

/// Represents an ACL resource
public struct ACL: Equatable, Hashable {
    public enum ACLType: Int {
        case unknown = 0
        case catalog = 1
        case app = 2
        case feature = 3
        case permission = 4
    }
    
    public let id: ACLID
    public let createDate: Date
    public let path: String
    public let type: ACLType
    /// When this ACL stopped being registered. `nil` while it is registered.
    ///
    /// A retired ACL keeps its ID, its grants, and its licenses. It answers no
    /// verification, and registering its path again revives it — so a name that
    /// comes back is the same record, and tokens already naming it still work.
    public let retiredDate: Date?
    
    public func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }
}

/// Represents an ACL that is assigned to a user.
public struct ACLItem: Codable, Equatable, Sendable {
    public let id: ACLItemID?
    public let createDate: Date
    public let aclId: ACLID
    public let userId: User.ID
}

/// Used as the ACL "key" when a service is asking if the current user has permission to access the respective resource.
///
/// Internally this is converted to an `ACLPath`, which is used to quickly find its respective ACLID.
public struct ACLKey: Codable, Equatable, Sendable {
    public let catalog: String // e.g. python
    public let bundleId: String // e.g. io.bithead.test-manager
    public let feature: String? // e.g. projects.r
    
    public init(catalog: String, bundleId: String, feature: String?) {
        self.catalog = catalog
        self.bundleId = bundleId
        self.feature = feature
    }
}

/// An app license is how the system knows whether a user can open the app or not
public struct AppLicense: Codable, Equatable, Sendable {
    public let id: AppLicenseID
    public let createDate: Date
    public let appAclId: ACLID
    public let userId: User.ID
}
