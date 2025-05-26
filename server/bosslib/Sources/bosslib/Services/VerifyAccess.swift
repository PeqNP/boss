
/// Verify access token and return an `AuthenticatedUser`.
///
/// - Parameter accessToken: Access token to verify
/// - Parameter peer: The location from which the request was sent from
/// - Returns: An authenticated user
public func verifyAccess(accessToken: String?, peer: String?) async throws -> AuthenticatedUser {
    let session = try await api.account.verifyAccessToken(accessToken)
    guard let userID = UserID(session.jwt.subject.value) else {
        boss.log.e("User ID (\(session.jwt.subject.value)) could not be decoded from JWT (\(session.jwt)) token ID (\(session.tokenId))")
        throw api.error.AccessError()
    }
    boss.log.d("Verified user ID (\(session.jwt.subject.value))")
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
