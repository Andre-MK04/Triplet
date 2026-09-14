import XCTest
@testable import Farelin

final class AppConfigurationTests: XCTestCase {
    func testProductionRejectsStagingHost() {
        XCTAssertThrowsError(
            try AppConfiguration(
                environmentValue: "production",
                apiBaseURLValue: "https://farelin-api-staging-staging.up.railway.app"
            )
        ) { error in
            XCTAssertEqual(error as? ConfigurationError, .environmentHostMismatch)
        }
    }

    func testStagingRejectsProductionHost() {
        XCTAssertThrowsError(
            try AppConfiguration(
                environmentValue: "staging",
                apiBaseURLValue: "https://www.farelin.com/backend"
            )
        ) { error in
            XCTAssertEqual(error as? ConfigurationError, .environmentHostMismatch)
        }
    }

    func testConfigurationRequiresHTTPS() {
        XCTAssertThrowsError(
            try AppConfiguration(
                environmentValue: "staging",
                apiBaseURLValue: "http://farelin-api-staging-staging.up.railway.app"
            )
        ) { error in
            XCTAssertEqual(error as? ConfigurationError, .insecureAPIURL)
        }
    }
}
