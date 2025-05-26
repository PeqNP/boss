/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

public typealias UserID = Int
public typealias VerificationCode = String

public enum AccountSystem: Int, Equatable, Codable {
    case ays
}

public struct User: Equatable, Codable {
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
    
    public var homeNodeID: NodeID?
    public var avatarUrl: URL?
    public var preferredLanguage: Script.Language?
    public var preferredTheme: String?
    public var preferredFont: String?
}

public struct AuthenticatedUser: Equatable {
    public let user: User
    let peer: String?

    public init(user: User, peer: String?) {
        self.user = user
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
    let orgNodePath: NodePath
}
