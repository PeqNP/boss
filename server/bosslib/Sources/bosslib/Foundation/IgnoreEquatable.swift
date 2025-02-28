/// Copyright ⓒ 2023 Bithead LLC. All rights reserved.

import Foundation

@propertyWrapper
public struct IgnoreEquatable<Value: Codable>: Equatable, Codable, CustomStringConvertible {
    public var wrappedValue: Value

    public var description: String {
        String(describing: wrappedValue)
    }
    
    public init(wrappedValue: Value) {
        self.wrappedValue = wrappedValue
    }

    public static func == (lhs: IgnoreEquatable<Value>, rhs: IgnoreEquatable<Value>) -> Bool {
        true
    }
    
    // Required for the value to encode with only the value rather than render
    // as a dictionary value using framework like `Vapor`.
    enum CodingKeys: CodingKey {
        case wrappedValue
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        wrappedValue = try container.decode(Value.self)
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(wrappedValue)
    }
}

@propertyWrapper
public struct IgnoreHashable<Value: Equatable>: Hashable {
    public var wrappedValue: Value

    public init(wrappedValue value: Value) {
        self.wrappedValue = value
    }

    public func hash(into hasher: inout Hasher) { }
}
