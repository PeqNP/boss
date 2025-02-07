/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

public extension api.error {
    class FailedToCreateJWT: api.Error { }
    class FailedToSendVerificationCode: api.Error { }
    class FailedToVerifyAccountCode: api.Error { }
    class InvalidJWT: api.Error { }
    class InvalidNode: api.Error { }
    class InvalidSlackCode: api.Error { }
    class InvalidVerificationCode: api.Error { }
    class NodeNotFound: api.Error { }
    class UserNotFound: api.Error { }
    class UserIsNotVerified: api.Error { }
    class UserIsVerified: api.Error { }

    struct InvalidAccountInfo: AYSError {
        public enum Field: Equatable, CustomStringConvertible {
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
