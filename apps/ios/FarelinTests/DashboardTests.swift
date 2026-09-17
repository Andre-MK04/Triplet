import XCTest
@testable import Farelin

@MainActor
final class DashboardTests: XCTestCase {
    private var today: Date { Date(timeIntervalSince1970: 1_789_646_400) } // 17 September 2026 UTC

    private func summary(id: String = "watch", active: Bool = true, end: String = "2026-12-01",
                         checked: String? = nil, notified: String? = nil) -> SavedWatchSummary {
        SavedWatchSummary(id: id, name: "Nordic weekends", originAirports: ["CPH"],
            destinationAirports: ["ARN"], startDate: "2026-10-01", endDate: end,
            maxBudget: 200, frequency: "weekly", isActive: active, lastCheckedAt: checked,
            lastNotifiedAt: notified, lastBestPrice: nil)
    }

    func testEmptyTodayInvitesDiscoveryWithoutClaimingMonitoring() {
        let overview = TodayWatchOverview(watches: [], now: today)
        XCTAssertEqual(overview.monitoringCount, 0)
        XCTAssertTrue(overview.message.contains("Find a trip"))
    }

    func testPausedTodayDoesNotClaimActiveChecks() {
        let watch = summary(active: false)
        let overview = TodayWatchOverview(watches: [watch], now: today)
        XCTAssertEqual(overview.state(of: watch), .paused)
        XCTAssertEqual(overview.monitoringCount, 0)
        XCTAssertTrue(overview.message.contains("No watches are checking"))
    }

    func testExpiredActiveWatchIsNotMonitoring() {
        let watch = summary(end: "2026-09-01")
        let overview = TodayWatchOverview(watches: [watch], now: today)
        XCTAssertEqual(overview.state(of: watch), .expired)
        XCTAssertEqual(overview.monitoringCount, 0)
        XCTAssertTrue(overview.message.contains("windows have ended"))
    }

    func testWatchRemainsCurrentThroughEndDate() {
        let watch = summary(end: "2026-09-17")
        let overview = TodayWatchOverview(watches: [watch], now: today.addingTimeInterval(3600 * 11))
        XCTAssertEqual(overview.state(of: watch), .waiting)
        XCTAssertEqual(overview.monitoringCount, 1)
    }

    func testTodayPrioritizesObservedWatchesThenWaitingPausedExpired() {
        let watches = [summary(id: "expired", end: "2020-01-01"), summary(id: "paused", active: false),
                       summary(id: "waiting"), summary(id: "observed", checked: "2026-09-15T12:00:00Z")]
        let overview = TodayWatchOverview(watches: watches, now: today)
        XCTAssertEqual(overview.orderedWatches.map(\.id), ["observed", "waiting", "paused", "expired"])
        XCTAssertEqual(overview.monitoringCount, 2)
    }

    func testRecentRecordedNotificationSortsBeforeOlderNotification() {
        let watches = [summary(id: "old", checked: "2026-09-15", notified: "2026-09-14T12:00:00Z"),
                       summary(id: "new", checked: "2026-09-15", notified: "2026-09-16T12:00:00Z")]
        XCTAssertEqual(TodayWatchOverview(watches: watches, now: today).orderedWatches.first?.id, "new")
    }

    func testNaiveUTCNotificationTimestampsKeepWithinDayOrdering() {
        let watches = [summary(id: "a-old", checked: "2026-09-15", notified: "2026-09-16T09:00:00.123456"),
                       summary(id: "z-new", checked: "2026-09-15", notified: "2026-09-16T18:00:00")]
        XCTAssertEqual(TodayWatchOverview(watches: watches, now: today).orderedWatches.first?.id, "z-new")
    }

    func testUnavailableDateDoesNotInventExpiryOrTimestamp() {
        let watch = summary(end: "not-a-date")
        XCTAssertEqual(TodayWatchOverview(watches: [watch], now: today).state(of: watch), .waiting)
        XCTAssertEqual(TodayWatchOverview.displayDate("not-a-date"), "Date unavailable")
        XCTAssertFalse(TodayWatchOverview.displayDate("2026-09-17T12:00:00.123456").contains("T12"))
    }

