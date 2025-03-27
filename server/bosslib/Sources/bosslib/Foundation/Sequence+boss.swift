/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

extension Sequence {
    /// Asynchronsly map values.
    ///
    /// - Parameter transform: The transform that can be async throws
    /// - Returns: List of transformed values
    /// - Note: Provide way to map values where transformation requires async throws
    func asyncMap<T>(_ transform: (Element) async throws -> T) async throws -> [T] {
        var results: [T] = []
        for item in self {
            let result = try await transform(item)
            results.append(result)
        }
        return results
    }
}
