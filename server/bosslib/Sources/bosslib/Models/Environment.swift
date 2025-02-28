/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

import Foundation

public enum Environment {
    case dev
    case prod
}

extension Environment {
    var toString: String {
        switch self {
        case .dev:
            return "Development"
        case .prod:
            return "Production"
        }
    }
}
