/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

enum service {
    nonisolated(unsafe) static var node = NodeService()
    nonisolated(unsafe) static var user = UserService()
    nonisolated(unsafe) static var test = TestService()

    enum error {
        struct InvalidSchemaID: BOSSError {
            let type: Any.Type
            init<T>(_ type: T.Type) {
                self.type = type
            }

            var description: String {
                "Invalid schema ID for (\(String(describing: type)))"
            }
        }

        struct FailedToSave: BOSSError {
            let type: Any.Type
            init<T>(_ type: T.Type) {
                self.type = type
            }

            var description: String {
                "Failed to save record type (\(String(describing: type)))"
            }
        }
        
        struct DatabaseFailure: BOSSError {
            let message: String
            init(_ message: String) {
                self.message = message
            }
            
            var description: String {
                message
            }
        }
        
        struct InvalidInput: BOSSError {
            let message: String
            init(_ message: String) {
                self.message = message
            }
            
            var description: String {
                message
            }
        }

        final class CorruptData: BOSSError { }
        final class RecordNotFound: BOSSError { }
        final class TransactionNotStarted: BOSSError { }
    }
}
