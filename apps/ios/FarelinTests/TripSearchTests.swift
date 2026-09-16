import XCTest
@testable import Farelin

@MainActor
final class TripSearchTests: XCTestCase {
    func testFlexibleBudgetAndOneStopAreSentToExistingEngine() async throws {
        let service = FakeTripSearchService(response: .fixture)
        let store = TripSearchStore(service: service)
        store.advanced.flexibleBudget = true
        store.advanced.directPreference = "one_stop"
        await store.searchAdvanced(profileOrigins: ["CPH"])
        let captured = await service.lastAdvancedRequest()
        let request = try XCTUnwrap(captured)
        XCTAssertTrue(request.flexibleBudget)
        XCTAssertNil(request.maxBudget)
        XCTAssertEqual(request.maxStops, 1)
        XCTAssertEqual(request.directOnly, false)
        let json = try JSONSerialization.jsonObject(with: JSONEncoder().encode(request)) as? [String: Any]
        XCTAssertEqual(json?["flexibleBudget"] as? Bool, true)
        XCTAssertEqual(json?["maxStops"] as? Int, 1)
    }

    func testCombinedProviderSearchIncludesAllFlightsButNotGround() throws {
        var root = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(Self.searchJSON.utf8)) as? [String: Any])
        var trip = try XCTUnwrap((root["trips"] as? [[String: Any]])?.first)
        let original = try XCTUnwrap(trip["outboundFlight"] as? [String: Any])
        let legs = [("CPH", "ATH", "2026-10-07"), ("ATH", "SKP", "2026-10-15"), ("SOF", "CPH", "2026-11-21")]
        var segments: [[String: Any]] = []
        for (index, leg) in legs.enumerated() {
            var flight = original
            flight["origin"] = leg.0
            flight["destination"] = leg.1
            flight["departureDateTime"] = leg.2 + "T09:00:00"
            flight["bookingUrl"] = "https://www.aviasales.com/search/CPH0710ATH1?marker=747408"
            segments.append(["kind": "flight", "origin": leg.0, "destination": leg.1,
                             "originCity": leg.0, "destinationCity": leg.1,
                             "departureDate": leg.2, "flight": flight])
            if index == 1 {
                segments.append(["kind": "ground", "origin": "SKP", "destination": "SOF",
                                 "originCity": "Skopje", "destinationCity": "Sofia", "departureDate": "2026-10-17"])
            }
        }
        trip["tripType"] = "multi_city"
        trip["provider"] = "travelpayouts"
        trip["segments"] = segments
        root["trips"] = [trip]
        var response = try JSONDecoder().decode(FarelinAISearchResponse.self, from: JSONSerialization.data(withJSONObject: root))
        let url = try XCTUnwrap(response.trips.first?.checkPriceURL)
        XCTAssertEqual(url.path, "/search/CPH0710ATH1510SKP-SOF2111CPH1")
        XCTAssertTrue(url.absoluteString.contains("currency=eur"))
        XCTAssertTrue(url.absoluteString.contains("marker=747408"))
        segments[1]["departureDate"] = "2026-10-06"
        trip["segments"] = segments
        root["trips"] = [trip]
        response = try JSONDecoder().decode(FarelinAISearchResponse.self, from: JSONSerialization.data(withJSONObject: root))
        XCTAssertNil(response.trips.first?.checkPriceURL, "Invalid chronology must not create a broken provider link")
    }

    func testEditingResultsPreservesDraftAndDoesNotSubmitAgain() async {
        let service = FakeTripSearchService(response: .fixture)
        let store = TripSearchStore(service: service)
        store.query = "A quiet weekend in Scandinavia"
        store.advanced.destinations = [.scandinavia]
        store.advanced.budgetText = "200"
        let draft = store.advanced
        await store.search(origins: ["CPH"])
        store.clearResults()
        XCTAssertNil(store.response)
        XCTAssertEqual(store.advanced, draft)
        XCTAssertEqual(store.query, "A quiet weekend in Scandinavia")
        let advancedRequest = await service.lastAdvancedRequest()
        XCTAssertNil(advancedRequest)
        let counts = await service.callCounts()
        XCTAssertEqual(counts.ai, 1)
        XCTAssertEqual(counts.advanced, 0)
    }

    func testWiderDatesPrepareDraftWithoutChangingOtherChoicesOrCallingProvider() async throws {
        let service = FakeTripSearchService(response: .fixture)
        let store = TripSearchStore(service: service)
        store.advanced.useProfileOrigins = false
        store.advanced.selectedOrigins = ["CPH", "MMX"]
        store.advanced.destinations = [.stockholm, .helsinki]
        store.advanced.tripPlan = "multi_city"
        store.advanced.budgetText = "400"
        store.advanced.directPreference = "direct"
        store.advanced.useProfileDates = false
        let original = store.advanced
        XCTAssertTrue(store.canReviewWiderDates)
        XCTAssertTrue(store.prepareWiderDateWindow())
        var expected = original
        expected.endDate = try XCTUnwrap(Calendar(identifier: .gregorian).date(byAdding: .day, value: 30, to: original.endDate))
        XCTAssertEqual(store.advanced, expected)
        let aiRequest = await service.lastRequest()
        let advancedRequest = await service.lastAdvancedRequest()
        XCTAssertNil(aiRequest)
        XCTAssertNil(advancedRequest)
        XCTAssertFalse(store.isSearching)
    }

    func testWiderDatesUseResolvedProfileDatesFromResults() async throws {
        let response = try JSONDecoder().decode(FarelinAISearchResponse.self, from: Data(Self.searchJSON.utf8))
        let store = TripSearchStore(service: FakeTripSearchService(response: response))
        await store.searchAdvanced(profileOrigins: ["CPH"])
        let parsed = try XCTUnwrap(store.response?.parsedRequest)
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        XCTAssertTrue(store.prepareWiderDateWindow())
        XCTAssertFalse(store.advanced.useProfileDates)
        XCTAssertEqual(formatter.string(from: store.advanced.startDate), parsed.startDate)
        let oldEnd = try XCTUnwrap(formatter.date(from: parsed.endDate))
        XCTAssertEqual(store.advanced.endDate, Calendar(identifier: .gregorian).date(byAdding: .day, value: 30, to: oldEnd))
        XCTAssertNil(store.response)
    }

    func testWiderDatesDoNotGuessWhenProfileHasNotBeenResolved() {
        let store = TripSearchStore(service: FakeTripSearchService(response: .fixture))
        let draft = store.advanced
        XCTAssertFalse(store.prepareWiderDateWindow())
        XCTAssertFalse(store.canReviewWiderDates)
        XCTAssertEqual(store.advanced, draft)
    }

    func testWiderDatesNeverConvertAnAIRequestIntoDifferentStructuredFilters() async {
        let store = TripSearchStore(service: FakeTripSearchService(response: .fixture))
        store.query = "A direct flight to Japan in November"
        store.advanced.useProfileDates = false
        await store.search(origins: ["CPH"])
        let draft = store.advanced
        XCTAssertTrue(store.lastSearchUsedAI)
        XCTAssertFalse(store.canReviewWiderDates)
        XCTAssertFalse(store.prepareWiderDateWindow())
        XCTAssertNotNil(store.response)
        XCTAssertEqual(store.advanced, draft)
    }

    func testOpportunityFeedUsesObservedTripsWithoutRequestingAISearch() async throws {
        let search = try JSONSerialization.jsonObject(with: Data(Self.searchJSON.utf8)) as? [String: Any]
        let trips = try XCTUnwrap(search?["trips"])
        let data = try JSONSerialization.data(withJSONObject: [
            "trips": trips,
            "originAirports": ["CPH"],
            "source": "cached_database",
            "isReady": true,
            "isStale": true,
        ])
        let feed = try JSONDecoder().decode(NativeOpportunityFeed.self, from: data)
        let service = CountingOpportunityService(feed: feed)
        let store = OpportunityStore(service: service)

        await store.load()
        await store.load()

        XCTAssertEqual(store.feed?.trips.first?.routeTitle, "CPH → Stockholm")
        XCTAssertEqual(store.feed?.source, "cached_database")
        XCTAssertTrue(store.feed?.isStale == true)
        let callCount = await service.calls()
        XCTAssertEqual(callCount, 1)
    }
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

    func testNativeWatchRequestUsesOnlyPersistedScopeAndWeeklyFrequency() throws {
        let request = NativeSavedWatchRequest(
            email: "tester@example.invalid",
            name: "Stockholm trips",
            originAirports: ["CPH"],
            destinationAirports: ["ARN"],
            startDate: "2026-10-01",
            endDate: "2026-12-31",
            minTripLengthDays: 4,
            maxTripLengthDays: 7,
            maxBudget: 300,
            maxGroundTransferHours: 4,
            tripStyle: "one city",
            frequency: "weekly",
            triggerMode: "below_budget"
        )
        let body = try XCTUnwrap(JSONSerialization.jsonObject(with: JSONEncoder().encode(request)) as? [String: Any])
        XCTAssertEqual(body["frequency"] as? String, "weekly")
        XCTAssertEqual(body["destinationAirports"] as? [String], ["ARN"])
        XCTAssertEqual(body["maxBudget"] as? Double, 300)
        XCTAssertEqual(body["destinationCountries"] as? [String], [])
        XCTAssertNil(body["routeStops"])
    }

    func testRegionWatchOmitsEmptyAirportConstraint() throws {
        var request = NativeSavedWatchRequest(
            email: "tester@example.invalid", name: "Nordics", originAirports: ["CPH", "MMX"],
            destinationAirports: nil, startDate: "2026-10-01", endDate: "2026-12-31",
            minTripLengthDays: 4, maxTripLengthDays: 7, maxBudget: 400, maxGroundTransferHours: 6,
            tripStyle: "surprise me", frequency: "weekly", triggerMode: "below_budget"
        )
        request.destinationRegions = ["nordics"]
        request.tripPlan = "multi_city"
        let body = try XCTUnwrap(JSONSerialization.jsonObject(with: JSONEncoder().encode(request)) as? [String: Any])
        XCTAssertNil(body["destinationAirports"])
        XCTAssertEqual(body["destinationRegions"] as? [String], ["nordics"])
        XCTAssertEqual(body["tripPlan"] as? String, "multi_city")
        XCTAssertEqual(body["originAirports"] as? [String], ["CPH", "MMX"])
    }

    func testMultiCityResponseKeepsEveryPricedFlightLegAndStop() throws {
        var envelope = try XCTUnwrap(
            JSONSerialization.jsonObject(with: Data(Self.searchJSON.utf8)) as? [String: Any]
        )
        var trips = try XCTUnwrap(envelope["trips"] as? [[String: Any]])
        var trip = trips[0]
        let outbound = try XCTUnwrap(trip["outboundFlight"] as? [String: Any])
        let homebound = try XCTUnwrap(trip["returnFlight"] as? [String: Any])
        trip["tripType"] = "multi_city"
        trip["stays"] = [
            ["code": "STO", "city": "Stockholm", "country": "Sweden", "countryCode": "SE",
             "arrivalDate": "2026-10-16", "departureDate": "2026-10-18", "nights": 2],
            ["code": "HEL", "city": "Helsinki", "country": "Finland", "countryCode": "FI",
             "arrivalDate": "2026-10-18", "departureDate": "2026-10-20", "nights": 2],
        ]
        trip["segments"] = [
            ["kind": "flight", "origin": "CPH", "destination": "ARN", "originCity": "Copenhagen",
             "destinationCity": "Stockholm", "departureDate": "2026-10-16", "flight": outbound],
            ["kind": "flight", "origin": "ARN", "destination": "HEL", "originCity": "Stockholm",
             "destinationCity": "Helsinki", "departureDate": "2026-10-18", "flight": outbound],
            ["kind": "flight", "origin": "HEL", "destination": "CPH", "originCity": "Helsinki",
             "destinationCity": "Copenhagen", "departureDate": "2026-10-20", "flight": homebound],
        ]
        trip["groundEstimate"] = NSNull()
        trips[0] = trip
        envelope["trips"] = trips

        let response = try JSONDecoder().decode(
            FarelinAISearchResponse.self,
            from: JSONSerialization.data(withJSONObject: envelope)
        )

        XCTAssertEqual(response.trips[0].segments?.filter { $0.kind == "flight" }.count, 3)
        XCTAssertEqual(response.trips[0].routeTitle, "CPH → Stockholm → Helsinki → CPH")
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
        XCTAssertNil(request?.maxGroundTransferHours)
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

    func testExploreAcceptsSingleScandinaviaRegion() async {
        let service = FakeTripSearchService(response: .fixture)
        let store = TripSearchStore(service: service)
        store.advanced.tripPlan = "multi_city"
        store.advanced.destinations = [.scandinavia]

        await store.searchAdvanced(profileOrigins: ["CPH"])

        let request = await service.lastAdvancedRequest()
        XCTAssertEqual(request?.destinationRegions, ["scandinavia"])
        XCTAssertEqual(request?.tripPlan, "multi_city")
        XCTAssertNil(request?.routeStops)
        XCTAssertNil(store.errorMessage)
    }

    func testExploreResolvesTypedScandinaviaWithoutManualCitySelection() async {
        let service = FakeTripSearchService(response: .fixture)
        let store = TripSearchStore(service: service)
        store.advanced.tripPlan = "multi_city"
        store.placeQuery = "Scandinavia"
        await store.searchAdvanced(profileOrigins: ["CPH"])
        let request = await service.lastAdvancedRequest()
        XCTAssertEqual(request?.destinationRegions, ["scandinavia"])
        XCTAssertNil(request?.routeStops)
        XCTAssertNil(store.errorMessage)
    }

    func testSavedFareIsExplicitlyAnObservedBookmarkWithSafePriceLink() throws {
        let json = """
        {"id":"fare-1","suggestionId":"suggestion-1","title":"Stockholm → Oslo",
         "tripType":"multi_city","observedPrice":245,"currency":"EUR","fareStatus":"indicative",
         "observedAt":"2026-09-15T12:00:00","checkPriceUrl":"https://www.aviasales.com/search/VIESTO",
         "savedAt":"2026-09-15T12:01:00","disclaimer":"Saved fare is an observation, not a monitored price."}
        """
        let fare = try JSONDecoder().decode(SavedFareSummary.self, from: Data(json.utf8))
        XCTAssertEqual(fare.tripType, "multi_city")
        XCTAssertEqual(fare.observedPrice, 245)
        XCTAssertEqual(fare.fareStatus, "indicative")
        XCTAssertEqual(fare.checkPriceURL?.scheme, "https")
        XCTAssertTrue(fare.disclaimer.contains("not a monitored price"))
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

    func testAdvancedOpenJawAcceptsOneBroadRegionForFareBackedProposal() async {
        let service = FakeTripSearchService(response: .fixture)
        let store = TripSearchStore(service: service)
        store.advanced.tripPlan = "open_jaw"
        store.advanced.destinations = [.scandinavia]
        await store.searchAdvanced(profileOrigins: ["CPH"])
        let request = await service.lastAdvancedRequest()
        XCTAssertEqual(request?.destinationRegions, ["scandinavia"])
        XCTAssertNil(request?.returnOriginAirports)
        XCTAssertEqual(request?.tripPlan, "open_jaw")
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

private actor CountingOpportunityService: OpportunityServicing {
    let feed: NativeOpportunityFeed
    private var count = 0

    init(feed: NativeOpportunityFeed) { self.feed = feed }

    func opportunities() async throws -> NativeOpportunityFeed {
        count += 1
        return feed
    }

    func calls() -> Int { count }
}

private actor FakeTripSearchService: TripSearchServicing {
    private let response: FarelinAISearchResponse
    private var request: FarelinAISearchRequest?
    private var advancedRequest: FarelinAdvancedSearchRequest?
    private var aiCalls = 0
    private var advancedCalls = 0

    init(response: FarelinAISearchResponse) {
        self.response = response
    }

    func searchTrips(_ request: FarelinAISearchRequest) async throws -> FarelinAISearchResponse {
        aiCalls += 1
        self.request = request
        return response
    }

    func advancedSearch(_ request: FarelinAdvancedSearchRequest) async throws -> FarelinAISearchResponse {
        advancedCalls += 1
        advancedRequest = request
        return response
    }

    func searchPlaces(_ query: String) async throws -> [FlightPlaceResult] {
        query.caseInsensitiveCompare("Scandinavia") == .orderedSame ? [.scandinavia] : []
    }

    func lastRequest() -> FarelinAISearchRequest? { request }
    func lastAdvancedRequest() -> FarelinAdvancedSearchRequest? { advancedRequest }
    func callCounts() -> (ai: Int, advanced: Int) { (aiCalls, advancedCalls) }
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
    static let scandinavia = FlightPlaceResult(
        code: "scandinavia", kind: "region", name: "Scandinavia",
        subtitle: "Region", city: nil, countryCode: nil,
        countryName: nil, continent: nil, searchCodes: []
    )
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
            segments: nil, stays: nil, flightCost: nil, groundEstimate: nil,
            transportTotalEstimate: nil, durationMatch: nil,
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
