/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

import Foundation

class ACLDirectory {

    let acl: ACL

    init(aclEntity: ACL) {
        self.acl = aclEntity
    }

    func entity(for user: User) -> ACL? {
        return nil
    }
}
