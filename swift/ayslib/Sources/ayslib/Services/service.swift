/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

enum service {
    static var node = NodeService()
    static var user = UserService()
    static var test = TestService()

    typealias Error = ays.Error

    enum error {
        class InvalidSchemaID: service.Error {
            let type: Any.Type
            init<T>(_ type: T.Type) {
                self.type = type
            }

            override var description: String {
                "Invalid schema ID for (\(String(describing: type)))"
            }
        }

        class FailedToSave: service.Error {
            let type: Any.Type
            init<T>(_ type: T.Type) {
                self.type = type
            }

            override var description: String {
                "Failed to save record type (\(String(describing: type)))"
            }
        }

        class DatabaseFailure: service.Error { }
        class CorruptData: service.Error { }
        class RecordNotFound: service.Error { }
        class TransactionNotStarted: service.Error { }
        class InvalidInput: service.Error { }
    }
}
