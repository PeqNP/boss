/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import JWTKit

public struct BOSSJWT: JWTPayload, Equatable {
    enum CodingKeys: String, CodingKey {
        /// TokenID
        case id = "id"
        case issuedAt = "iat"
        /// User.id
        case subject = "sub"
        case expiration = "exp"
    }

    public var id: IDClaim
    public var issuedAt: IssuedAtClaim
    public var subject: SubjectClaim
    public var expiration: ExpirationClaim

    public func verify(using signer: JWTKit.JWTSigner) throws {
        try self.expiration.verifyNotExpired()
    }
}
