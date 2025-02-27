/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

enum service {
    nonisolated(unsafe) static var node = NodeService()
    nonisolated(unsafe) static var user = UserService()
    nonisolated(unsafe) static var test = TestService()

    enum error {
        final class InvalidSchemaID: AutoError {
            let type: Any.Type
            init<T>(_ type: T.Type) {
                self.type = type
            }

            override var description: String {
                "Invalid schema ID for (\(String(describing: type)))"
            }
        }

        final class FailedToSave: AutoError {
            let type: Any.Type
            init<T>(_ type: T.Type) {
                self.type = type
            }

            override var description: String {
                "Failed to save record type (\(String(describing: type)))"
            }
        }

        final class DatabaseFailure: AutoError { }
        final class CorruptData: AutoError { }
        final class RecordNotFound: AutoError { }
        final class TransactionNotStarted: AutoError { }
        final class InvalidInput: AutoError { }
    }
}
