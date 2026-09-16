import XCTest

@MainActor
final class FarelinUITests: XCTestCase {
    func testExploreResultsFocusAndEditKeepsBudget() {
        let app = XCUIApplication()
        app.launchArguments = ["-ui-testing", "-ui-testing-discover"]
        app.launch()
        let budget = app.buttons["€400"]
        XCTAssertTrue(budget.waitForExistence(timeout: 5))
        budget.tap()
        let search = app.buttons["Find trips"]
        for _ in 0..<5 where !search.isHittable { app.swipeUp() }
        XCTAssertTrue(search.isHittable)
        search.tap()
        let edit = app.buttons["discover-edit-search"]
        XCTAssertTrue(edit.waitForExistence(timeout: 5))
        XCTAssertTrue(edit.isHittable, "Completed results should be visible without scrolling back through the form")
        XCTAssertFalse(app.staticTexts["THE ESSENTIALS"].exists)
        let resultScreenshot = XCTAttachment(screenshot: app.screenshot())
        resultScreenshot.name = "Discover results and recovery"
        resultScreenshot.lifetime = .keepAlways
        add(resultScreenshot)
        edit.tap()
        XCTAssertTrue(budget.waitForExistence(timeout: 3))
        XCTAssertTrue(budget.isSelected)
        XCTAssertFalse(edit.exists)
    }

    func testEmptyExploreCanReviewWiderDatesWithoutAnotherSearch() {
        let app = XCUIApplication()
        app.launchArguments = ["-ui-testing", "-ui-testing-discover"]
        app.launch()
        XCTAssertTrue(app.buttons["Next 3 months"].waitForExistence(timeout: 5))
        app.buttons["Next 3 months"].tap()
        app.buttons["€200"].tap()
        let search = app.buttons["Find trips"]
        for _ in 0..<5 where !search.isHittable { app.swipeUp() }
        search.tap()
        let widen = app.buttons["Review 30 more days"]
        XCTAssertTrue(widen.waitForExistence(timeout: 5))
        widen.tap()
        XCTAssertTrue(app.buttons["€200"].waitForExistence(timeout: 3))
        XCTAssertTrue(app.buttons["€200"].isSelected)
        XCTAssertFalse(app.buttons["Next 3 months"].isSelected)
        XCTAssertFalse(app.staticTexts["No observed fares found"].exists,
                       "Review should return to the draft, not perform another search")
    }

    func testFoundationScreenLaunches() {
        let app = XCUIApplication()
        app.launchArguments = ["-ui-testing"]
        app.launch()
        XCTAssertTrue(app.staticTexts["FARELIN"].waitForExistence(timeout: 5))
    }

    func testCreateAccountTapExplainsMissingPassword() {
        let app = XCUIApplication()
        app.launchArguments = ["-ui-testing"]
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
