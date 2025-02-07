/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation


struct Account: Codable {
    enum Tier: Codable {
        // Restricted to N features - determined by server
        case free
        case personal
        case business
        // Unrestricted
        case enterprise
        // Unrestricted. Provided to @ys developers and external devs that provide value.
        case developer
    }
    struct Stats: Codable {
        // Number of objects currently created within account
        let numObjects: Int
        // Total allowed objects allowed for account tier
        let maxObjects: Int
    }

    var tier: Account.Tier?
    let stats: Account.Stats
    var isYearly: Bool
    let isActive: Bool
    let nextPaymentDate: String?
}

extension Account.Tier {
    var toString: String {
        switch self {
        case .business:
            return "Business"
        case .developer:
            return "Developer"
        case .enterprise:
            return "Enterprise";
        case .free:
            return "Free"
        case .personal:
            return "Personal"
        }
    }
}
