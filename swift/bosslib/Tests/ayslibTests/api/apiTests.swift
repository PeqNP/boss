/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation
import XCTest

@testable import ayslib

final class apiTests: XCTestCase {
    override func setUpWithError() throws {
        try super.setUpWithError()
        api.reset()
    }
    
    func testVersion() throws {
        let version = try api.version()
        log.i("ayslib version (\(version))")
        XCTAssertNotEqual(version, "unknown")
        XCTAssertFalse(version.contains("fatal"))
    }

    func testConfig() async throws {
        try await ays.start(storage: .memory)
        XCTAssertNotEqual(ays.config.hmacKey, "")
    }
}
