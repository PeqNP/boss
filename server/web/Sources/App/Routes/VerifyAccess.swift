/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import Vapor

/// Verifies the `Authorization: Bearer <JWT>` token against a cached token.
///
/// - Parameter request: The HTTP `Request`
/// - Returns: An `AuthenticatedUser`
/// - Throws: If authorization token is invalid, user is not found, etc.
func verifyAccess(header request: Request, refreshToken: Bool = true, verifyMfaChallenge: Bool = true) async throws -> AuthenticatedUser {
    let authorization = request.headers.first(name: "Authorization")
    let accessToken: String? = if let authorization {
        String(authorization.trimmingPrefix("Bearer "))
    } else {
        nil
    }
    return try await verifyAccess(
        accessToken: accessToken,
        peer: request.peerAddress?.description,
        refreshToken: refreshToken,
        verifyMfaChallenge: verifyMfaChallenge
    )
}

func verifyAccess(cookie request: Request, refreshToken: Bool = true, verifyMfaChallenge: Bool = true) async throws -> AuthenticatedUser {
    // For testing 👇
    // return api.account.guestUser()
    let accessToken = request.cookies["accessToken"]?.string
    return try await verifyAccess(
        accessToken: accessToken,
        peer: request.peerAddress?.description,
        refreshToken: refreshToken,
        verifyMfaChallenge: verifyMfaChallenge
    )
}
