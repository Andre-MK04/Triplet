import MapKit
import XCTest
@testable import Farelin

@MainActor
final class MyWorldTests: XCTestCase {
    func testTravelMapPayloadDecodesBackendShape() throws {
        let response = try JSONDecoder().decode(
            TravelMapResponse.self,
            from: Data(Self.mapJSON.utf8)
        )

        XCTAssertEqual(response.countries.first?.name, "Denmark")
        XCTAssertEqual(response.countries.first?.primaryStatus, "visited")
        XCTAssertEqual(response.stats.countriesVisited, 1)
        XCTAssertEqual(response.stats.worldExploredPercentage, 0.51)
    }

    func testCountryGeometryIsBundledAndDecodesFranceAndNorway() throws {
        let url = try XCTUnwrap(Bundle.main.url(forResource: "NaturalEarthCountries", withExtension: "geojson"))
        let features = try MKGeoJSONDecoder().decode(Data(contentsOf: url)).compactMap { $0 as? MKGeoJSONFeature }
        XCTAssertGreaterThan(features.count, 150)
        let alpha3Codes = try features.compactMap { feature -> String? in
            guard let properties = feature.properties else { return nil }
            let values = try XCTUnwrap(JSONSerialization.jsonObject(with: properties) as? [String: Any])
            return values["ADM0_A3"] as? String
        }
        XCTAssertTrue(alpha3Codes.contains("FRA"))
        XCTAssertTrue(alpha3Codes.contains("NOR"))
    }

    func testStoreLoadsCatalogAndMapThenFiltersByNameOrCode() async {
        let service = FakeTravelMapService()
        let store = MyWorldStore(service: service)

        await store.load()
        store.query = "jap"

        XCTAssertEqual(store.filteredCatalog.map(\.name), ["Japan"])
        XCTAssertEqual(store.countriesByCode["DK"]?.primaryStatus, "visited")
        XCTAssertNil(store.errorMessage)
    }

    func testUpdatingASelectedCountryReloadsAuthoritativeStats() async {
        let service = FakeTravelMapService()
        let store = MyWorldStore(service: service)
        await store.load()
        store.select("JP")

        await store.updateSelected(CountryStateUpdate(wishlist: true))

        let updates = await service.updates()
        XCTAssertEqual(updates, ["JP"])
        XCTAssertEqual(store.countriesByCode["JP"]?.primaryStatus, "wishlist")
        XCTAssertEqual(store.map?.stats.wishlistCountries, 1)
    }

    private static let mapJSON = """
    {
      "countries": [{
        "code": "DK", "name": "Denmark", "continent": "Europe",
        "visited": true, "lived": false, "wishlist": false,
        "primaryStatus": "visited", "visitCount": 1, "residenceCount": 0,
        "visits": [], "updatedAt": "2026-09-14T12:00:00Z"
      }],
      "stats": {
        "countriesVisited": 1, "countriesLivedIn": 0, "wishlistCountries": 0,
        "worldTotal": 195, "worldExploredPercentage": 0.51,
        "continentsVisited": 1, "continentTotal": 6,
        "continentProgress": [{"name": "Europe", "visited": 1, "total": 44}]
      },
      "updatedAt": "2026-09-14T12:00:00Z"
    }
    """
}

private actor FakeTravelMapService: TravelMapServicing {
    private var wishlist = false
    private var updatedCodes: [String] = []

    func countryCatalog() async throws -> CountryCatalogResponse {
        CountryCatalogResponse(
            definition: "UN member states",
            worldTotal: 195,
            continentTotal: 6,
            continents: ["Europe", "Asia"],
            countries: [
                CountryCatalogEntry(
                    code: "DK", alpha3: "DNK", numericCode: "208", name: "Denmark",
                    continent: "Europe", countsTowardWorldTotal: true
                ),
                CountryCatalogEntry(
                    code: "JP", alpha3: "JPN", numericCode: "392", name: "Japan",
                    continent: "Asia", countsTowardWorldTotal: true
                ),
            ]
        )
    }

    func travelMap() async throws -> TravelMapResponse {
        let countries = [denmark] + (wishlist ? [japanWishlist] : [])
        return TravelMapResponse(
            countries: countries,
            stats: TravelMapStats(
                countriesVisited: 1,
                countriesLivedIn: 0,
                wishlistCountries: wishlist ? 1 : 0,
                worldTotal: 195,
                worldExploredPercentage: 0.51,
                continentsVisited: 1,
                continentTotal: 6,
                continentProgress: [ContinentProgress(name: "Europe", visited: 1, total: 44)]
            ),
            updatedAt: "2026-09-14T12:00:00Z"
        )
    }

    func updateCountry(_ code: String, update: CountryStateUpdate) async throws -> TravelMapCountry {
        updatedCodes.append(code)
        wishlist = true
        return japanWishlist
    }

    func updates() -> [String] { updatedCodes }

    private var denmark: TravelMapCountry {
        TravelMapCountry(
            code: "DK", name: "Denmark", continent: "Europe", visited: true,
            lived: false, wishlist: false, primaryStatus: "visited", visitCount: 1,
            residenceCount: 0, visits: [], updatedAt: "2026-09-14T12:00:00Z"
        )
    }

    private var japanWishlist: TravelMapCountry {
        TravelMapCountry(
            code: "JP", name: "Japan", continent: "Asia", visited: false,
            lived: false, wishlist: true, primaryStatus: "wishlist", visitCount: 0,
            residenceCount: 0, visits: [], updatedAt: "2026-09-14T12:00:00Z"
        )
    }
}
