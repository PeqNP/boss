/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

public typealias MFACode = String
// Base32 TOTP secret
public typealias TOTPSecret = String
public typealias UserID = Int
public typealias VerificationCode = String

public enum AccountSystem: Int, Equatable, Codable, Sendable {
    case boss
}

public struct User: Equatable, Codable, Sendable {
    @IgnoreEquatable
    public var id: UserID
    public let system: AccountSystem
    public var fullName: String
    public var email: String
    /// Password is encrypted. Therefore, equating is not useful.
    @IgnoreEquatable
    public var password: String
    public var verified: Bool
    public var enabled: Bool
    public var mfaEnabled: Bool
    public var totpSecret: String?
    
    public var avatarUrl: URL?
    public var preferredTheme: String?
    public var preferredFont: String?
}

public struct AuthenticatedUser: Equatable {
    public let user: User
    public let session: UserSession
    let peer: String?

    public init(user: User, session: UserSession, peer: String?) {
        self.user = user
        self.session = session
        self.peer = peer
    }
    
    public var isSuperUser: Bool {
        user.id == Global.superUserId
    }

    public var isGuestUser: Bool {
        user.id == Global.guestUserId
    }

    public var enabled: Bool {
        user.enabled
    }

    public var verified: Bool {
        user.verified
    }
}

public typealias TokenID = String
public typealias AccessToken = String

public struct UserSession: Equatable {
    public let tokenId: TokenID
    public let accessToken: AccessToken
    public let jwt: BOSSJWT

    init(tokenId: TokenID, accessToken: AccessToken, jwt: BOSSJWT) {
        self.tokenId = tokenId
        self.accessToken = accessToken
        self.jwt = jwt
    }
}

public struct ShallowUserSession: Equatable {
    public let tokenId: TokenID
    public let accessToken: AccessToken
}

struct UserVerification {
    let userID: UserID
}

struct TemporaryMFA {
    let id: Int
    let createDate: Date
    let userId: UserID
    let secret: String
}

struct AccountRecoveryCode {
    let id: Int
    let createDate: Date
    let updateDate: Date
    let expirationDate: Date
    let email: String
    let code: String
    let recovered: Bool
}

public struct SystemEmail: Equatable {
    public let email: String
    public let name: String
    public let subject: String
    public let body: String
    // Many e-mails provide a code to the user to verify an action. This value will populated in those contexts. It can then be used at test time. It should not be used as a consumer. The `body` of the message must have the `code`.
    @IgnoreEquatable
    public var code: String?
}
