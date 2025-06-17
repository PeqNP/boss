/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

@testable import bosslib

class FakeSignerProvider: SignerProvider {
    var _sign: (bosslib.BOSSJWT) throws -> String = { _ in fatalError("SignerProvider.sign") }
    var _verify: (String) throws -> bosslib.BOSSJWT = { _ in fatalError("SignerProvider.verify") }
    
    func sign(_ jwt: bosslib.BOSSJWT) throws -> String {
        try _sign(jwt)
    }
    
    func verify(_ token: String) throws -> bosslib.BOSSJWT {
        try _verify(token)
    }
}
