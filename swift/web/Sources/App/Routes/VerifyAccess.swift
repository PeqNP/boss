/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import ayslib
import Vapor

struct AccessError: Error { }

/// Verifies the `Authorization: Bearer <JWT>` token against a cached token.
///
/// - Parameter request: The HTTP `Request`
/// - Returns: An `AuthenticatedUser`
/// - Throws: If authorization token is invalid, user is not found, etc.
func verifyAccess(app: Application, header request: Request) async throws -> AuthenticatedUser {
    let authorization = request.headers.first(name: "Authorization")
    let accessToken: String? = if let authorization {
        String(authorization.trimmingPrefix("Bearer "))
    } else {
        nil
    }
    return try await verifyAccess(app: app, accessToken: accessToken, peer: request.peerAddress?.description)
}

func verifyAccess(app: Application, cookie request: Request) async throws -> AuthenticatedUser {
    // For testing
    // return api.account.guestUser()
    let accessToken = request.cookies["accessToken"]?.string
    return try await verifyAccess(app: app, accessToken: accessToken, peer: request.peerAddress?.description)
}

func verifyAccess(app: Application, accessToken: String?, peer: String?) async throws -> AuthenticatedUser {
    let session = try await api.account.verifyAccessToken(accessToken)
    guard let userID = UserID(session.jwt.subject.value) else {
        app.logger.error("User ID (\(session.jwt.subject.value)) could not be decoded from JWT (\(session.jwt)) token ID (\(session.tokenId))")
        throw AccessError()
    }
    app.logger.debug("Verified user ID (\(session.jwt.subject.value))")
    let user = try await api.account.user(auth: api.account.superUser(), id: userID)
    let auth = AuthenticatedUser(user: user, peer: peer)
    // If user has been disabled, do not allow them into the system
    guard auth.isSuperUser || user.enabled else {
        throw api.error.UserNotFound()
    }
    guard auth.isSuperUser || user.verified else {
        throw api.error.UserIsNotVerified()
    }
    return auth
}
