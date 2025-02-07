/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

import Foundation

extension String {
    var isNumber: Bool {
        return !isEmpty && rangeOfCharacter(from: CharacterSet.decimalDigits.inverted) == nil
    }

    // MARK: Substring

    /// This is adapted from https://stackoverflow.com/a/39742687/455791
    /// Where String is `"Hello,World!"`

    // `.substring(from: 1, to: 7)` -> `ello,Wo`
    func substring(from: Int?, to: Int?) -> String {
        if let start = from {
            guard start < self.count else {
                return ""
            }
        }

        if let end = to {
            guard end >= 0 else {
                return ""
            }
        }

        if let start = from, let end = to {
            guard end - start >= 0 else {
                return ""
            }
        }

        let startIndex: String.Index
        if let start = from, start >= 0 {
            startIndex = self.index(self.startIndex, offsetBy: start)
        } else {
            startIndex = self.startIndex
        }

        let endIndex: String.Index
        if let end = to, end >= 0, end < self.count {
            endIndex = self.index(self.startIndex, offsetBy: end + 1)
        } else {
            endIndex = self.endIndex
        }

        return String(self[startIndex ..< endIndex])
    }

    // `.substring(from: 3)` -> `lo,World!`
    func substring(from: Int) -> String {
        return self.substring(from: from, to: nil)
    }

    // `.substring(to: 7)` -> `Hello,Wo`
    func substring(to: Int) -> String {
        return self.substring(from: nil, to: to)
    }

    // `.substring(from: 1, length: 4)` -> `ello`
    func substring(from: Int?, length: Int) -> String {
        guard length > 0 else {
            return ""
        }

        let end: Int
        if let start = from, start > 0 {
            end = start + length - 1
        } else {
            end = length - 1
        }

        return self.substring(from: from, to: end)
    }

    // `.substring(length: 4, to: 7)` -> `o,Wo`
    func substring(length: Int, to: Int?) -> String {
        guard let end = to, end > 0, length > 0 else {
            return ""
        }

        let start: Int
        if let end = to, end - length > 0 {
            start = end - length + 1
        } else {
            start = 0
        }

        return self.substring(from: start, to: to)
    }
    
    /// Returns a "cleaned" string.
    ///
    /// - Parameter str: The string to strip whitespaces from
    /// - Returns: `nil` if string is `nil` or the string has no characters
    func cleaned() -> String? {
        let cleaned = trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleaned.isEmpty else {
            return nil
        }
        return cleaned
    }
}
