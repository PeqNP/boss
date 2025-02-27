/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

public extension api.error {
    final class FailedToCreateJWT: AutoError { }
    final class FailedToSendVerificationCode: AutoError { }
    final class FailedToVerifyAccountCode: AutoError { }
    final class InvalidJWT: AutoError { }
    final class InvalidNode: AutoError { }
    final class InvalidSlackCode: AutoError { }
    final class InvalidVerificationCode: AutoError { }
    final class NodeNotFound: AutoError { }
    final class UserNotFound: AutoError { }
    final class UserIsNotVerified: AutoError { }
    final class UserIsVerified: AutoError { }

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
