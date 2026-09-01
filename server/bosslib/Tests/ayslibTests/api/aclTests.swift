/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import Foundation
import XCTest

@testable import bosslib

final class aclTests: XCTestCase {
    /// - Test registering an app's features
    /// - Test verifying access to resources
    func test_acl() async throws {
        try await boss.start(storage: .memory)
        
        let user = try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example.com", password: "Password1!", fullName: "Eric", verified: true, enabled: true)
        var authUser = AuthenticatedUser(user: user, session: .fake(), peer: nil)
        
        // describe: invalid bundle ID
        await XCTAssertError(
            try await api.acl.registerApps([.init(bundleId: " ", features: [])]),
            api.error.InvalidParameter(name: "bundleId")
        )
        // describe: invalid feature
        await XCTAssertError(
            try await api.acl.registerApps([.init(bundleId: "io.bithead", features: ["  "])]),
            api.error.InvalidParameter(name: "feature")
        )
        // describe: invalid feature first part
        await XCTAssertError(
            try await api.acl.registerApps([.init(bundleId: "io.bithead", features: [".r"])]),
            api.error.InvalidParameter(name: "feature", expected: "A feature name must have at least one character")
        )
        // describe: invalid feature second part
        await XCTAssertError(
            try await api.acl.registerApps([.init(bundleId: "io.bithead", features: ["Feature."])]),
            api.error.InvalidParameter(name: "feature", expected: "A permission name must have at least one character")
        )
        // describe: more than one dot is added
        await XCTAssertError(
            try await api.acl.registerApps([.init(bundleId: "io.bithead", features: ["Feature.r.extra"])]),
            api.error.InvalidParameter(name: "feature", expected: "Only one dot is allowed")
        )
        
        var apps: [ACLApp] = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"])
        ]
        var paths = try await api.acl.registerApps(apps)
        var expected: ACLPathMap = [
            "io.bithead.test": 1,
            "io.bithead.test,Test": 2,
            "io.bithead.test,Test,r": 3,
        ]
        XCTAssertEqual(paths, expected)
                
        // describe: user does not have license to use app (yet)
        await XCTAssertError(
            try await api.acl.appLicense(id: 1, user: user),
            service.error.RecordNotFound()
        )
        
        // describe: user requests license for app that does not exist
        await XCTAssertError(
            try await api.acl.appLicense(id: 42, user: user),
            service.error.RecordNotFound()
        )
        
