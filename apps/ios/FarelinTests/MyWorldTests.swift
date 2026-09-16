import MapKit
import Metal
import SceneKit
import XCTest
@testable import Farelin

@MainActor
final class MyWorldTests: XCTestCase {
    func testPolygonHolesAndDateLineAreNotSelectedAsSolidLand() {
        let polygon = EarthCountryGeometry.Polygon(code: "XX", selectable: true,
            points: [CGPoint(x: 0, y: 0), CGPoint(x: 10, y: 0), CGPoint(x: 10, y: 10), CGPoint(x: 0, y: 10)],
            holes: [[CGPoint(x: 4, y: 4), CGPoint(x: 6, y: 4), CGPoint(x: 6, y: 6), CGPoint(x: 4, y: 6)]])
        XCTAssertTrue(polygon.contains(latitude: 2, longitude: 2))
        XCTAssertFalse(polygon.contains(latitude: 5, longitude: 5))
        let seam = EarthCountryGeometry.Polygon(code: "YY", selectable: true,
            points: EarthCountryGeometry.unwrapRing([[179, -10], [-179, -10], [-179, 10], [179, 10], [179, -10]]))
        XCTAssertTrue(seam.contains(latitude: 0, longitude: -179.5))
        XCTAssertTrue(seam.contains(latitude: 0, longitude: 179.5))
        XCTAssertFalse(seam.contains(latitude: 0, longitude: 0))
    }
    func testPolarAndWorldwideCountryGeometryRegression() {
        let geography = EarthCountryGeometry.load(alpha3ToCode: [
            "SVN": "SI", "DNK": "DK", "MEX": "MX", "JPN": "JP",
            "AUS": "AU", "ARG": "AR", "ATA": "AQ", "FJI": "FJ",
        ])
        for (lat, lon, code) in [(46.05, 14.51, "SI"), (55.68, 12.57, "DK"),
                                 (19.43, -99.13, "MX"), (35.68, 139.69, "JP"),
                                 (-25.0, 135.0, "AU"), (-34.6, -58.38, "AR"),
                                 (-85.0, 0.0, "AQ"), (-85.0, 179.9, "AQ"), (-85.0, -179.9, "AQ")] {
            XCTAssertEqual(geography.country(at: lat, longitude: lon), code, "\(lat), \(lon)")
        }
        XCTAssertNil(geography.country(at: 0, longitude: -140))
    }

    func testNaiveBackendDateDoesNotLeakISOTimestampIntoUI() {
        XCTAssertEqual(FarelinSearchFormat.shortDate("2026-10-07T09:00:00"), "7 Oct")
    }

    func testSceneKitSphereCoordinateConvention() throws {
        let node = SCNNode(geometry: SCNSphere(radius: 1))
        let scene = SCNScene()
        scene.rootNode.addChildNode(node)
        let camera = SCNNode()
        camera.camera = SCNCamera()
        camera.position = SCNVector3(0, 0, 3)
        scene.rootNode.addChildNode(camera)
        let renderer = SCNRenderer(device: MTLCreateSystemDefaultDevice())
        renderer.scene = scene
        renderer.pointOfView = camera
        for rotation in [SCNVector3Zero, SCNVector3(0, Float.pi / 2, 0), SCNVector3(Float.pi / 4, 0, 0)] {
            node.eulerAngles = rotation
            _ = renderer.snapshot(atTime: 0, with: CGSize(width: 360, height: 360), antialiasingMode: .none)
            let hit = try XCTUnwrap(renderer.hitTest(CGPoint(x: 180, y: 180), options: nil).first)
            let uv = hit.textureCoordinates(withMappingChannel: 0)
            let coordinate = EarthCountryGeometry.coordinate(at: hit.localCoordinates)
            XCTAssertEqual(coordinate.longitude, Double(uv.x) * 360 - 180, accuracy: 0.5)
            XCTAssertEqual(coordinate.latitude, 90 - Double(uv.y) * 180, accuracy: 0.5)
        }
    }
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

    func testSphereTextureGeometrySelectsCountriesByCoordinates() {
        let geography = EarthCountryGeometry.load(alpha3ToCode: [
            "FRA": "FR", "DNK": "DK", "JPN": "JP", "FJI": "FJ",
        ])

        XCTAssertGreaterThan(geography.polygons.count, 4)
        XCTAssertEqual(geography.country(at: 48.86, longitude: 2.35), "FR")
        XCTAssertEqual(geography.country(at: 55.68, longitude: 12.57), "DK")
        XCTAssertEqual(geography.country(at: 35.68, longitude: 139.69), "JP")
        XCTAssertNil(geography.country(at: 0, longitude: 0))
    }

