/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

extension api {
    public nonisolated(unsafe) internal(set) static var health = HealthAPI()
}

public class HealthAPI {
    var _stageNodeHealth: (Database.Session, Node) async throws -> Void

    init() {
        self._stageNodeHealth = bosslib.stageNodeHealth
    }

    func stageNodeHealth(
        session: Database.Session = Database.session(),
        _ node: Node
    ) async throws {
        try await _stageNodeHealth(session, node)
    }

    func stageNodeSensor(_ node: Node) {

    }
}

private func stageNodeHealth(session: Database.Session, node: Node) async throws {

}
