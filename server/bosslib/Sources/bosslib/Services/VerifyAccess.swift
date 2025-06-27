
/// Verify access token and return an `AuthenticatedUser`.
///
/// - Parameters:
///     - accessToken: Access token to verify
///     - peer: Where user is connecting from
///     - refreshToken: Refresh the token's TTL
///     - verifyMfaChallenge: If `true`, user must have passed the MFA challenge
/// - Returns: An authenticated user
public func verifyAccess(
    accessToken: String?,
    peer: String?,
    refreshToken: Bool = true,
    verifyMfaChallenge: Bool = true
) async throws -> AuthenticatedUser {
    let session = try await api.account.verifyAccessToken(accessToken, refreshToken: refreshToken, verifyMfaChallenge: verifyMfaChallenge)
    guard let userID = UserID(session.jwt.subject.value) else {
        boss.log.e("User ID (\(session.jwt.subject.value)) could not be decoded from JWT (\(session.jwt)) token ID (\(session.tokenId))")
        throw api.error.AccessError()
    }
    boss.log.d("Verified user ID (\(session.jwt.subject.value))")
    let user = try await api.account.user(auth: superUser(), id: userID)
    let auth = AuthenticatedUser(user: user, session: session, peer: peer)
    // If user has been disabled, do not allow them into the system
    guard auth.isSuperUser || user.enabled else {
        throw api.error.UserNotFound()
    }
    guard auth.isSuperUser || user.verified else {
        throw api.error.UserIsNotVerified()
    }
    return auth
}
