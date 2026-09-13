import XCTest

final class FarelinUITests: XCTestCase {
    func testFoundationScreenLaunches() {
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.staticTexts["FARELIN"].waitForExistence(timeout: 5))
    }
}

