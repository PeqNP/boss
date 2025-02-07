/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import XCTest

func XCTAssertError<T, E: Error & Equatable>(
    _ expression: @autoclosure () async throws -> T,
    _ inError: E,
    _ message: @autoclosure () -> String = "",
    file: StaticString = #filePath,
    line: UInt = #line
) async {
    do {
        _ = try await expression()
        XCTFail("Expected to throw error (\(inError))", file: file, line: line)
    }
    catch {
        guard let error = error as? E else {
            return XCTFail("Error (\(error)) is not an instance of (\(inError))", file: file, line: line)
        }
        XCTAssertEqual(inError, error, file: file, line: line)
    }
}

func XCTThrowsError<T, E: Error & Equatable>(
    _ expression: @autoclosure () throws -> T,
    _ inError: E,
    _ message: @autoclosure () -> String = "",
    file: StaticString = #filePath,
    line: UInt = #line
) {
    do {
        _ = try expression()
        XCTFail("Expected to throw error (\(inError))", file: file, line: line)
    }
    catch {
        guard let error = error as? E else {
            return XCTFail("Error (\(error)) is not an instance of (\(inError))", file: file, line: line)
        }
        XCTAssertEqual(inError, error, file: file, line: line)
    }
}
