/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.
/// https://jwt.io/ - Verify JWTs

import JWTKit

extension api {
    public nonisolated(unsafe) internal(set) static var signer = SignerAPI(p: _JWTSigner())
}

public protocol SignerProvider {
    func sign(_ jwt: BOSSJWT) throws -> String
    func verify(_ token: String) throws -> BOSSJWT
}

final public class SignerAPI {
    private let p: SignerProvider
    
    init(p: SignerProvider) {
        self.p = p
    }
    
    func sign(_ jwt: BOSSJWT) throws -> String {
        try p.sign(jwt)
    }
    
    func verify(_ token: String) throws -> BOSSJWT {
        try p.verify(token)
    }
}

class _JWTSigner: SignerProvider {
    private let signer = JWTSigner.hs256(key: boss.config.hmacKey)
    
    func sign(_ jwt: BOSSJWT) throws -> String {
        try signer.sign(jwt.make())
    }
    
    func verify(_ token: String) throws -> BOSSJWT {
        let jwt = try signer.verify(token, as: BOSSJWT.JWT.self)
        return BOSSJWT(
            id: jwt.id.value,
            issuedAt: jwt.issuedAt.value,
            subject: jwt.subject.value,
            expiration: jwt.expiration.value
        )
    }
}
