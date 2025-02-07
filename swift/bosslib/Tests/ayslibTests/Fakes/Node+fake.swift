/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

@testable import ayslib

extension Node {
    static func fake(
        id: NodeID = 0,
        path: String = "",
        type: NodeType = .service,
        logo: String? = nil,
        description: String? = nil,
        dependencies: [Node]? = nil,
        children: [Node]? = nil,
        dependents: [Node]? = nil,
        health: Node.Health = .empty,
        contacts: [Contact]? = nil,
        acl: [ACL] = [],
        properties: [NodeProperty]? = nil,
        alertingConfig: Node.AlertingConfig? = nil
    ) -> Node {
        .init(
            id: id,
            path: path,
            type: type,
            logo: logo,
            description: description,
            dependencies: dependencies,
            children: children,
            dependents: dependents,
            health: health,
            contacts: contacts,
            acl: acl,
            properties: properties,
            alertingConfig: alertingConfig
        )
    }
}
