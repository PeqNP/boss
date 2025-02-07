/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

public struct GlobalSoftwareKey: Equatable {
    public let id: Int
    public let name: String
    public let description: String?
    public let enabled: Bool
}

// Represents a software key that can be accessed from scripts.
public struct SoftwareKey: Equatable {
    public enum Owner: Equatable {
        case me
        case ancestor(nodePath: NodePath, globalSoftwareKeyId: Int?)
        case global(id: Int)
    }

    public let id: Int?
    public let owner: Owner
    public let name: String
    public let value: String
    public let inherited: Bool
    public let enabled: Bool

    public var isReadOnly: Bool {
        switch owner {
        case .ancestor:
            return true
        case .me, .global:
            return false
        }
    }

    public static func empty() -> SoftwareKey {
        .init(id: nil, owner: .me, name: "", value: "", inherited: true, enabled: true)
    }
}

/// Represents all software keys that can be displayed in a parameter field
public struct AllSoftwareKeys {
    /// Keys associated to node
    public let nodeKeys: [SoftwareKey]
    /// All global enabled global keys
    public let globalKeys: [GlobalSoftwareKey]

    public static func empty() -> AllSoftwareKeys {
        .init(nodeKeys: [], globalKeys: [])
    }
}

public struct NodeSoftwareKeys: Equatable {
    /// Keys associated to node
    public let keys: [SoftwareKey]
    /// Available global keys that can be associated to
    public let availableGlobalKeys: [GlobalSoftwareKey]

    public static func empty() -> NodeSoftwareKeys {
        .init(keys: [], availableGlobalKeys: [])
    }

    public func keyName(for id: Int) -> String {
        for key in keys {
            if key.id == id {
                return key.name
            }
        }
        return "Not found"
    }

    public func globalKeyName(for id: Int) -> String {
        for key in keys {
            switch key.owner {
            case .me:
                continue
            case let .global(id):
                if key.id == id {
                    return key.name
                }
            case .ancestor:
                continue
            }
        }
        for key in availableGlobalKeys {
            if key.id == id {
                return key.name
            }
        }
        return "Not found"
    }
}
