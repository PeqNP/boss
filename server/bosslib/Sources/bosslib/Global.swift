/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

public enum Global {
    public static let auth0Url = "https://bithead.us.auth0.com/api/v2/"
    public static let phoneNumber = "+1 (253) 329-1280"

    /// Refer to `v1.swift` for users added to the `ays` database when the system first initializes
    static let superUserId: UserID = 1
    static let guestUserId: UserID = 2
}
