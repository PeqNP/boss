/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import Foundation
internal import SQLiteKit

struct LeanService: LeanProvider {
    func createLine(session: Database.Session, user: User, factoryId: Factory.ID, name: String?) async throws -> Line {
        guard let name = name, !name.trimmingCharacters(in: .whitespaces).isEmpty else {
            throw api.error.RequiredParameter("name")
        }
        fatalError("not implemented")
    }
}
