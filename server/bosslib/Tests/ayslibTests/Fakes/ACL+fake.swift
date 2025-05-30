/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

@testable import bosslib

extension ACL {
    static func fake(
        name: String = "",
        operations: [ACLOp] = [],
        type: EntityType = .all,
        readOnly: ReadOnlyReason? = nil
    ) -> ACL {
        .init(name: name, operations: operations, type: type, readOnly: readOnly)
    }
}

extension Entity {
    static func fake(
        id: EntityID = 0,
        name: String = "",
        type: ACL.EntityType = .all,
        enabled: Bool = false
    ) -> Entity {
        .init(id: id, name: name, type: type, enabled: enabled)
    }
}

struct FakeACLObject: ACLObject {
    var acl: [ACL]
    
    init(acl: [ACL] = []) {
        self.acl = acl
    }
}
