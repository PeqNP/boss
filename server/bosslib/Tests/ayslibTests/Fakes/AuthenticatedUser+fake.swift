/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

@testable import bosslib

extension AuthenticatedUser {
    static func fake(
        user: User = .fake(id: 3),
        session: UserSession = .fake(),
        peer: String = ""
    ) -> AuthenticatedUser {
        .init(
            user: user,
            session: session,
            peer: peer
        )
    }
}
