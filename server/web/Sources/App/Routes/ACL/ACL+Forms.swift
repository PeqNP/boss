/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Vapor

enum ACLForm {
    struct ACL: Content {
        let name: String
        let permissions: [String]
    }
    struct RegisterACL: Content {
        let acls: [ACLForm.ACL]
    }
}
