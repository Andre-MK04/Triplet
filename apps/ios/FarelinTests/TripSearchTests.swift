import XCTest
@testable import Farelin

@MainActor
final class TripSearchTests: XCTestCase {
    func testAISearchResponseDecodesBackendShape() throws {
        let response = try JSONDecoder().decode(
            FarelinAISearchResponse.self,
            from: Data(Self.searchJSON.utf8)
        )

        XCTAssertEqual(response.trips.count, 1)
        XCTAssertEqual(response.trips[0].routeTitle, "CPH → Stockholm")
        XCTAssertEqual(response.trips[0].price?.freshness, "fresh")
        XCTAssertEqual(response.parsedRequest?.originAirports, ["CPH", "MMX"])
        XCTAssertEqual(response.providerMetadata?.cachedResultsUsed, true)
    }

    func testSearchUsesProfileOriginsAndKeepsServerResults() async {
        let service = FakeTripSearchService(response: .fixture)
        let store = TripSearchStore(service: service)
        store.query = "A food weekend in Stockholm next month"

        await store.search(origins: ["CPH", "MMX"])

        let request = await service.lastRequest()
        XCTAssertEqual(request?.originAirports, ["CPH", "MMX"])
        XCTAssertEqual(store.response?.trips.first?.destination?.city, "Stockholm")
        XCTAssertNil(store.errorMessage)
        XCTAssertFalse(store.isSearching)
    }

    func testSearchRequiresAnOriginWithoutCallingBackend() async {
        let service = FakeTripSearchService(response: .fixture)
        let store = TripSearchStore(service: service)
        store.query = "A week somewhere warm next month"

        await store.search(origins: [])

        let request = await service.lastRequest()
        XCTAssertEqual(store.errorMessage, "Add at least one origin airport to your travel profile first.")
        XCTAssertNil(request)
    }

    func testRapidSubmissionsOnlyCreateOneMeteredSearch() async throws {
        let service = SlowCountingTripSearchService(response: .fixture)
        let store = TripSearchStore(service: service)
        store.query = "A food weekend in Stockholm next month"

        store.submit(origins: ["CPH"])
        store.submit(origins: ["CPH"])
        store.submit(origins: ["CPH"])

        XCTAssertTrue(store.isSearching)
        try await Task.sleep(for: .milliseconds(120))
        let callCount = await service.callCount()
        XCTAssertEqual(callCount, 1)
    }

    func testAdvancedSearchUsesProfileForBlankFieldsAndSendsExplicitOverrides() async {
        let service = FakeTripSearchService(response: .fixture)
        let store = TripSearchStore(service: service)
        store.advanced.destinations = [.stockholm]
        store.advanced.travelStyles = ["food"]
        store.advanced.directPreference = "connections"
        store.advanced.budgetText = "350"

        await store.searchAdvanced(profileOrigins: ["CPH", "MMX"])

        let request = await service.lastAdvancedRequest()
        XCTAssertNil(request?.originAirports)
        XCTAssertEqual(request?.destinationAirports, ["STO"])
        XCTAssertEqual(request?.travelStyles, ["food"])
        XCTAssertEqual(request?.directOnly, false)
        XCTAssertEqual(request?.maxBudget, 350)
        XCTAssertNil(request?.startDate)
        XCTAssertNil(store.errorMessage)
    }

    func testAdvancedSearchDefaultsToReturnAndSendsTheVisibleTripShape() async {
        let service = FakeTripSearchService(response: .fixture)
        let store = TripSearchStore(service: service)

        XCTAssertEqual(store.advanced.tripPlan, "return")

        await store.searchAdvanced(profileOrigins: ["CPH"])

        let request = await service.lastAdvancedRequest()
        XCTAssertEqual(request?.tripPlan, "return")
        XCTAssertNil(store.errorMessage)
    }

    func testAdvancedMultiCityRequiresTwoSpecificStopsWithoutCallingBackend() async {
        let service = FakeTripSearchService(response: .fixture)
        let store = TripSearchStore(service: service)
        store.advanced.tripPlan = "multi_city"
        store.advanced.destinations = [.stockholm]

        await store.searchAdvanced(profileOrigins: ["CPH"])

        XCTAssertEqual(
            store.errorMessage,
            "Add at least two cities or airports in travel order for a multi-city trip."
        )
        let request = await service.lastAdvancedRequest()
        XCTAssertNil(request)
    }

