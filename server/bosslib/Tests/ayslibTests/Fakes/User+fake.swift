/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

@testable import bosslib

extension User {
    static func fake(
        id: UserID = 3, // A non-admin/guest account
        system: AccountSystem = .boss,
        fullName: String = "",
        email: String = "",
        password: String = "",
        verified: Bool = false,
        enabled: Bool = false,
        mfaEnabled: Bool = false,
        totpSecret: String? = nil
    ) -> User {
        .init(
            id: id,
            system: system,
            fullName: fullName,
            email: email,
            password: password,
            verified: verified,
            enabled: enabled,
            mfaEnabled: mfaEnabled,
            totpSecret: totpSecret
        )
    }
}
