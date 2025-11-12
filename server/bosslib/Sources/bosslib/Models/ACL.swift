/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

import Foundation

public typealias ACLID = Int
public typealias ACLItemID = Int
public typealias ACLFeature = String
public typealias ACLPath = String
public typealias AppLicenseID = Int
public typealias BundleID = String

/// Provides map for an ACL path to its respective internal ACL ID. This is used when determining if a user has access to a feature. This map could potentially live inside of Reddis, etc.
public typealias ACLPathMap = [ACLPath: ACLID]

public struct ACLCatalog: Codable, Equatable, Sendable {
    var paths: ACLPathMap
}

/// This is an intermediary structure used when registering an ACL catalog.
public struct ACLApp: Codable, Equatable, Sendable {
    public let bundleId: BundleID
    public let features: Set<ACLFeature>
        
    public init(bundleId: BundleID, features: Set<ACLFeature>) {
        self.bundleId = bundleId
        self.features = features
    }
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
    struct App: Codable, Equatable, Sendable {
        let id: Int
        let name: String
        let features: [ACLTree.Feature]
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
    
    public func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }
}

/// Represents an ACL that is assigned to a user.
public struct ACLItem: Codable, Equatable, Sendable {
    public let id: ACLItemID?
    public let createDate: Date
    public let aclId: ACLID
    public let userId: UserID
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
    public let userId: UserID
}
