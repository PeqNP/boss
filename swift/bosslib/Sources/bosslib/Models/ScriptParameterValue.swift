/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

public struct ScriptParameterValue: Equatable, Codable {
    public enum `Type`: Equatable, Codable {
        /// This will eventually contain a keystore which allows a user to extract user/pass from an account. A new feature will need to be added to store these user/pass values.
        // case keystore
        case string(String)
        case int(Int)
        case boolean(Bool)
        case double(Double)

        public var toString: String {
            switch self {
            case .boolean(let value):
                return value ? "true" : "false"
            case .int(let value):
                return String(value)
            case .string(let value):
                return value
            case .double(let value):
                return String(value)
            }
        }

        public static let `default`: ScriptParameterValue.`Type` = .string("UNKNOWN")
    }

    public static func makeEmpty() -> Self {
        .init(type: .default)
    }

    public static func make(from parameter: Script.Parameter) -> Self {
        switch parameter.type {
        case .boolean:
            return .init(id: parameter.id, type: .boolean(false))
        case .double:
            return .init(id: parameter.id, type: .double(0))
        case .int:
            return .init(id: parameter.id, type: .int(0))
        case .string:
            return .init(id: parameter.id, type: .string(""))
        }
    }

    public var id: String?
    public var type: ScriptParameterValue.`Type`
}
