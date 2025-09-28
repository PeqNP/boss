/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

import Foundation

extension Array {
    public subscript(safe index: Int, default defaultValue: @autoclosure () -> Element) -> Element {
        guard index >= 0, index < endIndex else {
            return defaultValue()
        }

        return self[index]
    }
    
    public subscript(safe index: Int) -> Element? {
        guard index >= 0, index < endIndex else {
            return nil
        }
        
        return self[index]
    }
    
    public mutating func safeRemoveFirst() -> Element? {
        if isEmpty {
            return nil
        }
        return removeFirst()
    }
}
