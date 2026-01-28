/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Vapor

/// Register the `/friend/` routes.
public func registerFriend(_ app: Application) {
    app.group("friend") { group in
        group.get { req in
            return try await makeFriends(for: req.authUser)
        }.openAPI(
            summary: "Get all friends, friend requests, and pending requests",
            response: .type(Fragment.Friends.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
        
        group.post("add") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(FriendForm.AddFriend.self)
            let (_, recipient) = try await api.friend.addFriend(user: authUser.user, email: form.email)
            
            // If user exists, send them notification and event
            if let userId = recipient?.id {
                let notifications: [bosslib.Notification] = [
                    try await api.notification.saveNotification(
                        bundleId: "io.bithead.boss",
                        controllerName: "Notification",
                        deepLink: "settings://friends/pending-requests",
                        title: "New friend request",
                        body: "\(authUser.user.fullName) has sent you a friend request.",
                        metadata: nil,
                        userId: userId,
                        persist: false
                    )
                ]
                await ConnectionManager.shared.sendNotifications(notifications)
                
                // Update friend's list
                let events: [bosslib.NotificationEvent] = [
                    .init(name: "io.bithead.boss.friends.refresh", userId: userId, data: [:])
                ]
                await ConnectionManager.shared.sendEvents(events)
            }
            
            return try await makeFriends(for: authUser)
        }.openAPI(
            summary: "Add a new friend",
            body: .type(FriendForm.AddFriend.self),
            contentType: .application(.json),
            response: .type(Fragment.Friends.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
        
        group.post("remove") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(FriendForm.RemoveFriend.self)
            let friend = try await api.friend.removeFriend(user: authUser.user, id: form.id)
            
            // Update friend's list
            let events: [bosslib.NotificationEvent] = [
                .init(name: "io.bithead.boss.friends.refresh", userId: friend.id, data: [:])
            ]
            await ConnectionManager.shared.sendEvents(events)
            
            return try await makeFriends(for: authUser)
        }.openAPI(
            summary: "Remove a friend",
            body: .type(FriendForm.RemoveFriend.self),
            contentType: .application(.json),
            response: .type(Fragment.Friends.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
        
        group.post("accept") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(FriendForm.AcceptFriendRequest.self)
            let friend = try await api.friend.acceptFriendRequest(user: authUser.user, id: form.id)
            
            // Let the initiator know the user accepted their request
            let notifications: [bosslib.Notification] = [
                try await api.notification.saveNotification(
                    bundleId: "io.bithead.boss",
                    controllerName: "Notification",
                    deepLink: "settings://friends",
                    title: "Accepted request",
                    body: "\(authUser.user.fullName) has accepted your friend request.",
                    metadata: nil,
                    userId: friend.id,
                    persist: false
                )
            ]
            await ConnectionManager.shared.sendNotifications(notifications)
            
            // Update friend's list
            let events: [bosslib.NotificationEvent] = [
                .init(name: "io.bithead.boss.friends.refresh", userId: friend.id, data: [:])
            ]
            await ConnectionManager.shared.sendEvents(events)
            
            return try await makeFriends(for: authUser)
        }.openAPI(
            summary: "Accept a friend request",
            body: .type(FriendForm.AcceptFriendRequest.self),
            contentType: .application(.json),
            response: .type(Fragment.Friends.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
        
        group.post("reject") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(FriendForm.RejectFriendRequest.self)
            try await api.friend.removeFriendRequest(user: authUser.user, id: form.id)
            return try await makeFriends(for: authUser)
        }.openAPI(
            summary: "Reject friend request",
            body: .type(FriendForm.RejectFriendRequest.self),
            contentType: .application(.json),
            response: .type(Fragment.Friends.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
    }
}

private func makeFriends(for authUser: AuthenticatedUser) async throws -> Fragment.Friends {
    let friends = try await api.friend.friends(user: authUser.user)
    let requests = try await api.friend.friendRequests(user: authUser.user)
    return .init(
        friendRequests: requests
            .filter { $0.userId != authUser.user.id }
            .map { $0.makeFriendRequestOption() },
        yourRequests: requests
            .filter { $0.userId == authUser.user.id }
            .map { $0.makeMyFriendRequestOption() },
        friends: friends
            .map { $0.makeFriendOption() }
    )
}
