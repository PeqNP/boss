/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import Foundation

extension api {
    public nonisolated(unsafe) internal(set) static var lean = LeanAPI(provider: LeanService())
}

protocol LeanProvider {
}

final public class LeanAPI {
    let p: LeanProvider
    
    init(provider: LeanProvider) {
        self.p = provider
    }
}
