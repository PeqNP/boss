/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

@testable import ayslib

extension User {
    static func fake(
        id: UserID = 3, // A non-admin/guest account
        system: AccountSystem = .ays,
        fullName: String = "",
        email: String = "",
        password: String = "",
        verified: Bool = false,
        enabled: Bool = false,
        homeNodeID: NodeID? = nil
    ) -> User {
        .init(
            id: id,
            system: system,
            fullName: fullName,
            email: email,
            password: password,
            verified: verified,
            enabled: enabled,
            homeNodeID: homeNodeID
        )
    }
}
