import XCTest

@MainActor
final class FarelinUITests: XCTestCase {
    func testFoundationScreenLaunches() {
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.staticTexts["FARELIN"].waitForExistence(timeout: 5))
    }

    func testCreateAccountTapExplainsMissingPassword() {
        let app = XCUIApplication()
        app.launch()

        let createAccountTab = app.buttons["Create account"].firstMatch
        XCTAssertTrue(createAccountTab.waitForExistence(timeout: 5))
        createAccountTab.tap()

        let email = app.textFields["auth-email"]
        XCTAssertTrue(email.waitForExistence(timeout: 2))
        email.tap()
        email.typeText("traveler@example.com")

        app.switches["auth-legal-toggle"].tap()
        app.buttons["auth-submit"].tap()

        XCTAssertTrue(app.staticTexts["auth-form-message"].waitForExistence(timeout: 2))
        XCTAssertEqual(app.staticTexts["auth-form-message"].label, "Enter your password.")
    }
}
