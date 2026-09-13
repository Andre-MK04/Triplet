import XCTest
@testable import Farelin

final class PurchaseProviderTests: XCTestCase {
    func testLaunchProviderExposesNoPurchases() async throws {
        let products = try await DisabledPurchaseProvider().products()
        XCTAssertTrue(products.isEmpty)
    }
}

