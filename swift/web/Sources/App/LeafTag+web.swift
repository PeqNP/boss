/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation
import Leaf

/// - Returns: String `"null"` if value is `nil`.
/// - Note: Used when interpolating form values to a Javascript `null` value if respetive value is `nil`.
struct NullTag: LeafTag {
    func render(_ ctx: LeafKit.LeafContext) throws -> LeafData {
        guard let value = ctx.parameters.first?.string else {
            return .string("null")
        }
        return .string(value)
    }
}

/// - Returns: `true` when value is `nil`. `false`, otherwise.
struct IsNilTag: LeafTag {
    func render(_ ctx: LeafKit.LeafContext) throws -> LeafData {
        guard let isNil = ctx.parameters.first?.isNil else {
            return .bool(true)
        }
        return .bool(isNil)
    }
}

struct JSONObjectTag: UnsafeUnescapedLeafTag {
    func render(_ ctx: LeafKit.LeafContext) throws -> LeafKit.LeafData {
        guard let data = ctx.parameters.first?.dictionary else {
            return .string("null")
        }
        var dict = [String: String]()
        for (key, value) in data {
            dict[key] = value.short
        }
        let jsonData = try JSONEncoder().encode(dict)
        let jsonString = String(data: jsonData, encoding: .utf8)
        return .string(jsonString)
    }
}