    func testAdvancedOpenJawMapsArrivalAndFlyHomeCitiesToDifferentFields() async {
        let service = FakeTripSearchService(response: .fixture)
        let store = TripSearchStore(service: service)
        store.advanced.tripPlan = "open_jaw"
        store.advanced.destinations = [.stockholm, .helsinki]

        await store.searchAdvanced(profileOrigins: ["CPH"])

        let request = await service.lastAdvancedRequest()
        XCTAssertEqual(request?.destinationAirports, ["STO"])
        XCTAssertEqual(request?.returnOriginAirports, ["HEL"])
        XCTAssertEqual(request?.tripPlan, "open_jaw")
        XCTAssertNil(request?.routeStops)
        XCTAssertNil(store.errorMessage)
    }

    func testAdvancedOpenJawRequiresExactlyTwoSpecificCities() async {
        let service = FakeTripSearchService(response: .fixture)
        let store = TripSearchStore(service: service)
        store.advanced.tripPlan = "open_jaw"
        store.advanced.destinations = [.stockholm]

        await store.searchAdvanced(profileOrigins: ["CPH"])

        XCTAssertEqual(
            store.errorMessage,
            "Add exactly two cities or airports: where you land, then where you fly home from."
        )
        let request = await service.lastAdvancedRequest()
        XCTAssertNil(request)
    }

    func testTripDetailLoadsAnExistingCachedItineraryWithoutRegenerating() async {
        let service = FakeTripDetailService(
            suggestion: .fixture(itinerary: .fixture),
            generated: ItineraryGenerationResponse(itinerary: .fixture, cached: false)
        )
        let store = TripDetailStore(
            trip: .fixture(),
            suggestionID: "suggestion",
            service: service
        )

        await store.load()
        await store.generateItinerary()
        let generationCalls = await service.generationCallCount()

        XCTAssertEqual(store.title, "Copenhagen for food lovers")
        XCTAssertEqual(store.itinerary?.days.first?.items.first?.title, "Torvehallerne tasting")
        XCTAssertTrue(store.itineraryWasCached)
        XCTAssertEqual(generationCalls, 0)
    }

    func testTripDetailGeneratesAnItineraryOnlyOnce() async {
        let service = FakeTripDetailService(
            suggestion: .fixture(itinerary: nil),
            generated: ItineraryGenerationResponse(itinerary: .fixture, cached: false)
        )
        let store = TripDetailStore(
            trip: .fixture(),
            suggestionID: "suggestion",
            service: service
        )

        await store.load()
        await store.generateItinerary()
        await store.generateItinerary()
        let generationCalls = await service.generationCallCount()

        XCTAssertEqual(store.itinerary?.summary, "A realistic food-focused weekend.")
        XCTAssertFalse(store.itineraryWasCached)
        XCTAssertEqual(generationCalls, 1)
    }

    func testRapidItineraryTapsOnlyCreateOneGenerationRequest() async throws {
        let service = FakeTripDetailService(
            suggestion: .fixture(itinerary: nil),
            generated: ItineraryGenerationResponse(itinerary: .fixture, cached: false)
        )
        let store = TripDetailStore(
            trip: .fixture(),
            suggestionID: "suggestion",
            service: service
        )

        store.submitItineraryGeneration()
        store.submitItineraryGeneration()
        store.submitItineraryGeneration()

        XCTAssertTrue(store.isGenerating)
        try await Task.sleep(for: .milliseconds(40))
        let generationCalls = await service.generationCallCount()
        XCTAssertEqual(generationCalls, 1)
    }

    func testEstimatedPriceCopyNeverSoundsGuaranteed() {
        let trip = SearchTrip.fixture(isEstimate: true, freshness: "stale", legCount: 3)

        XCTAssertEqual(FarelinSearchFormat.priceHeadline(trip), "Estimated from €210")
        XCTAssertTrue(FarelinSearchFormat.observationDetail(trip).contains("separately observed"))
        XCTAssertFalse(FarelinSearchFormat.observationDetail(trip).lowercased().contains("guaranteed price"))
    }