        // describe: invalid bundle ID
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "  ", feature: "")),
            api.error.InvalidParameter(name: "bundleId")
        )
        // describe: invalid feature
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.test", feature: "")),
            api.error.InvalidParameter(name: "feature")
        )
        // describe: invalid feature first part
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.test", feature: ".r")),
            api.error.InvalidParameter(name: "feature", expected: "A feature name must have at least one character")
        )
        // describe: invalid feature second part
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.test", feature: "Feature.")),
            api.error.InvalidParameter(name: "feature", expected: "A permission name must have at least one character")
        )
        // describe: more than one dot is added
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.test", feature: "Feature.r.next")),
            api.error.InvalidParameter(name: "feature", expected: "Only one dot is allowed")
        )
        
        // describe: verify access to app that does not exist
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.fake", feature: nil)),
            api.error.AppDoesNotExist()
        )
        
        // describe: verify user against feature that does not exist
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.test", feature: "Fake.r")),
            api.error.AccessDenied()
        )
        
        // describe: provide license to app
        var expectedLicense = try await api.acl.issueAppLicense(id: 1, to: user)
        var license = try await api.acl.appLicense(id: 1, user: user)
        XCTAssertEqual(license, expectedLicense)
        
        // describe: a role is granted; the user still holds an old token
        //
        // `io.bithead.test` declared no roles, so it has `default`, holding
        // every feature it registered.
        let firstRoles = try await api.acl.roles(bundleId: "io.bithead.test")
        let testDefault = try XCTUnwrap(firstRoles.first { $0.name == "default" }?.id)
        try await api.acl.assignRole(id: testDefault, to: user)
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.test", feature: "Test.r")),
            api.error.AccessDenied()
        )

        // describe: they sign in, and the token carries the role
        authUser = AuthenticatedUser(user: user, session: .fake(jwt: .fake(apps: [1], roles: [testDefault])), peer: nil)
        try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.test", feature: "Test.r"))

        var held: [ACLRoleID] = try await api.acl.userRoles(for: user)
        XCTAssertEqual(held, [testDefault])

        // describe: new app is added
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.w"]),
        ]
        paths = try await api.acl.registerApps(apps)
        expected = [
            "io.bithead.test": 1,
            "io.bithead.test,Test": 2,
            "io.bithead.test,Test,r": 3,
            "io.bithead.boss": 4,
            "io.bithead.boss,Feature": 5,
            "io.bithead.boss,Feature,w": 6,
        ]
        XCTAssertEqual(paths, expected)
        
        // describe: a new feature is added
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.w", "Person.r"]),
        ]
        paths = try await api.acl.registerApps(apps)
        expected = [
            "io.bithead.test": 1,
            "io.bithead.test,Test": 2,
            "io.bithead.test,Test,r": 3,
            "io.bithead.boss": 4,
            "io.bithead.boss,Feature": 5,
            "io.bithead.boss,Feature,w": 6,
            "io.bithead.boss,Person": 7,
            "io.bithead.boss,Person,r": 8,
        ]
        XCTAssertEqual(paths, expected)

        // describe: a new feature permission is added
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.w", "Feature.r", "Person.r"]),
        ]
        paths = try await api.acl.registerApps(apps)
        expected = [
            "io.bithead.test": 1,
            "io.bithead.test,Test": 2,
            "io.bithead.test,Test,r": 3,
            "io.bithead.boss": 4,
            "io.bithead.boss,Feature": 5,
            "io.bithead.boss,Feature,w": 6,
            "io.bithead.boss,Person": 7,
            "io.bithead.boss,Person,r": 8,
            "io.bithead.boss,Feature,r": 9,
        ]
        XCTAssertEqual(paths, expected)
        
        // describe: create hierchical structure of ACL
        let tree = try await api.acl.aclTree()
        // Built in pieces: one literal this deep is more than the type checker
        // will take.
        let bossFeatures: [ACLTree.Feature] = [
            .init(id: 5, name: "Feature",
                  permissions: [.init(id: 9, name: "r"), .init(id: 6, name: "w")]),
            .init(id: 7, name: "Person", permissions: [.init(id: 8, name: "r")])
        ]
        // A role's features carry only the permissions it holds, and no id of
        // their own — the grouping is for reading, not for granting.
        let bossRoles: [ACLTree.Role] = [
            .init(id: 2, name: "default", features: [
                .init(id: 0, name: "Feature",
                      permissions: [.init(id: 9, name: "r"), .init(id: 6, name: "w")]),
                .init(id: 0, name: "Person", permissions: [.init(id: 8, name: "r")])
            ])
        ]
        let testFeatures: [ACLTree.Feature] = [
            .init(id: 2, name: "Test", permissions: [.init(id: 3, name: "r")])
        ]
        let testRoles: [ACLTree.Role] = [
            .init(id: 1, name: "default", features: [
                .init(id: 0, name: "Test", permissions: [.init(id: 3, name: "r")])
            ])
        ]
        let expectedApps: [ACLTree.App] = [
            .init(id: 4, name: "io.bithead.boss", features: bossFeatures, roles: bossRoles),
            .init(id: 1, name: "io.bithead.test", features: testFeatures, roles: testRoles)
        ]
        let expectedTree = ACLTree(apps: expectedApps)
        // it: should create a sorted tree structure
        XCTAssertEqual(tree, expectedTree)
        
        // describe: duplicate feature permission added
        let duplicateFeatures: [ACLApp] = [
            .init(bundleId: "io.bithead.test", features: ["Test.r", "Test.r"]), // <- Duplicate is here
            .init(bundleId: "io.bithead.boss", features: ["Feature.w", "Feature.r", "Person.r"]),
        ]
        paths = try await api.acl.registerApps(duplicateFeatures)
        // it: should not contain duplicate feature
        XCTAssertEqual(paths, expected) // Uses same `expected` as previous test
        
        // describe: a feature permission is removed
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.r", "Person.r"]),
        ]
        paths = try await api.acl.registerApps(apps)
        expected = [
            "io.bithead.test": 1,
            "io.bithead.test,Test": 2,
            "io.bithead.test,Test,r": 3,
            "io.bithead.boss": 4,
            "io.bithead.boss,Feature": 5,
            "io.bithead.boss,Person": 7,
            "io.bithead.boss,Person,r": 8,
            "io.bithead.boss,Feature,r": 9,
        ]
        XCTAssertEqual(paths, expected)
        
        // describe: a feature is removed
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Person.r"]),
        ]
        paths = try await api.acl.registerApps(apps)
        expected = [
            "io.bithead.test": 1,
            "io.bithead.test,Test": 2,
            "io.bithead.test,Test,r": 3,
            "io.bithead.boss": 4,
            "io.bithead.boss,Person": 7,
            "io.bithead.boss,Person,r": 8,
        ]
        XCTAssertEqual(paths, expected)
        
        // describe: an app is absent from the registration
        apps = [
            .init(bundleId: "io.bithead.boss", features: ["Person.r"]),
        ]
        paths = try await api.acl.registerApps(apps)
        // it: returns what this registration carried
        expected = [
            "io.bithead.boss": 4,
            "io.bithead.boss,Person": 7,
            "io.bithead.boss,Person,r": 8,
        ]
        XCTAssertEqual(paths, expected)
        // it: leaves the absent app where it was — a registration speaks only
        // for the apps it carries, and an app that failed to load carries none
        XCTAssertEqual(api.acl.aclPaths()["io.bithead.test"], 1)
        XCTAssertEqual(api.acl.aclPaths()["io.bithead.test,Test,r"], 3)
        
        // describe: the license a second app needs
        let declaredForBoss = try await api.acl.roles(bundleId: "io.bithead.boss")
        let bossRole = try XCTUnwrap(declaredForBoss.first { $0.name == "default" }?.id)
        try await api.acl.assignRole(id: bossRole, to: user)
        
        // describe: check if user has access to app
        expectedLicense = try await api.acl.issueAppLicense(id: 4, to: user)
        license = try await api.acl.appLicense(id: 4, user: user)
        XCTAssertEqual(license, expectedLicense)
        
        // describe: revoke app license
        try await api.acl.revokeAppLicense(id: 4, from: user)
        // it: should not return a license
        await XCTAssertError(
            try await api.acl.appLicense(id: 4, user: user),
            service.error.RecordNotFound()
        )
        
        // describe: re-issue license
        expectedLicense = try await api.acl.issueAppLicense(id: 4, to: user)
        license = try await api.acl.appLicense(id: 4, user: user)
        XCTAssertEqual(license, expectedLicense)
        
        // describe: they sign in again, holding the second app's role
        authUser = AuthenticatedUser(user: user, session: .fake(jwt: .fake(apps: [4], roles: [bossRole])), peer: nil)
        try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.boss", feature: "Person.r"))
        
        // it: a license for one app is not a license for another
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.test", feature: "Test.r")),
            api.error.AccessDenied()
        )
    }
    
    func test_registerAcl() async throws {
        try await boss.start(storage: .memory)
        
        // describe: send large set of features; one duplicate feature (ExecuteTestRun)
        var apps: [ACLApp] = [
            .init(bundleId: "io.bithead.test-manager", features: ["Project.w", "Project.r", "TestRun.r", "TestSuite.w", "TestSuiteEditor", "ExecuteTestRun", "ExecuteTestRun", "TestRun.w", "TestSuite.r"]),
        ]
        var paths = try await api.acl.registerApps(apps)
        var expected: ACLPathMap = [
            "io.bithead.test-manager": 1,
            "io.bithead.test-manager,ExecuteTestRun": 2,
            "io.bithead.test-manager,Project": 3,
            "io.bithead.test-manager,Project,r": 4,
            "io.bithead.test-manager,Project,w": 5,
            "io.bithead.test-manager,TestRun": 6,
            "io.bithead.test-manager,TestRun,r": 7,
            "io.bithead.test-manager,TestRun,w": 8,
            "io.bithead.test-manager,TestSuite": 9,
            "io.bithead.test-manager,TestSuite,r": 10,
            "io.bithead.test-manager,TestSuite,w": 11,
            "io.bithead.test-manager,TestSuiteEditor": 12,
        ]
        XCTAssertEqual(paths, expected)

        // describe: register the same values again
        apps = [
            .init(bundleId: "io.bithead.test-manager", features: ["Project.w", "Project.r", "TestRun.r", "TestSuite.w", "TestSuiteEditor", "ExecuteTestRun", "ExecuteTestRun", "TestRun.w", "TestSuite.r"]),
        ]
        // it: should return the same config
        paths = try await api.acl.registerApps(apps)
        expected = [
            "io.bithead.test-manager": 1,
            "io.bithead.test-manager,ExecuteTestRun": 2,
            "io.bithead.test-manager,Project": 3,
            "io.bithead.test-manager,Project,r": 4,
            "io.bithead.test-manager,Project,w": 5,
            "io.bithead.test-manager,TestRun": 6,
            "io.bithead.test-manager,TestRun,r": 7,
            "io.bithead.test-manager,TestRun,w": 8,
            "io.bithead.test-manager,TestSuite": 9,
            "io.bithead.test-manager,TestSuite,r": 10,
            "io.bithead.test-manager,TestSuite,w": 11,
            "io.bithead.test-manager,TestSuiteEditor": 12,
        ]
        XCTAssertEqual(paths, expected)
        
        // describe: a registration carrying no apps
        apps = []
        paths = try await api.acl.registerApps(apps)
        // it: speaks for nothing, so it returns nothing
        XCTAssertEqual(paths, [:])
        
        // it: and leaves what is registered where it was
        expected = [
            "io.bithead.test-manager": 1,
            "io.bithead.test-manager,ExecuteTestRun": 2,
            "io.bithead.test-manager,Project": 3,
            "io.bithead.test-manager,Project,r": 4,
            "io.bithead.test-manager,Project,w": 5,
            "io.bithead.test-manager,TestRun": 6,
            "io.bithead.test-manager,TestRun,r": 7,
            "io.bithead.test-manager,TestRun,w": 8,
            "io.bithead.test-manager,TestSuite": 9,
            "io.bithead.test-manager,TestSuite,r": 10,
            "io.bithead.test-manager,TestSuite,w": 11,
            "io.bithead.test-manager,TestSuiteEditor": 12,
        ]
        XCTAssertEqual(api.acl.aclPaths(), expected)
    }

    /// An app absent from a registration has said nothing about itself.
    ///
    /// Most often it failed to load: `api.py` logs the failure and carries on,
    /// so the app never calls `register_acl` and never reaches the payload.
    /// Reading that as "this app has nothing" retires everything it owns.
    func test_keepUnregisteredAcl() async throws {
        try await boss.start(storage: .memory)

        let user = try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example.com", password: "Password1!", fullName: "Eric", verified: true, enabled: true)

        var apps: [ACLApp] = [
            .init(bundleId: "io.bithead.one", features: ["Job.r"]),
            .init(bundleId: "io.bithead.two", features: ["Word.r"])
        ]
        let registered = try await api.acl.registerApps(apps)

        let twoApp = try XCTUnwrap(registered["io.bithead.two"])
        let twoRead = try XCTUnwrap(registered["io.bithead.two,Word,r"])
        try await api.acl.issueAppLicense(id: twoApp, to: user)
        let twoRoles = try await api.acl.roles(bundleId: "io.bithead.two")
        let twoDefault = try XCTUnwrap(twoRoles.first { $0.name == "default" }?.id)
        try await api.acl.assignRole(id: twoDefault, to: user)

        // describe: the second app fails to load, so only the first registers
        apps = [.init(bundleId: "io.bithead.one", features: ["Job.r"])]
        _ = try await api.acl.registerApps(apps)

        let paths = api.acl.aclPaths()
        XCTAssertEqual(paths["io.bithead.two"], twoApp, "it: leaves the absent app where it was")
        XCTAssertEqual(paths["io.bithead.two,Word,r"], twoRead, "it: keeps its features, with their ids")

        let held: [ACLRoleID] = try await api.acl.userRoles(for: user)
        XCTAssertTrue(held.contains(twoDefault), "it: keeps the grant")

        let licensed: [ACLID] = try await api.acl.userApps(for: user)
        XCTAssertTrue(licensed.contains(twoApp), "it: keeps the license")
    }

    /// A name the payload stops carrying is retired rather than destroyed.
    func test_retireAcl() async throws {
        try await boss.start(storage: .memory)

        let user = try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example.com", password: "Password1!", fullName: "Eric", verified: true, enabled: true)

        var apps: [ACLApp] = [
            .init(bundleId: "io.bithead.one", features: ["Job.r", "Job.w"],
                  roles: ["Operator": ["Job.r", "Job.w"]])
        ]
        let paths = try await api.acl.registerApps(apps)

        let app = try XCTUnwrap(paths["io.bithead.one"])
        let write = try XCTUnwrap(paths["io.bithead.one,Job,w"])
        try await api.acl.issueAppLicense(id: app, to: user)
        let roles = try await api.acl.roles(bundleId: "io.bithead.one")
        let operatorRole = try XCTUnwrap(roles.first { $0.name == "Operator" }?.id)
        try await api.acl.assignRole(id: operatorRole, to: user)

        var authUser = AuthenticatedUser(user: user, session: .fake(jwt: .fake(apps: [app], roles: [operatorRole])), peer: nil)
        try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.one", feature: "Job.w"))

        // describe: the route naming `Job.w` is retagged, so nothing registers it
        apps = [.init(bundleId: "io.bithead.one", features: ["Job.r"],
                      roles: ["Operator": ["Job.r"]])]
        _ = try await api.acl.registerApps(apps)

        XCTAssertNil(api.acl.aclPaths()["io.bithead.one,Job,w"],
                     "it: stops answering for a name nothing registers")
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.one", feature: "Job.w")),
            api.error.AccessDenied()
        )

        let held: [ACLRoleID] = try await api.acl.userRoles(for: user)
        XCTAssertTrue(held.contains(operatorRole),
                      "it: keeps the grant, which is what makes this recoverable")

        // describe: the name comes back
        apps = [.init(bundleId: "io.bithead.one", features: ["Job.r", "Job.w"],
                      roles: ["Operator": ["Job.r", "Job.w"]])]
        let returned = try await api.acl.registerApps(apps)

        XCTAssertEqual(returned["io.bithead.one,Job,w"], write,
                       "it: is the same record, so every issued token still names it")
        try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.one", feature: "Job.w"))
    }

    /// Destroying grants is something somebody asks for.
    func test_pruneAcl() async throws {
        try await boss.start(storage: .memory)

        let user = try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example.com", password: "Password1!", fullName: "Eric", verified: true, enabled: true)

        var apps: [ACLApp] = [
            .init(bundleId: "io.bithead.one", features: ["Job.r", "Job.w"],
                  roles: ["Operator": ["Job.r", "Job.w"]])
        ]
        let paths = try await api.acl.registerApps(apps)
        let write = try XCTUnwrap(paths["io.bithead.one,Job,w"])
        let roles = try await api.acl.roles(bundleId: "io.bithead.one")
        let operatorRole = try XCTUnwrap(roles.first { $0.name == "Operator" }?.id)
        try await api.acl.assignRole(id: operatorRole, to: user)

        apps = [.init(bundleId: "io.bithead.one", features: ["Job.r"],
                      roles: ["Operator": ["Job.r"]])]
        _ = try await api.acl.registerApps(apps)

        // describe: what is waiting to go, before anything goes
        let retired = try await api.acl.retiredAcl()
        XCTAssertEqual(retired.map { $0.id }, [write], "it: names what pruning would take")

        let removed = try await api.acl.pruneAcl()
        XCTAssertEqual(removed, 1)

        let held = try await api.acl.roleFeatures(id: operatorRole)
        XCTAssertEqual(held, ["Job.r"],
                       "it: takes the role's link with it, having been asked to")

        // describe: the name comes back after pruning
        apps = [.init(bundleId: "io.bithead.one", features: ["Job.r", "Job.w"],
                      roles: ["Operator": ["Job.r", "Job.w"]])]
        let returned = try await api.acl.registerApps(apps)
        XCTAssertNotNil(returned["io.bithead.one,Job,w"], "it: registers again")

        let stillHeld = try await api.acl.userRoles(for: user)
        XCTAssertEqual(stillHeld, [operatorRole],
                       "it: the role survives — what was pruned is what it held")

        // SQLite hands a freed rowid to the next insert, so a pruned ACL's ID
        // can be issued again to something else. A token minted before the
        // prune and naming the old ID would match the new record, until the
        // holder signs in again. One more reason pruning is asked for rather
        // than reached by a deploy.
    }

    /// Pruning, when the role that held the permission is retired too.
    ///
    /// Registration rebuilds what a role holds, but only for roles the payload
    /// still names — a retired role keeps its links untouched. So a retired
    /// role is the one case where pruning can leave a link pointing at a row
    /// that no longer exists.
    func test_pruneAclClearsRetiredRoleLinks() async throws {
        try await boss.start(storage: .memory)

        var apps: [ACLApp] = [
            .init(bundleId: "io.bithead.one", features: ["Job.r", "Job.w"],
                  roles: ["Operator": ["Job.r", "Job.w"]])
        ]
        let paths = try await api.acl.registerApps(apps)
        let write = try XCTUnwrap(paths["io.bithead.one,Job,w"])
        let roles = try await api.acl.roles(bundleId: "io.bithead.one")
        let operatorRole = try XCTUnwrap(roles.first { $0.name == "Operator" }?.id)

        // The role goes away along with the permission, so nothing rebuilds
        // what it held.
        apps = [.init(bundleId: "io.bithead.one", features: ["Job.r"],
                      roles: ["Employee": ["Job.r"]])]
        _ = try await api.acl.registerApps(apps)
        let orphaned = try await api.acl.rolePermissionCount(aclId: write)
        XCTAssertEqual(orphaned, 1,
                       "it: a retired role holds on to what it was given")

        let removed = try await api.acl.pruneAcl()
        XCTAssertEqual(removed, 1)

        // it: leaves no link behind pointing at a row that is gone. SQLite
        // hands a freed rowid to the next insert, and a role still holding the
        // old one would come to hold whatever takes its place.
        let remaining = try await api.acl.rolePermissionCount(aclId: write)
        XCTAssertEqual(remaining, 0)
    }

    /// The migration, against a database that already exists.
    ///
    /// `.memory` builds every version in one pass, so it says nothing about a
    /// database sitting at an earlier version with rows in it — which is every
    /// database that is not brand new.
    func test_migrateAcl() async throws {
        let directory = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("acl-migration-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let path = directory.appendingPathComponent("boss.sqlite3")

        // A database as it stands before this migration: through 1.2.0, with an
        // ACL somebody holds.
        try await Database.start(storage: .file(path))
        var apps: [ACLApp] = [.init(bundleId: "io.bithead.one", features: ["Job.r"])]
        let paths = try await api.acl.registerApps(apps)
        let read = try XCTUnwrap(paths["io.bithead.one,Job,r"])

        // describe: the database is opened again by a later start
        try await Database.start(storage: .file(path))

        // it: keeps what it held
        let again = try await api.acl.registerApps(apps)
        XCTAssertEqual(again["io.bithead.one,Job,r"], read,
                       "it: is the same record across a restart")

        // it: retires rather than deletes, on a database that was already there
        apps = [.init(bundleId: "io.bithead.one", features: [])]
        _ = try await api.acl.registerApps(apps)
        let retired = try await api.acl.retiredAcl()
        XCTAssertTrue(retired.contains { $0.id == read },
                      "it: the column the migration added is being written")
    }

    /// An app's roles, and the features each one holds.
    func test_registerRole() async throws {
        try await boss.start(storage: .memory)

        let apps: [ACLApp] = [
            .init(bundleId: "io.bithead.one",
                  features: ["Job.r", "Job.w"],
                  roles: ["Operator": ["Job.r", "Job.w"], "Employee": ["Job.r"]])
        ]
        _ = try await api.acl.registerApps(apps)

        let roles = try await api.acl.roles(bundleId: "io.bithead.one")
        XCTAssertEqual(roles.map { $0.name }.sorted(), ["Employee", "Operator"])

        let operatorRole = try XCTUnwrap(roles.first { $0.name == "Operator" })
        let employeeRole = try XCTUnwrap(roles.first { $0.name == "Employee" })
        let operatorHolds = try await api.acl.roleFeatures(id: operatorRole.id).sorted()
        XCTAssertEqual(operatorHolds, ["Job.r", "Job.w"])
        let employeeHolds = try await api.acl.roleFeatures(id: employeeRole.id)
        XCTAssertEqual(employeeHolds, ["Job.r"], "it: holds only what named it")
    }

    /// An app with no roles of its own.
    func test_defaultRole() async throws {
        try await boss.start(storage: .memory)

        let apps: [ACLApp] = [
            .init(bundleId: "io.bithead.one", features: ["Job.r", "Job.w"])
        ]
        _ = try await api.acl.registerApps(apps)

        let roles = try await api.acl.roles(bundleId: "io.bithead.one")
        XCTAssertEqual(roles.map { $0.name }, ["default"],
                       "it: has one, so an app works before it declares any")
        let holds = try await api.acl.roleFeatures(id: roles[0].id).sorted()
        XCTAssertEqual(holds, ["Job.r", "Job.w"], "it: holds every feature the app has")
    }

    /// A role keeps its ID while its features move underneath it.
    func test_retireRole() async throws {
        try await boss.start(storage: .memory)

        var apps: [ACLApp] = [
            .init(bundleId: "io.bithead.one",
                  features: ["Job.r", "Job.w"],
                  roles: ["Operator": ["Job.r", "Job.w"], "Employee": ["Job.r"]])
        ]
        _ = try await api.acl.registerApps(apps)
        let before = try await api.acl.roles(bundleId: "io.bithead.one")
        let operatorId = try XCTUnwrap(before.first { $0.name == "Operator" }?.id)

        // describe: a route stops naming Employee, and Operator gains nothing
        apps = [
            .init(bundleId: "io.bithead.one",
                  features: ["Job.r", "Job.w"],
                  roles: ["Operator": ["Job.r", "Job.w"]])
        ]
        _ = try await api.acl.registerApps(apps)

        let after = try await api.acl.roles(bundleId: "io.bithead.one")
        XCTAssertEqual(after.map { $0.name }, ["Operator"],
                       "it: stops answering for a role nothing names")
        XCTAssertEqual(after[0].id, operatorId,
                       "it: keeps the ID of the one that stayed")

        // describe: the role comes back
        apps = [
            .init(bundleId: "io.bithead.one",
                  features: ["Job.r", "Job.w"],
                  roles: ["Operator": ["Job.r", "Job.w"], "Employee": ["Job.r"]])
        ]
        _ = try await api.acl.registerApps(apps)

        let revived = try await api.acl.roles(bundleId: "io.bithead.one")
        XCTAssertEqual(revived.map { $0.name }.sorted(), ["Employee", "Operator"],
                       "it: is the same record, so a grant of it still holds")
    }

    /// Granting a role, and reaching a route through it.
    func test_grantRole() async throws {
        try await boss.start(storage: .memory)

        let user = try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example.com", password: "Password1!", fullName: "Eric", verified: true, enabled: true)

        let apps: [ACLApp] = [
            .init(bundleId: "io.bithead.one",
                  features: ["Job.r", "Job.w"],
                  roles: ["Operator": ["Job.r", "Job.w"], "Employee": ["Job.r"]])
        ]
        let paths = try await api.acl.registerApps(apps)
        let app = try XCTUnwrap(paths["io.bithead.one"])
        try await api.acl.issueAppLicense(id: app, to: user)

        let roles = try await api.acl.roles(bundleId: "io.bithead.one")
        let employee = try XCTUnwrap(roles.first { $0.name == "Employee" }?.id)

        try await api.acl.assignRole(id: employee, to: user)
        let held = try await api.acl.userRoles(for: user)
        XCTAssertEqual(held, [employee])

        // describe: the user signs in holding the role
        let authUser = AuthenticatedUser(
            user: user,
            session: .fake(jwt: .fake(apps: [app], roles: [employee])),
            peer: nil
        )
        try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.one", feature: "Job.r"))

        // describe: a permission the role does not hold
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.one", feature: "Job.w")),
            api.error.AccessDenied()
        )

        // describe: the role is taken away
        try await api.acl.removeRole(id: employee, from: user)
        let after = try await api.acl.userRoles(for: user)
        XCTAssertEqual(after, [], "it: holds nothing once the role is gone")
    }

    /// A route moving between roles reaches the holder without a new token.
    func test_retagRoute() async throws {
        try await boss.start(storage: .memory)

        let user = try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example.com", password: "Password1!", fullName: "Eric", verified: true, enabled: true)

        var apps: [ACLApp] = [
            .init(bundleId: "io.bithead.one",
                  features: ["Job.r", "Job.w"],
                  roles: ["Operator": ["Job.r", "Job.w"], "Employee": ["Job.r"]])
        ]
        let paths = try await api.acl.registerApps(apps)
        let app = try XCTUnwrap(paths["io.bithead.one"])
        try await api.acl.issueAppLicense(id: app, to: user)

        let roles = try await api.acl.roles(bundleId: "io.bithead.one")
        let employee = try XCTUnwrap(roles.first { $0.name == "Employee" }?.id)
        try await api.acl.assignRole(id: employee, to: user)

        let authUser = AuthenticatedUser(
            user: user,
            session: .fake(jwt: .fake(apps: [app], roles: [employee])),
            peer: nil
        )
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.one", feature: "Job.w")),
            api.error.AccessDenied()
        )

        // describe: `Job.w` is retagged to reach Employee too
        apps = [
            .init(bundleId: "io.bithead.one",
                  features: ["Job.r", "Job.w"],
                  roles: ["Operator": ["Job.r", "Job.w"], "Employee": ["Job.r", "Job.w"]])
        ]
        _ = try await api.acl.registerApps(apps)

        // it: reaches it on the same token — the grant names the role, and what
        // the role holds is resolved at the request
        try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.one", feature: "Job.w"))
    }

    /// The tree Settings draws, which grants a role rather than a permission.
    func test_aclTreeRoles() async throws {
        try await boss.start(storage: .memory)

        let apps: [ACLApp] = [
            .init(bundleId: "io.bithead.one",
                  features: ["Job.r", "Job.w"],
                  roles: ["Operator": ["Job.r", "Job.w"], "Employee": ["Job.r"]])
        ]
        _ = try await api.acl.registerApps(apps)

        let tree = try await api.acl.aclTree()
        let app = try XCTUnwrap(tree.apps.first { $0.name == "io.bithead.one" })

        XCTAssertEqual(app.roles.map { $0.name }.sorted(), ["Employee", "Operator"],
                       "it: names the roles a user may be given")

        // it: groups what it holds by feature, which is how Settings lists it —
        // one bullet a feature, its permissions after the colon
        let employee = try XCTUnwrap(app.roles.first { $0.name == "Employee" })
        XCTAssertEqual(employee.features.map { $0.name }, ["Job"])
        XCTAssertEqual(employee.features[0].permissions.map { $0.name }, ["r"])

        let operatorRole = try XCTUnwrap(app.roles.first { $0.name == "Operator" })
        XCTAssertEqual(operatorRole.features.map { $0.name }, ["Job"])
        XCTAssertEqual(operatorRole.features[0].permissions.map { $0.name },
                       ["r", "w"])

        // describe: an app that declared no roles
        _ = try await api.acl.registerApps(apps + [.init(bundleId: "io.bithead.two", features: ["Word.r"])])
        let after = try await api.acl.aclTree()
        let two = try XCTUnwrap(after.apps.first { $0.name == "io.bithead.two" })
        XCTAssertEqual(two.roles.map { $0.name }, ["default"],
                       "it: has the one BOSS supplies, holding every feature")
        XCTAssertEqual(two.roles[0].features.map { $0.name }, ["Word"])
    }

    /// A role holding a feature reaches the permissions beneath it.
    func test_widenToFeature() async throws {
        try await boss.start(storage: .memory)

        let user = try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example.com", password: "Password1!", fullName: "Eric", verified: true, enabled: true)

        // `TestSuiteEditor` is registered without a dot, so the role holds the
        // feature itself and the walk widens to it.
        let apps: [ACLApp] = [
            .init(bundleId: "io.bithead.wide", features: ["TestSuiteEditor"],
                  roles: ["Editor": ["TestSuiteEditor"]])
        ]
        let paths = try await api.acl.registerApps(apps)
        let app = try XCTUnwrap(paths["io.bithead.wide"])
        try await api.acl.issueAppLicense(id: app, to: user)

        let roles = try await api.acl.roles(bundleId: "io.bithead.wide")
        let editor = try XCTUnwrap(roles.first { $0.name == "Editor" }?.id)
        try await api.acl.assignRole(id: editor, to: user)

        let authUser = AuthenticatedUser(
            user: user, session: .fake(jwt: .fake(apps: [app], roles: [editor])), peer: nil)
        try await api.acl.verifyAccess(for: authUser, to: .init(bundleId: "io.bithead.wide", feature: "TestSuiteEditor.r"))

        // describe: taking the role away
        try await api.acl.removeRole(id: editor, from: user)
        let held = try await api.acl.userRoles(for: user)
        XCTAssertEqual(held, [])
    }
}
