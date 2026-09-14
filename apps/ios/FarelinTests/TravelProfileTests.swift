import XCTest
@testable import Farelin

@MainActor
final class TravelProfileTests: XCTestCase {
    func testIncompleteProfileDoesNotAdoptLegacyViennaPlaceholder() async {
        let store = TravelProfileStore(service: FakeTravelProfileService(profile: .incomplete))

        await store.load()

        XCTAssertEqual(store.draft?.homeLocation, "")
        XCTAssertEqual(store.draft?.originAirports, [])
        XCTAssertFalse(store.isComplete)
    }

    func testSelectingLocationAndLoadingRecommendationsPreselectsWithinPlanLimit() async {
        let service = FakeTravelProfileService(
            profile: .incomplete,
            recommended: [.copenhagen, .malmo, .billund]
        )
        let store = TravelProfileStore(service: service)
        await store.load()

        await store.selectLocation(.copenhagen)
        await store.loadRecommendedAirports(preselectLimit: 2)

        XCTAssertEqual(store.draft?.homeLocation, "Copenhagen, Denmark")
        XCTAssertEqual(store.draft?.baseLocationId, 42)
        XCTAssertEqual(store.draft?.originAirports, ["CPH", "MMX"])
        XCTAssertEqual(store.draft?.recommendedOriginAirports, ["CPH", "MMX", "BLL"])
    }

    func testOriginAirportLimitIsExplainedBeforeAddingAnotherAirport() async {
        let store = TravelProfileStore(service: FakeTravelProfileService(profile: .incomplete))
        await store.load()
        store.update { $0.originAirports = ["CPH", "MMX", "BLL"] }

        store.toggleAirportCode("HAM", limit: 3)

        XCTAssertEqual(store.draft?.originAirports, ["CPH", "MMX", "BLL"])
        XCTAssertEqual(store.errorMessage, "Your current plan allows up to 3 origin airports.")
    }

    func testSavingUsesStructuredComfortModesAndUrgentDealTrigger() async {
        let service = FakeTravelProfileService(profile: .incomplete, savedProfile: .complete)
        let store = TravelProfileStore(service: service)
        await store.load()
        store.update {
            $0.homeLocation = "Copenhagen, Denmark"
            $0.baseLocationId = 42
            $0.baseLatitude = 55.6761
            $0.baseLongitude = 12.5683
            $0.originAirports = ["CPH"]
            $0.comfortRuleModes = [
                "avoid_overnight_layovers": "require",
                "no_departures_before_6am": "prefer",
            ]
            $0.notificationFrequency = "urgent_only"
        }

        let saved = await store.save()
        let payload = await service.lastSavedPayload()

        XCTAssertTrue(saved)
        XCTAssertTrue(store.isComplete)
        XCTAssertEqual(payload?.comfortRuleModes["avoid_overnight_layovers"], "require")
        XCTAssertEqual(payload?.comfortRules.sorted(), ["avoid_overnight_layovers", "no_departures_before_6am"])
        XCTAssertEqual(payload?.alertTriggerMode, "route_deal")
    }
}

private actor FakeTravelProfileService: TravelProfileServicing {
    private let profile: TravelProfileResponse
    private let savedProfile: TravelProfileResponse
    private let recommended: [AirportResult]
    private var savedPayload: TravelProfilePayload?

    init(
        profile: TravelProfileResponse,
        savedProfile: TravelProfileResponse? = nil,
        recommended: [AirportResult] = []
    ) {
        self.profile = profile
        self.savedProfile = savedProfile ?? profile
        self.recommended = recommended
    }

    func travelProfile() -> TravelProfileResponse { profile }

    func updateTravelProfile(_ payload: TravelProfilePayload) -> TravelProfileResponse {
        savedPayload = payload
        return savedProfile
    }

    func searchLocations(_ query: String) -> [LocationResult] { [.copenhagen] }

    func recommendedAirports(
        latitude: Double,
        longitude: Double,
        maxDistanceKm: Int
    ) -> [AirportResult] { recommended }

    func searchAirports(
        _ query: String,
        latitude: Double?,
        longitude: Double?
    ) -> [AirportResult] { recommended }

    func lastSavedPayload() -> TravelProfilePayload? { savedPayload }
}

private extension TravelProfileResponse {
    static let incomplete = fixture(isComplete: false, homeLocation: nil, originAirports: ["VIE"])
    static let complete = fixture(isComplete: true, homeLocation: "Copenhagen, Denmark", originAirports: ["CPH"])

    static func fixture(
        isComplete: Bool,
        homeLocation: String?,
        originAirports: [String]
    ) -> TravelProfileResponse {
        TravelProfileResponse(
            userId: "user-1",
            isComplete: isComplete,
            homeLocation: homeLocation,
            originAirports: originAirports,
            maxAirportTravelTimeMinutes: 120,
            preferredTripTypes: ["food"],
            preferredTripLengthMin: 2,
            preferredTripLengthMax: 7,
            budgetComfortZone: "under_200",
            spontaneity: "flexible_monthly",
            comfortRules: [],
            openJawWillingness: "simple_returns_only",
            notificationFrequency: "weekly_digest",
            excludedAirlines: [],
            preferredMonths: [],
            baseLocationId: isComplete ? 42 : nil,
            baseLatitude: isComplete ? 55.6761 : nil,
            baseLongitude: isComplete ? 12.5683 : nil,
            maxAirportDistanceKm: 200,
            recommendedOriginAirports: isComplete ? ["CPH"] : [],
            dealSensitivity: "balanced",
            absoluteMaxBudget: nil,
            alertTriggerMode: "any",
            comfortRuleModes: [:],
            themePreference: "system"
        )
    }
}

private extension LocationResult {
    static let copenhagen = LocationResult(
        id: 42,
        name: "Copenhagen",
        countryCode: "DK",
        countryName: "Denmark",
        adminRegion: "Capital Region",
        latitude: 55.6761,
        longitude: 12.5683,
        population: 1_400_000
    )
}

private extension AirportResult {
    static let copenhagen = fixture(code: "CPH", city: "Copenhagen", distance: 8)
    static let malmo = fixture(code: "MMX", city: "Malmö", distance: 52)
    static let billund = fixture(code: "BLL", city: "Billund", distance: 216)

    static func fixture(code: String, city: String, distance: Double) -> AirportResult {
        AirportResult(
            iataCode: code,
            name: "\(city) Airport",
            city: city,
            countryCode: code == "MMX" ? "SE" : "DK",
            countryName: code == "MMX" ? "Sweden" : "Denmark",
            latitude: 55.0,
            longitude: 12.0,
            type: "large_airport",
            scheduledService: true,
            distanceKm: distance
        )
    }
}
