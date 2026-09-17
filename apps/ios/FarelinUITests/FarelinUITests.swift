import XCTest

@MainActor
final class FarelinUITests: XCTestCase {
    // Visibility checks request accessibility snapshots. Exit bounded scroll
    // loops once visible: `for ... where` still checks every remaining iteration.
    func testLongAdvancedResultsNeverLeaveBlankViewport() {
        let app = XCUIApplication()
        app.launchArguments = ["-ui-testing", "-ui-testing-discover", "-ui-testing-results", "-ui-testing-dark"]
        app.launch()
        app.buttons["Use my defaults"].tap()
        for round in 0..<3 {
            let search = app.buttons["advanced-search"]
            for _ in 0..<6 {
                if search.isHittable { break }
                app.swipeUp()
            }
            XCTAssertTrue(search.isHittable)
            search.tap()
            let edit = app.buttons["discover-edit-search"]
            XCTAssertTrue(edit.waitForExistence(timeout: 5))
            let shot = XCTAttachment(screenshot: app.screenshot())
            shot.name = "Long advanced results round \(round)"
            shot.lifetime = .keepAlways
            add(shot)
            XCTAssertTrue(edit.isHittable, "A long result list must start on its header, not an empty scroll offset")
            app.swipeUp()
            let cardShot = XCTAttachment(screenshot: app.screenshot())
            cardShot.name = "Trip card action layout"
            cardShot.lifetime = .keepAlways
            add(cardShot)
            app.swipeDown()
            for _ in 0..<3 {
                if edit.isHittable { break }
                app.swipeDown()
            }
            edit.tap()
        }
    }

    func testExploreResultsFocusAndEditKeepsBudget() {
        let app = XCUIApplication()
        app.launchArguments = ["-ui-testing", "-ui-testing-discover"]
        app.launch()
        completeExplore(app)
        let budget = app.staticTexts["explore-budget-value"]
        let search = app.buttons["Find trips"]
        for _ in 0..<5 {
            if search.isHittable { break }
            app.swipeUp()
        }
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
        XCTAssertEqual(budget.label, "Up to €200")
        XCTAssertFalse(edit.exists)
    }

    func testEmptyExploreCanReviewWiderDatesWithoutAnotherSearch() {
        let app = XCUIApplication()
        app.launchArguments = ["-ui-testing", "-ui-testing-discover"]
        app.launch()
        completeExplore(app)
        let search = app.buttons["Find trips"]
        for _ in 0..<5 {
            if search.isHittable { break }
            app.swipeUp()
        }
        search.tap()
        let widen = app.buttons["Review 30 more days"]
        XCTAssertTrue(widen.waitForExistence(timeout: 5))
        widen.tap()
        XCTAssertTrue(app.staticTexts["explore-budget-value"].waitForExistence(timeout: 3))
        XCTAssertEqual(app.staticTexts["explore-budget-value"].label, "Up to €200")
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

    func testSuggestedPromptsHaveEqualWidths() {
        let app = XCUIApplication()
        app.launchArguments = ["-ui-testing", "-ui-testing-discover"]
        app.launch()
        app.buttons["Ask Farelin"].tap()
        let first = app.buttons["prompt-example-0"]
        XCTAssertTrue(first.waitForExistence(timeout: 3))
        for index in 1...2 {
            let next = app.buttons["prompt-example-\(index)"]
            XCTAssertEqual(first.frame.width, next.frame.width, accuracy: 1)
            XCTAssertEqual(first.frame.height, next.frame.height, accuracy: 1)
        }
    }

    func testPriceActionFitsWithAccessibilityText() {
        let app = XCUIApplication()
        app.launchArguments = ["-ui-testing", "-ui-testing-discover", "-ui-testing-results", "-ui-testing-dark", "-ui-testing-large-text"]
        app.launch()
        tapVisible("Use my defaults", in: app)
        tapVisible("advanced-search", in: app)
        XCTAssertTrue(app.buttons["discover-edit-search"].waitForExistence(timeout: 5))
        let price = app.descendants(matching: .any).matching(identifier: "trip-check-price").firstMatch
        for _ in 0..<8 {
            if price.isHittable { break }
            app.swipeUp()
        }
        XCTAssertTrue(price.isHittable)
        XCTAssertLessThanOrEqual(price.frame.maxX, app.frame.width - 20)
        XCTAssertLessThan(price.frame.height, 90, "The action should remain a single line at larger text sizes")
        let shot = XCTAttachment(screenshot: app.screenshot())
        shot.name = "Accessible price action"
        shot.lifetime = .keepAlways
        add(shot)
    }

    private func tapVisible(_ title: String, in app: XCUIApplication) {
        let button = app.buttons[title]
        for _ in 0..<6 {
            if button.isHittable { break }
            app.swipeUp()
        }
        XCTAssertTrue(button.isHittable, title)
        button.tap()
    }

    private func completeExplore(_ app: XCUIApplication) {
        XCTAssertTrue(app.buttons["Next 3 months"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.sliders["explore-budget-slider"].exists)
        app.buttons["Next 3 months"].tap()
        XCTAssertTrue(app.sliders["explore-budget-slider"].exists)
        XCTAssertFalse(app.sliders["explore-duration-slider"].exists)
        tapVisible("Use this budget", in: app)
        XCTAssertTrue(app.sliders["explore-duration-slider"].exists)
        tapVisible("Use this length", in: app)
        tapVisible("Use profile mood", in: app)
        tapVisible("trip-shape-return", in: app)
    }

    func testFlexibleBudgetAndSlidersAreProgressive() {
        let app = XCUIApplication()
        app.launchArguments = ["-ui-testing", "-ui-testing-discover"]
        app.launch()
        app.buttons["Next 3 months"].tap()
        let slider = app.sliders["explore-budget-slider"]
        XCTAssertTrue(slider.waitForExistence(timeout: 3))
        slider.adjust(toNormalizedSliderPosition: 1)
        XCTAssertEqual(app.staticTexts["explore-budget-value"].label, "Up to €1500")
        tapVisible("explore-flexible-budget", in: app)
        XCTAssertEqual(app.staticTexts["explore-budget-value"].label, "Flexible")
        let duration = app.sliders["explore-duration-slider"]
        for _ in 0..<4 {
            if duration.isHittable && duration.frame.maxY <= app.frame.height - 180 { break }
            app.swipeUp()
        }
        XCTAssertTrue(duration.isHittable)
        XCTAssertLessThan(duration.frame.maxY, app.frame.height - 160, "Move the slider above the floating tab bar before dragging")
        duration.adjust(toNormalizedSliderPosition: 1)
        XCTAssertEqual(app.staticTexts["explore-duration-value"].label, "30 nights")
        tapVisible("Use this length", in: app)
        tapVisible("Use profile mood", in: app)
        tapVisible("trip-shape-return", in: app)
        XCTAssertTrue(app.buttons["advanced-search"].exists)
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = "Progressive Explore sliders"
        screenshot.lifetime = .keepAlways
        add(screenshot)
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
