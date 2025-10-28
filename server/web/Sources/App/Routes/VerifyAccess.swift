/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import Vapor

func verifyAccess(
    _ request: Request,
    refreshToken: Bool = true,
    verifyMfaChallenge: Bool = true,
    acl: ACLScope? = nil
) async throws -> AuthenticatedUser {
    // For testing 👇
    // return api.account.guestUser()
    let accessToken = request.cookies["accessToken"]?.string
    return try await verifyAccess(
        accessToken: accessToken,
        peer: request.peerAddress?.description,
        refreshToken: refreshToken,
        verifyMfaChallenge: verifyMfaChallenge,
        acl: acl
    )
}
