/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import Foundation
import SwiftOTP
import XCTest

@testable import bosslib

final class leanTests: XCTestCase {
    /// Test saving the `Line` model.
    func testLine() async throws {
        try await boss.start(storage: .memory)

        // describe: Create a new Line with only the name

        // when: name is nil
        await XCTAssertError(
            try await api.lean.createLine(user: superUser().user, factoryId: 1, name: nil),
            api.error.RequiredParameter("name")
        )

        // when: name is empty
        await XCTAssertError(
            try await api.lean.createLine(user: superUser().user, factoryId: 1, name: ""),
            api.error.RequiredParameter("name")
        )
    }
}
