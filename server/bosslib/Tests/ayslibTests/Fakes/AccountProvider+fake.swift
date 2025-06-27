/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

@testable import bosslib

class FakeAccountProvider: AccountProvider {
    var _users: (Database.Session, AuthenticatedUser) async throws -> [User] = { _, _ in fatalError("AccountProvider.users") }
    var _createAccount: (Database.Session, AuthenticatedUser, String?, String?, String?, Bool) async throws -> (User, VerificationCode?) = { _, _, _, _, _, _ in fatalError("AccountProvider.createAccount") }
    var _createUser: (Database.Session, AuthenticatedUser, String?, String?, String?, Bool, Bool) async throws -> User = { _, _, _, _, _, _, _ in fatalError("AccountProvider.createUser") }
    var _saveUser: (Database.Session, AuthenticatedUser, UserID?, String?, String?, String?, Bool, Bool) async throws -> User = { _, _, _, _, _, _, _, _ in fatalError("AccountProvider.saveUser") }
    var _updateUser: (Database.Session, AuthenticatedUser, User) async throws -> User = { _, _, _ in fatalError("AccountProvider.updateUser") }
    var _deleteUser: (Database.Session, AuthenticatedUser, UserID) async throws -> Void = { _, _, _ in fatalError("AccountProvider.deleteUser") }
    
    var _generateTotpSecret: (Database.Session, AuthenticatedUser, User) async throws -> (TOTPSecret, URL) = { _, _, _ in fatalError("AccountProvider.generateTotpSecret") }
    var _registerMfa: (Database.Session, AuthenticatedUser, MFACode?) async throws -> User = { _, _, _ in fatalError("AccountProvider.registerMfa") }
    
    var _sendVerificationCode: (Database.Session, User) async throws -> String = { _, _ in fatalError("AccountProvider.sendVerificationCode") }
    var _userWithID: (Database.Session, AuthenticatedUser, UserID) async throws -> User = { _, _, _ in fatalError("AccountProvider.userWithID") }

    var _signIn: (Database.Session, String?, String?) async throws -> (User, UserSession) = { _, _, _ in fatalError("AccountProvider.signIn") }
    var _verifyCredentials: (Database.Session, String?, String?) async throws -> User = { _, _, _ in fatalError("AccountProvider.verifyCredentials") }
    var _verifyMfa: (Database.Session, AuthenticatedUser, MFACode?) async throws -> Void = { _, _, _ in fatalError("AccountProvider.verifyMfa") }
    var _makeUserSession: (Database.Session, User) async throws -> UserSession = { _, _ in fatalError("AccountProvider.makeUserSession") }
    
    var _verifyAccountCode: (Database.Session, VerificationCode?) async throws -> User = { _, _ in fatalError("AccountProvider.verifyAccountCode") }
    var _verifyAccessToken: (Database.Session, AccessToken?, Bool, Bool) async throws -> UserSession = { _, _, _, _ in fatalError("AccountProvider.verifyAccessToken") }
    var _internalVerifyAccessToken: (AccessToken, Bool, Bool) async throws -> BOSSJWT = { _, _, _ in fatalError("AccountProvider.internalVerifyAccessToken") }
    var _registerSlackCode: (Database.Session, String?) async throws -> String = { _, _ in fatalError("AccountProvider.registerSlackCode") }
    var _signOut: (Database.Session, AuthenticatedUser) async throws -> Void = { _, _ in fatalError("AccountProvider.signOut") }

    func users(session: bosslib.Database.Session, user: bosslib.AuthenticatedUser) async throws -> [bosslib.User] {
        try await _users(session, user)
    }
    
    func createAccount(session: bosslib.Database.Session, admin: bosslib.AuthenticatedUser, fullName: String?, email: String?, password: String?, verified: Bool) async throws -> (bosslib.User, bosslib.VerificationCode?) {
        try await _createAccount(session, admin, fullName, email, password, verified)
    }
    
    func createUser(session: bosslib.Database.Session, admin: bosslib.AuthenticatedUser, email: String?, password: String?, fullName: String?, verified: Bool, enabled: Bool) async throws -> bosslib.User {
        try await _createUser(session, admin, email, password, fullName, verified, enabled)
    }
    
    func saveUser(session: bosslib.Database.Session, user: bosslib.AuthenticatedUser, id: bosslib.UserID?, email: String?, password: String?, fullName: String?, verified: Bool, enabled: Bool) async throws -> bosslib.User {
        try await _saveUser(session, user, id, email, password, fullName, verified, enabled)
    }
    
    func updateUser(session: bosslib.Database.Session, auth: bosslib.AuthenticatedUser, user: bosslib.User) async throws -> bosslib.User {
        try await _updateUser(session, auth, user)
    }
    
    func deleteUser(session: bosslib.Database.Session, auth: bosslib.AuthenticatedUser, id: bosslib.UserID) async throws {
        try await _deleteUser(session, auth, id)
    }
    
    func generateTotpSecret(session: bosslib.Database.Session, authUser: bosslib.AuthenticatedUser, user: bosslib.User) async throws -> (bosslib.TOTPSecret, URL) {
        try await _generateTotpSecret(session, authUser, user)
    }
    
    func registerMfa(session: bosslib.Database.Session, authUser: bosslib.AuthenticatedUser, code: bosslib.MFACode?) async throws -> bosslib.User {
        try await _registerMfa(session, authUser, code)
    }
    
    func user(session: bosslib.Database.Session, auth: bosslib.AuthenticatedUser, id: bosslib.UserID) async throws -> bosslib.User {
        try await _userWithID(session, auth, id)
    }
    
    func signIn(session: bosslib.Database.Session, email: String?, password: String?) async throws -> (bosslib.User, bosslib.UserSession) {
        try await _signIn(session, email, password)
    }
    
    func verifyCredentials(session: bosslib.Database.Session, email: String?, password: String?) async throws -> bosslib.User {
        try await _verifyCredentials(session, email, password)
    }
    
    func verifyMfa(session: bosslib.Database.Session, authUser: bosslib.AuthenticatedUser, code: String?) async throws {
        try await _verifyMfa(session, authUser, code)
    }
    
    func makeUserSession(session: bosslib.Database.Session, user: bosslib.User) async throws -> bosslib.UserSession {
        try await _makeUserSession(session, user)
    }
    
    func sendVerificationCode(session: bosslib.Database.Session, to user: bosslib.User) async throws -> bosslib.VerificationCode {
        try await _sendVerificationCode(session, user)
    }
    
    func verifyAccountCode(session: bosslib.Database.Session, code: bosslib.VerificationCode?) async throws -> bosslib.User {
        try await _verifyAccountCode(session, code)
    }
    
    func verifyAccessToken(session: bosslib.Database.Session, _ accessToken: bosslib.AccessToken?, refreshToken: Bool, verifyMfaChallenge: Bool) async throws -> bosslib.UserSession {
        try await _verifyAccessToken(session, accessToken, refreshToken, verifyMfaChallenge)
    }
    
    func registerSlackCode(session: bosslib.Database.Session, _ code: String?) async throws -> String {
        try await _registerSlackCode(session, code)
    }
    
    func signOut(session: bosslib.Database.Session, user: bosslib.AuthenticatedUser) async throws {
        try await _signOut(session, user)
    }
}
