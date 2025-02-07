/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

public struct OrgConfig {
    public struct SlackConfig {
        public let teamId: String?
        public let teamName: String?
    }

    public var alertTypes: [AlertType]
    public var mediaHttpPath: String
    public let supportedLanguages: [Script.Language]
    public let slack: SlackConfig?
    public var dataRetentionInDays: Int
    public let authProvider: OrgAuthProvider
    public let secret: String?
}

public extension OrgConfig {
    static var empty: OrgConfig {
        .init(
            alertTypes: [],
            mediaHttpPath: "",
            supportedLanguages: [],
            slack: nil,
            dataRetentionInDays: 0,
            authProvider: .default,
            secret: nil
        )
    }
}

extension OrgConfig {
    static var defaultConfig: OrgConfig {
        .init(
            alertTypes: [
                .init(name: "Debug", level: .debug),
                .init(name: "Info", level: .info),
                .init(name: "Warning", level: .warning),
                .init(name: "Error", level: .error),
                .init(name: "Critical", level: .critical)
            ],
            mediaHttpPath: "",
            supportedLanguages: [.python],
            slack: nil,
            dataRetentionInDays: 30,
            authProvider: .ays,
            secret: nil
        )
    }

}

public enum OrgAuthProvider {
    public struct Auth0Config {
        let url: String
    }

    case auth0(Auth0Config)
    case ays

    public static var `default`: OrgAuthProvider {
        .ays
    }
}

public extension OrgAuthProvider {
    var toString: String {
        switch self {
        case .auth0:
            return "Auth0"
        case .ays:
            return "ays"
        }
    }
}