    private static let searchJSON = """
    {
      "message": "Stockholm fits your food-focused weekend and the returned fare is within budget.",
      "parsedRequest": {
        "originAirports": ["CPH", "MMX"],
        "destinationAirports": ["STO"],
        "destinationCountries": [],
        "destinationRegions": [],
        "destinationContinents": [],
        "startDate": "2026-10-01",
        "endDate": "2026-11-30",
        "minTripLengthDays": 2,
        "maxTripLengthDays": 4,
        "maxBudget": 300,
        "maxGroundTransferHours": 3,
        "tripStyle": "one city",
        "tripPlan": "return",
        "directOnly": false,
        "includeBaggage": false,
        "travelStyles": ["food"]
      },
      "trips": [{
        "id": "trip-1",
        "tripType": "same_city",
        "outboundFlight": {
          "id": "out-1", "origin": "CPH", "destination": "ARN",
          "departureDateTime": "2026-10-16T09:00:00+02:00",
          "arrivalDateTime": "2026-10-16T10:15:00+02:00",
          "airline": "SK", "price": 55, "currency": "EUR",
          "bookingUrl": "https://example.com/check", "deepLink": null,
          "affiliateUrl": null, "stops": 0, "durationMinutes": 75,
          "isLive": false, "confidenceLevel": "indicative",
          "observedAt": "2026-09-14T10:00:00Z"
        },
        "returnFlight": {
          "id": "in-1", "origin": "ARN", "destination": "CPH",
          "departureDateTime": "2026-10-18T19:00:00+02:00",
          "arrivalDateTime": "2026-10-18T20:15:00+02:00",
          "airline": "SK", "price": 55, "currency": "EUR",
          "bookingUrl": "https://example.com/check", "deepLink": null,
          "affiliateUrl": null, "stops": 0, "durationMinutes": 75,
          "isLive": false, "confidenceLevel": "indicative",
          "observedAt": "2026-09-14T10:00:00Z"
        },
        "groundTransfer": null,
        "price": {
          "amount": 110, "currency": "EUR", "kind": "cached_return",
          "source": "travelpayouts-cache", "isLive": false,
          "isEstimate": false, "observedAt": "2026-09-14T10:00:00Z",
          "ageHours": 1, "freshness": "fresh", "freshnessScore": 95,
          "legCount": 1, "history": null
        },
        "totalPrice": 110, "tripLengthDays": 3, "nights": 2,
        "score": 82, "dealScore": 80, "fitScore": 86,
        "suggestionId": "suggestion-1", "fareKind": "round_trip_bundle",
        "explanation": "A useful short trip with convenient times.",
        "warnings": ["Cabin bag details are unknown."],
        "tags": ["food", "weekend"],
        "bookingUrl": "https://example.com/check", "provider": "travelpayouts",
        "destination": {
          "code": "STO", "kind": "city", "city": "Stockholm",
          "country": "Sweden", "countryCode": "SE", "continent": "Europe"
        }
      }],
      "relaxationNote": null,
      "missingFields": [],
      "providerMetadata": {
        "providerUsed": "travelpayouts", "providerName": "travelpayouts",
        "liveProviderAttempted": false, "liveProviderSucceeded": false,
        "cachedResultsUsed": true, "cachedResultsStale": false,
        "requestsAttempted": 0, "requestsLimit": 0, "rawOffersCount": 1,
        "mappedFlightsCount": 2, "skippedOffersCount": 0,
        "affiliateLinksGenerated": 1, "deepLinksReturned": 1,
        "providerWarnings": []
      },
      "aiMetadata": {
        "aiProvider": "openai", "model": "gpt-5-mini", "toolCallsUsed": 1,
        "fallbackUsed": false, "warnings": []
      }
    }
    """
}

private actor FakeTripSearchService: TripSearchServicing {
    private let response: FarelinAISearchResponse
    private var request: FarelinAISearchRequest?
    private var advancedRequest: FarelinAdvancedSearchRequest?

    init(response: FarelinAISearchResponse) {
        self.response = response
    }

    func searchTrips(_ request: FarelinAISearchRequest) async throws -> FarelinAISearchResponse {
        self.request = request
        return response
    }

    func advancedSearch(_ request: FarelinAdvancedSearchRequest) async throws -> FarelinAISearchResponse {
        advancedRequest = request
        return response
    }

    func searchPlaces(_ query: String) async throws -> [FlightPlaceResult] { [] }

    func lastRequest() -> FarelinAISearchRequest? { request }
    func lastAdvancedRequest() -> FarelinAdvancedSearchRequest? { advancedRequest }
}

private actor SlowCountingTripSearchService: TripSearchServicing {
    private let response: FarelinAISearchResponse
    private var calls = 0

    init(response: FarelinAISearchResponse) {
        self.response = response
    }

    func searchTrips(_ request: FarelinAISearchRequest) async throws -> FarelinAISearchResponse {
        calls += 1
        try await Task.sleep(for: .milliseconds(80))
        return response
    }

    func advancedSearch(_ request: FarelinAdvancedSearchRequest) async throws -> FarelinAISearchResponse {
        calls += 1
        try await Task.sleep(for: .milliseconds(80))
        return response
    }

    func searchPlaces(_ query: String) async throws -> [FlightPlaceResult] { [] }

    func callCount() -> Int { calls }
}

private actor FakeTripDetailService: TripDetailServicing {
    private let suggestion: TripSuggestionResponse
    private let generated: ItineraryGenerationResponse
    private var generationCalls = 0

    init(suggestion: TripSuggestionResponse, generated: ItineraryGenerationResponse) {
        self.suggestion = suggestion
        self.generated = generated
    }

    func tripSuggestion(id: String) async throws -> TripSuggestionResponse {
        suggestion
    }

    func generateItinerary(suggestionID: String) async throws -> ItineraryGenerationResponse {
        generationCalls += 1
        return generated
    }

    func generationCallCount() -> Int { generationCalls }
}

