/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Smtp
import Vapor

/// Register the private `/acl/` routes.
///
/// These routes are not accessible to the public.
public func registerACL(_ app: Application) {
    app.group("acl") { group in
        group.post("register") { req in
            let fragment = Fragment.RegisteredACL(success: true)
            return fragment
        }.openAPI(
            summary: "Register BOSS service ACLs",
            body: .type(ACLForm.RegisterACL.self),
            contentType: .application(.urlEncoded),
            response: .type(Fragment.RegisteredACL.self),
            responseContentType: .application(.json)
        )
    }
}
