/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

public enum Global {
    public static let auth0Url = "https://bithead.us.auth0.com/api/v2/"
    public static let phoneNumber = "+1 (253) 329-1280"
    
    // One half day. This ensures the user is more likely to see the sign in page the next day immediately upon starting work. Rather than being interrupted mid-work.
    public static let sessionTimeoutInSeconds: TimeInterval =  86_400 / 2
    // The maximum amount of time a user may be inactive before their session is automatically expired.
    public static let maxAllowableInactivityInMinutes: Int = 15
    
    public enum otp {
        public static let numDigits: Int = 6
        public static let expiresInSeconds: Int = 30
    }

    /// Refer to `v1_0_0.swift` for users added to the BOSS database when the system first initializes.
    static let superUserId: UserID = 1
    static let guestUserId: UserID = 2
    
    static let accountRecoveryExpirationTimeInSeconds: TimeInterval = 3_600 // One day
}