    func testGeographicWatchSummaryPreservesScopeInsteadOfClaimingAnywhere() throws {
        let data = Data("""
        {"id":"region","originAirports":["CPH"],"destinationRegions":["nordics"],
         "destinationCountries":[],"destinationContinents":[],"startDate":"2026-10-01",
         "endDate":"2026-12-01","maxBudget":200,"frequency":"weekly","isActive":true}
        """.utf8)
        let watch = try JSONDecoder().decode(SavedWatchSummary.self, from: data)
        XCTAssertEqual(watch.routeDescription, "CPH → nordics")
    }

    func testOrderedWatchSummaryKeepsStopOrder() {
        var watch = summary()
        watch.routeStops = ["ATH", "SKP", "SOF"]
        XCTAssertEqual(watch.routeDescription, "CPH → ATH → SKP → SOF")
    }

    func testFailedRefreshRetainsCachedDashboardAndShowsError() async {
        let service = RefreshFailingDashboardService()
        let store = DashboardStore(service: service)
        await store.load()
        await store.load(force: true)
        XCTAssertNotNil(store.dashboard)
        XCTAssertNotNil(store.errorMessage)
        XCTAssertFalse(store.isLoading)
    }
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

    func testWatchPauseResumeAndDeleteRefreshTheDashboard() async {
        let service = MutatingDashboardService()
        let store = DashboardStore(service: service)
        await store.load()
        guard let original = store.dashboard?.savedSearches.first else {
            return XCTFail("Expected a saved watch")
        }

        await store.setWatch(original, active: false)
        XCTAssertEqual(store.dashboard?.savedSearches.first?.isActive, false)
        XCTAssertNil(store.errorMessage)

        await store.setWatch(original, active: true)
        XCTAssertEqual(store.dashboard?.savedSearches.first?.isActive, true)

        await store.deleteWatch(original)
        XCTAssertEqual(store.dashboard?.savedSearches.count, 0)
        XCTAssertNil(store.workingWatchID)
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

private actor RefreshFailingDashboardService: DashboardServicing {
    var calls = 0
    func dashboard() throws -> DashboardResponse {
        calls += 1
        if calls > 1 { throw APIError.unavailable }
        return .fixture
    }
    func pauseWatch(id: String) throws -> SavedWatchSummary { throw APIError.unavailable }
    func resumeWatch(id: String) throws -> SavedWatchSummary { throw APIError.unavailable }
    func deleteWatch(id: String) throws { throw APIError.unavailable }
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

    func pauseWatch(id: String) async throws -> SavedWatchSummary { throw APIError.unavailable }
    func resumeWatch(id: String) async throws -> SavedWatchSummary { throw APIError.unavailable }
    func deleteWatch(id: String) async throws { throw APIError.unavailable }

    func requestCount() -> Int { requests }
}

private actor MutatingDashboardService: DashboardServicing {
    private var active = true
    private var removed = false

    func dashboard() async throws -> DashboardResponse {
        let base = DashboardResponse.fixture
        return DashboardResponse(
            user: base.user,
            billing: base.billing,
            usage: base.usage,
            savedSearches: removed ? [] : [watch],
            savedSearchSummary: SavedSearchSummary(total: removed ? 0 : 1, active: active && !removed ? 1 : 0)
        )
    }

    func pauseWatch(id: String) async throws -> SavedWatchSummary {
        active = false
        return watch
    }

    func resumeWatch(id: String) async throws -> SavedWatchSummary {
        active = true
        return watch
    }

    func deleteWatch(id: String) async throws { removed = true }

    private var watch: SavedWatchSummary {
        SavedWatchSummary(
            id: "watch-1", name: "Nordic weekends", originAirports: ["CPH"],
            destinationAirports: ["STO"], startDate: "2026-10-01", endDate: "2026-12-01",
            maxBudget: 200, frequency: "weekly", isActive: active,
            lastCheckedAt: nil, lastNotifiedAt: nil, lastBestPrice: nil
        )
    }
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