    func testUnselectableTerritoryStillDrawsAsLand() {
        let geography = EarthCountryGeometry.load(alpha3ToCode: ["FRA": "FR"])
        XCTAssertTrue(geography.polygons.contains { $0.code == "GL" })
        XCTAssertNil(geography.country(at: 64.18, longitude: -51.72))
    }

    func testTextureRendersAtBoundedResolution() throws {
        let url = try XCTUnwrap(Bundle.main.url(forResource: "NaturalEarthCountries", withExtension: "geojson"))
        let features = try MKGeoJSONDecoder().decode(Data(contentsOf: url))
        var codes: [String: String] = ["FRA": "FR", "NOR": "NO"]
        for case let feature as MKGeoJSONFeature in features {
            guard let properties = feature.properties,
                  let values = try JSONSerialization.jsonObject(with: properties) as? [String: Any],
                  let alpha3 = values["ADM0_A3"] as? String,
                  let iso2 = values["ISO_A2"] as? String,
                  iso2.count == 2, iso2 != "-99" else { continue }
            codes[alpha3] = iso2
        }
        let geography = EarthCountryGeometry.load(alpha3ToCode: codes)
        XCTAssertGreaterThan(geography.polygons.count, 180)
        let texture = geography.texture(states: ["FR": "visited"], selected: "FR", light: false)
        XCTAssertEqual(texture.size, CGSize(width: 2048, height: 1024))
        let attachment = XCTAttachment(image: texture)
        attachment.name = "Farelin Earth texture — France visited"
        attachment.lifetime = .keepAlways
        add(attachment)

        let scene = SCNScene()
        let sphere = SCNSphere(radius: 1)
        sphere.segmentCount = 144
        let material = SCNMaterial()
        material.lightingModel = .physicallyBased
        material.roughness.contents = NSNumber(value: 0.85)
        material.metalness.contents = NSNumber(value: 0.03)
        material.diffuse.contents = texture
        sphere.firstMaterial = material
        let earth = SCNNode(geometry: sphere)
        earth.eulerAngles = SCNVector3(0.45, -0.08, 0)
        let gridSphere = SCNSphere(radius: 1.012)
        gridSphere.segmentCount = 48
        let gridMaterial = SCNMaterial()
        gridMaterial.lightingModel = .constant
        gridMaterial.fillMode = .lines
        gridMaterial.diffuse.contents = UIColor(red: 0.09, green: 0.15, blue: 0.19, alpha: 1)
        gridMaterial.transparency = 0.18
        gridMaterial.writesToDepthBuffer = false
        gridSphere.firstMaterial = gridMaterial
        earth.addChildNode(SCNNode(geometry: gridSphere))
        scene.rootNode.addChildNode(earth)
        let camera = SCNNode()
        camera.camera = SCNCamera()
        camera.camera?.fieldOfView = 48
        camera.position = SCNVector3(0, 0, 3.25)
        scene.rootNode.addChildNode(camera)
        let key = SCNNode()
        key.light = SCNLight()
        key.light?.type = .directional
        key.light?.intensity = 1000
        key.eulerAngles = SCNVector3(-0.45, -0.55, 0)
        scene.rootNode.addChildNode(key)
        let fill = SCNNode()
        fill.light = SCNLight()
        fill.light?.type = .ambient
        fill.light?.intensity = 550
        scene.rootNode.addChildNode(fill)
        scene.background.contents = UIColor(red: 0.035, green: 0.060, blue: 0.083, alpha: 1)
        let renderer = SCNRenderer(device: MTLCreateSystemDefaultDevice())
        renderer.scene = scene
        renderer.pointOfView = camera
        let globeImage = renderer.snapshot(atTime: 0, with: CGSize(width: 360, height: 360),
                                           antialiasingMode: .multisampling2X)
        let globeAttachment = XCTAttachment(image: globeImage)
        globeAttachment.name = "Farelin Earth sphere — rendered in simulator"
        globeAttachment.lifetime = .keepAlways
        add(globeAttachment)
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

    func testCountryBrowserReturnsEntireAlphabetizedCatalogBeforeSearch() async {
        let store = MyWorldStore(service: FakeTravelMapService())
        await store.load()
        XCTAssertGreaterThan(store.filteredCatalog.count, 24)
        XCTAssertEqual(store.filteredCatalog.first?.name, "Country 00")
        XCTAssertEqual(store.filteredCatalog.last?.name, "Japan")
        store.query = "jap"
        XCTAssertEqual(store.filteredCatalog.map(\.name), ["Japan"])
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
            countries: (0..<30).map { number in
                CountryCatalogEntry(
                    code: String(format: "T%02d", number), alpha3: "TST", numericCode: "000",
                    name: String(format: "Country %02d", number), continent: "Europe",
                    countsTowardWorldTotal: false
                )
            } + [
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
