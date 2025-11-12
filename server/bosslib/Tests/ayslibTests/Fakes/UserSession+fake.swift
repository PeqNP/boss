/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

@testable import bosslib

extension UserSession {
    static func fake(
        tokenId: TokenID = "",
        accessToken: AccessToken = "",
        jwt: BOSSJWT = .fake()
    ) -> UserSession {
        .init(tokenId: tokenId, accessToken: accessToken, jwt: jwt)
    }
}

extension BOSSJWT {
    static func fake(
        id: String = "",
        issuedAt: Date = .now,
        subject: String = "",
        expiration: Date = .now,
        apps: [ACLID] = [],
        acl: [ACLID] = []
    ) -> BOSSJWT {
        .init(
            id: id,
            issuedAt: issuedAt,
            subject: subject,
            expiration: expiration,
            apps: apps,
            acl: acl
        )
    }
}
