/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

import Foundation

public func with<T>(_ item: T, update: (inout T) throws -> Void) rethrows -> T {
    var this = item
    try update(&this)
    return this
}
