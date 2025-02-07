/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

@testable import ayslib

extension AuthenticatedUser {
    static func fake(
        user: User = .fake(id: 3),
        peer: String = ""
    ) -> AuthenticatedUser {
        .init(
            user: user,
            peer: peer
        )
    }
}