private extension FarelinAISearchResponse {
    static let fixture = FarelinAISearchResponse(
        message: "Stockholm is a strong fit.",
        parsedRequest: nil,
        trips: [.fixture()],
        relaxationNote: nil,
        missingFields: [],
        providerMetadata: nil,
        sourceMap: nil,
        hardBudgetApplied: nil
    )
}

private extension FlightPlaceResult {
    static let stockholm = FlightPlaceResult(
        code: "STO",
        kind: "city",
        name: "Stockholm",
        subtitle: "City · Sweden",
        city: "Stockholm",
        countryCode: "SE",
        countryName: "Sweden",
        continent: "Europe",
        searchCodes: ["STO"]
    )

    static let helsinki = FlightPlaceResult(
        code: "HEL",
        kind: "city",
        name: "Helsinki",
        subtitle: "City · Finland",
        city: "Helsinki",
        countryCode: "FI",
        countryName: "Finland",
        continent: "Europe",
        searchCodes: ["HEL"]
    )
}

private extension TripSuggestionResponse {
    static func fixture(itinerary: ItineraryPlan?) -> TripSuggestionResponse {
        TripSuggestionResponse(
            id: "suggestion",
            title: "Copenhagen for food lovers",
            tripType: "same_city",
            createdAt: "2026-09-14T10:00:00Z",
            expiresAt: "2026-09-15T10:00:00Z",
            dealScore: 80,
            fitScore: 85,
            trip: .fixture(),
            itinerary: itinerary,
            disclaimer: "Prices were observed and may have changed."
        )
    }
}

private extension ItineraryPlan {
    static let fixture = ItineraryPlan(
        summary: "A realistic food-focused weekend.",
        days: [
            ItineraryDay(
                label: "Day 1 — arrival",
                items: [
                    ItineraryItem(
                        partOfDay: "afternoon",
                        title: "Torvehallerne tasting",
                        description: "Try a few Danish specialties after checking in.",
                        category: "food",
                        estimatedCost: "€20–35"
                    )
                ]
            )
        ],
        gettingAround: "Use the metro and walk in the centre.",
        extraCostEstimate: "€80–140",
        disclaimers: ["Confirm opening hours and prices."],
        generatedAt: "2026-09-14T10:00:00Z"
    )
}

private extension SearchTrip {
    static func fixture(
        isEstimate: Bool = false,
        freshness: String = "fresh",
        legCount: Int = 1
    ) -> SearchTrip {
        let outbound = SearchFlight(
            id: "out", origin: "CPH", destination: "ARN",
            departureDateTime: "2026-10-16T09:00:00Z",
            arrivalDateTime: "2026-10-16T10:15:00Z",
            airline: "SK", price: 105, currency: "EUR",
            bookingUrl: "https://example.com/check", deepLink: nil, affiliateUrl: nil,
            stops: 0, durationMinutes: 75, isLive: false,
            confidenceLevel: "indicative", observedAt: "2026-09-14T10:00:00Z"
        )
        let inbound = SearchFlight(
            id: "in", origin: "ARN", destination: "CPH",
            departureDateTime: "2026-10-18T19:00:00Z",
            arrivalDateTime: "2026-10-18T20:15:00Z",
            airline: "SK", price: 105, currency: "EUR",
            bookingUrl: "https://example.com/check", deepLink: nil, affiliateUrl: nil,
            stops: 0, durationMinutes: 75, isLive: false,
            confidenceLevel: "indicative", observedAt: "2026-09-14T10:00:00Z"
        )
        return SearchTrip(
            id: "trip", tripType: "same_city", outboundFlight: outbound,
            returnFlight: inbound, groundTransfer: nil,
            price: SearchPriceInfo(
                amount: 210, currency: "EUR",
                kind: isEstimate ? "estimated_multi_city" : "cached_return",
                source: "travelpayouts-cache", isLive: false, isEstimate: isEstimate,
                observedAt: "2026-09-14T10:00:00Z", ageHours: 72,
                freshness: freshness, legCount: legCount
            ),
            totalPrice: 210, tripLengthDays: 3, nights: 2, score: 80,
            dealScore: 80, fitScore: 85, suggestionId: "suggestion",
            fareKind: "round_trip_bundle", explanation: "A good fit.",
            warnings: [], tags: ["food"], bookingUrl: "https://example.com/check",
            provider: "travelpayouts",
            destination: SearchDestination(
                code: "STO", city: "Stockholm", country: "Sweden",
                countryCode: "SE", continent: "Europe"
            )
        )
    }
}
