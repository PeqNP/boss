/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

import Foundation

public struct NodeProperty: Equatable, Codable {
    public enum `Type`: Equatable, Codable {
        // System-generated property. Things like the Node's name, type, etc.
        case system
        // Custom property associated directly to Node
        case custom
        // Custom property derived from the Node of respective Measurement template.
        case template(nodeId: String, nodePath: String)
        case unknown
    }

    public var id: String?
    public var type: NodeProperty.`Type`
    public var name: String
    // This can either the value set by a user or a default value from a template.
    public var value: String?
}
