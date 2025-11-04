/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

import Foundation

public typealias ACLID = Int
public typealias ACLItemID = Int
public typealias BundleID = String
public typealias ACLFeature = String
public typealias ACLPath = String

public struct ACLCatalog: Codable, Equatable, Sendable {
    /// `ACLPath` maps to its respective internal ACL ID.
    let paths: [ACLPath: ACLID]
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

/// There are 3 types of ACL access
/// 1. The user needs to be signed in. No ACL is needed. The system/app needs a user to save information
/// 2. The app requires that a user has access to the app. All features are allowed.
/// 3. The app requries granular control over specific features within the app.

/// This is an intermediary structure used when registering an ACL catalog.
public enum ACLScope: Equatable, Sendable {
    /// A signed in user is required to access the service
    case user
    /// Used when an app only cares that the user has access to use the app
    case app(BundleID)
    /// Used when needing to provide more granular control over features within an app. Expects value to be in "FeatureName.Permission" format.
    case feature(BundleID, ACLFeature)
    
    /// Add a `.feature` to an `.app` scope.
    /// This is a convenience method used when building route permissions.
    public func feature(_ feature: String) -> ACLScope {
        switch self {
        case .user:
            boss.log.w("Can not add feature to .user scope")
            return self
        case let .app(bundleId):
            return .feature(bundleId, feature)
        case .feature:
            boss.log.w("Can not add feature to .feature scope")
            return self
        }
    }
}

/// Represents an ACL resource
public struct ACL: Equatable {
    public let id: ACLID
    public let createDate: Date
    public let path: String
}

/// Represents an ACL that is assigned to a user.
public struct ACLItem: Equatable {
    public let id: ACLItemID?
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
}
