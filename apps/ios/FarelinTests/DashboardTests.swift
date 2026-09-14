import XCTest
@testable import Farelin

@MainActor
final class DashboardTests: XCTestCase {
    func testDashboardPayloadDecodesBackendShape() throws {
        let data = Data(Self.dashboardJSON.utf8)

        let dashboard = try JSONDecoder().decode(DashboardResponse.self, from: data)

        XCTAssertEqual(dashboard.user.email, "traveler@example.com")
        XCTAssertEqual(dashboard.billing.plan, "free")
        XCTAssertEqual(dashboard.usage.aiSearchesPerMonth, 3)
        XCTAssertEqual(dashboard.savedSearches.first?.originAirports, ["LJU", "VIE"])
        XCTAssertEqual(dashboard.savedSearchSummary.active, 1)
    }

    func testDashboardStoreLoadsOnceUntilForced() async {
        let service = FakeDashboardService(response: .fixture)
        let store = DashboardStore(service: service)

        await store.load()
        await store.load()

        let initialRequestCount = await service.requestCount()
        XCTAssertEqual(store.dashboard?.billing.plan, "free")
        XCTAssertEqual(initialRequestCount, 1)

        await store.load(force: true)

        let forcedRequestCount = await service.requestCount()
        XCTAssertEqual(forcedRequestCount, 2)
    }

    func testDashboardStoreSurfacesFailureAndStopsLoading() async {
        let store = DashboardStore(service: FakeDashboardService(error: APIError.unavailable))

        await store.load()

        XCTAssertNil(store.dashboard)
        XCTAssertFalse(store.isLoading)
        XCTAssertEqual(
            store.errorMessage,
            "Farelin could not be reached. Check your connection and try again."
        )
    }

    private static let dashboardJSON = """
    {
      "user": {
        "id": "user-1",
        "email": "traveler@example.com",
        "displayName": "Traveler",
        "isVerified": true,
        "createdAt": "2026-09-11T12:00:00",
        "hasPassword": true,
        "connectedProviders": []
      },
      "billing": {
        "plan": "free",
        "subscriptionStatus": "none",
        "trialDaysRemaining": 0,
        "limits": {},
        "usage": {
          "aiSearchesThisMonth": 1,
          "aiSearchesPerMonth": 3,
          "activeSavedSearches": 1,
          "savedSearchLimit": 1,
          "maxOriginAirports": 3,
          "dailyWatchChecks": false,
          "unlimited": false
        },
        "canStartTrial": true,
        "canUpgrade": true,
        "canManageBilling": false
      },
      "usage": {
        "aiSearchesThisMonth": 1,
        "aiSearchesPerMonth": 3,
        "activeSavedSearches": 1,
        "savedSearchLimit": 1,
        "maxOriginAirports": 3,
        "dailyWatchChecks": false,
        "unlimited": false
      },
      "savedSearches": [{
        "id": "watch-1",
        "email": "traveler@example.com",
        "name": "Nordic weekends",
        "originAirports": ["LJU", "VIE"],
        "destinationAirports": ["CPH"],
        "startDate": "2026-10-01",
        "endDate": "2026-12-01",
        "minTripLengthDays": 3,
        "maxTripLengthDays": 5,
        "maxBudget": 180.0,
        "maxGroundTransferHours": 2.0,
        "tripStyle": "return",
        "frequency": "weekly",
        "isActive": true,
        "createdAt": "2026-09-14T10:00:00"
      }],
      "savedSearchSummary": {"total": 1, "active": 1}
    }
    """
}

private actor FakeDashboardService: DashboardServicing {
    private let response: DashboardResponse?
    private let error: Error?
    private var requests = 0

    init(response: DashboardResponse? = nil, error: Error? = nil) {
        self.response = response
        self.error = error
    }

    func dashboard() async throws -> DashboardResponse {
        requests += 1
        if let error { throw error }
        guard let response else { throw APIError.invalidResponse }
        return response
    }

    func requestCount() -> Int { requests }
}

private extension DashboardResponse {
    static let fixture = DashboardResponse(
        user: AuthUser(
            id: "user-1",
            email: "traveler@example.com",
            displayName: "Traveler",
            isVerified: true,
            createdAt: "2026-09-11T12:00:00",
            hasPassword: true,
            connectedProviders: []
        ),
        billing: DashboardBilling(
            plan: "free",
            subscriptionStatus: "none",
            trialDaysRemaining: 0,
            usage: .fixture,
            canStartTrial: true,
            canUpgrade: true,
            canManageBilling: false
        ),
        usage: .fixture,
        savedSearches: [],
        savedSearchSummary: SavedSearchSummary(total: 0, active: 0)
    )
}

private extension DashboardUsage {
    static let fixture = DashboardUsage(
        aiSearchesThisMonth: 0,
        aiSearchesPerMonth: 3,
        activeSavedSearches: 0,
        savedSearchLimit: 1,
        maxOriginAirports: 3,
        dailyWatchChecks: false,
        unlimited: false
    )
}
