/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

public typealias NotificationID = Int

public struct Notification: Codable, Equatable, Sendable {
    public let id: NotificationID
    // The bundle where the `NotificationController` is located
    public let bundleId: BundleID
    // Name of BOSS `NotificationController`
    public let controllerName: String
    // Location where user is redirected to when the notification is tapped
    public let deepLink: String
    // The title of the notification.
    // This will most likely be used only by generic BOSS notifications. App notifications should set the title themselves.
    public let title: String?
    // Data the controller uses to display custom messages. This could contain anything from a user's name, e-mail, an ID of a record, etc. The respective controller uses this to interpolate values in its message. e.g. Imagine if the metadata was `{email: "test@bithead.io"}`, and the Friends subsystem sent the message. The notification may say something like "You received a friend request from test.io.bithead!" When the user taps the notification, they will be redirected to the Settings > Friends page (the deep link informs BOSS where to redirect).
    public let metadata: [String: String]
    // The user the notification is sent to
    public let userId: UserID
    // Indicates that notification has been seen by user
    public let seen: Bool
}
