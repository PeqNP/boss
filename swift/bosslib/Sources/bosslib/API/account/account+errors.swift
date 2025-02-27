/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

public extension api.error {
    final class FailedToCreateJWT: BOSSError { }
    final class FailedToSendVerificationCode: BOSSError { }
    final class FailedToVerifyAccountCode: BOSSError { }
    final class InvalidJWT: BOSSError { }
    final class InvalidSlackCode: BOSSError { }
    final class InvalidVerificationCode: BOSSError { }
    final class NodeNotFound: BOSSError { }
    final class UserNotFound: BOSSError { }
    final class UserIsNotVerified: BOSSError { }
    final class UserIsVerified: BOSSError { }
    
    struct InvalidNode: BOSSError {
        let message: String
        
        public var description: String {
            message
        }
        
        init(_ message: String) {
            self.message = message
        }
    }

    struct InvalidAccountInfo: BOSSError {
        public enum Field: Equatable, CustomStringConvertible, Sendable {
            case email
            case fullName
            case orgPath
            case password

            public var description: String {
                switch self {
                case .email:
                    "Email"
                case .fullName:
                    "Full name"
                case .orgPath:
                    "Organization path"
                case .password:
                    "Password"
                }
            }
        }

        public let field: Field

        public init(field: Field) {
            self.field = field
        }

        public var description: String {
            "Please provide a value for field (\(field))."
        }
    }
}
