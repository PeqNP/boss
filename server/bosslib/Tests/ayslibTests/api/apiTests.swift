/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation
import XCTest

@testable import bosslib

final class apiTests: XCTestCase {
    override func setUpWithError() throws {
        try super.setUpWithError()
        api.reset()
    }
    
    func testVersion() throws {
        let version = try api.version()
        boss.log.i("bosslib version (\(version))")
        XCTAssertNotEqual(version, "unknown")
        XCTAssertFalse(version.contains("fatal"))
    }

    func testConfig() async throws {
        try await boss.start(storage: .memory)
        XCTAssertNotEqual(boss.config.hmacKey, "")
    }
}
