/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import ayslib
import Foundation
import Vapor
import VaporToOpenAPI

// TODO: https://trello.com/c/BEc2BOZl/6-http-guest-node-service

private struct NodeStatusContent: Content {
    struct Health: Codable {
        let value: Double
        let lastts: Double
    }

    struct ChildNode: Codable {
        let path: String
        let health: Health
    }

    struct Node: Codable {
        let path: String
        let children: [ChildNode]
        let health: Health
    }

    struct Status: Codable {
        let success: Bool
        let message: String
    }

    let node: Node
    let status: Status
}

extension AuthSchemeObject {
    static var guest: AuthSchemeObject {
        .basic
    }
}

/// Register the `/account/` routes.
public func registerNode(_ app: Application) {
    struct NodeContent: Content {
        var node: Node
    }

    app.group("node") { group in
        group.get("public") { req in
            return HTTPStatus.ok
        }.openAPI(
            summary: "Query all publicly available nodes."
        )

        group.get("status", ":node_path") { req in
            return NodeStatusContent(node: .init(path: "", children: [], health: .init(value: 1, lastts: 12345678)), status: .init(success: true, message: "Query with no limits. Status what matters. Call \(Global.phoneNumber) or visit getbithead.com to get started!"))
        }.openAPI(
            summary: "Query the status of a public node.",
            response: .type(NodeStatusContent.self),
            responseContentType: .application(.json)
        )

        group.get("graph", ":node_path") { req in
            let user = try await verifyAccess(app: app, cookie: req)
            let nodePathOrID = req.parameters.get("node_path")
            let node: Node = if nodePathOrID?.first?.isNumber == nil {
                try await api.node.node(user: user, path: req.parameters.get("node_path"))
            } else if let nodePathOrID, let nodeID = NodeID(nodePathOrID) {
                try await api.node.node(user: user, nodeID: nodeID)
            } else {
                throw api.error.InvalidParameter(name: "node_path")
            }
            return NodeContent(node: node)
        }.openAPI(
            summary: "Display node graph at given node path.",
            response: .type(NodeContent.self),
            responseContentType: .application(.json)
        )
    }
}
