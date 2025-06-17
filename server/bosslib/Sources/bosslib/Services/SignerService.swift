/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.
/// https://jwt.io/ - Verify JWTs

import JWTKit

extension api {
    public nonisolated(unsafe) internal(set) static var signer: SignerProvider = _JWTSigner()
}

public protocol SignerProvider {
    func sign(_ jwt: BOSSJWT) throws -> String
    func verify(_ token: String) throws -> BOSSJWT
}

class _JWTSigner: SignerProvider {
    private let signer = JWTSigner.hs256(key: boss.config.hmacKey)
    
    func sign(_ jwt: BOSSJWT) throws -> String {
        try signer.sign(jwt)
    }
    
    func verify(_ token: String) throws -> BOSSJWT {
        try signer.verify(token, as: BOSSJWT.self)
    }
}
