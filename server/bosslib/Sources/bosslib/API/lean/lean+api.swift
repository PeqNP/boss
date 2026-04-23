/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import Foundation

extension api {
    public nonisolated(unsafe) internal(set) static var lean = LeanAPI(provider: LeanService())
}

protocol LeanProvider {
    func createLine(session: Database.Session, user: User, factoryId: Factory.ID, name: String?) async throws -> Line
}

final public class LeanAPI {
    let p: LeanProvider
    
    init(provider: LeanProvider) {
        self.p = provider
    }

    @discardableResult
    public func createLine(
        session: Database.Session = Database.session(),
        user: User,
        factoryId: Factory.ID,
        name: String?
    ) async throws -> Line {
        try await p.createLine(session: session, user: user, factoryId: factoryId, name: name)
    }
}
