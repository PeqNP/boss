/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import JWTKit

public struct BOSSJWT: Equatable, Sendable {
    public var id: String
    public var issuedAt: Date
    public var subject: String
    public var expiration: Date
    public var apps: [ACLID]
    public var acl: [ACLID]
    
    struct ACLAppsClaim: JWTClaim, Equatable {
        var value: [ACLID]
    }
    
    struct ACLClaim: JWTClaim, Equatable {
        var value: [ACLID]
    }
    
    /// This is an intermediary structure to allow `BOSSJWT` to be `Sendable`. The `JWTKit` types `IDClaim`, `IssuedAtClaim`, etc. are not `Sendable`.
    struct JWT: JWTPayload, Equatable {
        enum CodingKeys: String, CodingKey {
            /// TokenID
            case id = "id"
            case issuedAt = "iat"
            /// User.id
            case subject = "sub"
            case expiration = "exp"
            // List of app IDs the user has access to
            case apps = "apps"
            // List of user ACLs
            case acl = "acl"
        }

        public var id: IDClaim
        public var issuedAt: IssuedAtClaim
        public var subject: SubjectClaim
        public var expiration: ExpirationClaim
        public var apps: ACLAppsClaim
        public var acl: ACLClaim
        
        public func verify(using signer: JWTKit.JWTSigner) throws {
            try expiration.verifyNotExpired()
        }
    }
    
    func make() -> JWT {
        JWT(
            id: IDClaim(value: id),
            issuedAt: IssuedAtClaim(value: issuedAt),
            subject: SubjectClaim(value: subject),
            expiration: ExpirationClaim(value: expiration),
            apps: ACLAppsClaim(value: apps),
            acl: ACLClaim(value: acl)
        )
    }
}
