/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import JWTKit

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
        id: IDClaim = .init(value: ""),
        issuedAt: IssuedAtClaim = .init(value: .now),
        subject: SubjectClaim = .init(value: ""),
        expiration: ExpirationClaim = .init(value: .now)
    ) -> BOSSJWT {
        .init(
            id: id,
            issuedAt: issuedAt,
            subject: subject,
            expiration: expiration
        )
    }
}
