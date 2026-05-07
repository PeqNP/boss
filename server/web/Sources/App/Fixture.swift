/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

#if DEBUG
import bosslib
import Foundation
import Vapor

/// Load a fixture JSON file and decode it into the inferred type.
///
/// Fixture files live in `server/web/Fixtures/` and are never packaged into
/// production builds (this function is compiled only when `DEBUG` is defined).
///
/// - Parameter path: Path relative to the package root, e.g. `"Fixtures/lean/factory-floor.json"`
/// - Returns: The decoded value.
func loadFixture<T: Decodable>(_ path: String) throws -> T {
    boss.log.i("Loading fixture @ (\(path))")
    let rootURL = URL(fileURLWithPath: DirectoryConfiguration.detect().workingDirectory)
    let fileURL = rootURL.appendingPathComponent(path)
    let data = try Data(contentsOf: fileURL)
    let decoder = JSONDecoder()
    return try decoder.decode(T.self, from: data)
}
#endif
