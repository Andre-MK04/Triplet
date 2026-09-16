import XCTest
@testable import Farelin

final class NativeReleaseTests: XCTestCase {
    func testExportRoundTripsStructuredJSON() throws {
        let data = Data(#"{"account":{"email":"private@example.com"},"usage":[1,true,null],"profile":null}"#.utf8)
        let document = try JSONDecoder().decode(AccountExport.self, from: data)
        let encoded = try JSONEncoder().encode(document)
        let original = try JSONSerialization.jsonObject(with: data) as! NSDictionary
        let roundTrip = try JSONSerialization.jsonObject(with: encoded) as! NSDictionary
        XCTAssertEqual(original, roundTrip)
    }

    func testAppleNonceHashMatchesStandardSHA256() {
        XCTAssertEqual(NativeIdentityButtons.hashedNonce("abc"),
                       "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    }

    func testNotificationDoesNotAcceptArbitraryURL() {
        XCTAssertNil(NotificationDestination.parse(watchId: "https://attacker.example"))
        XCTAssertNil(NotificationDestination.parse(watchId: "../auth/me"))
        XCTAssertNil(NotificationDestination.parse(watchId: nil))
    }

    func testNotificationAcceptsWatchUUIDOnly() {
        let id = "AE158B49-278F-4C26-8DD4-2E9CBE6D95AC"
        XCTAssertEqual(NotificationDestination.parse(watchId: id), .watch(id.lowercased()))
    }

    func testWatchEditsDoNotReplaceDestinationCriteria() throws {
        let update = NativeWatchUpdate(name: "Nordics", startDate: "2026-10-01", endDate: "2026-10-31",
            minTripLengthDays: 4, maxTripLengthDays: 7, maxBudget: 300, maxGroundTransferHours: 4,
            frequency: "weekly", triggerMode: "any", directOnly: false, includeBaggage: false)
        let json = try JSONSerialization.jsonObject(with: JSONEncoder().encode(update)) as! [String: Any]
        XCTAssertEqual(json["frequency"] as? String, "weekly")
        for key in ["destinationRegions", "destinationCountries", "routeStops", "originAirports", "tripPlan"] {
            XCTAssertNil(json[key], "A partial watch edit must preserve \(key)")
        }
    }

    func testWatchDetailsKeepBroadDestinationScope() throws {
        let json = #"{"id":"watch","name":"Nordics","originAirports":["CPH"],"destinationAirports":null,"destinationCountries":[],"destinationRegions":["nordics"],"destinationContinents":[],"tripPlan":"multi_city","routeStops":null,"startDate":"2026-10-01","endDate":"2026-10-31","minTripLengthDays":4,"maxTripLengthDays":7,"maxBudget":400,"maxGroundTransferHours":4,"frequency":"weekly","triggerMode":"any","directOnly":false,"includeBaggage":false,"isActive":true}"#
        let detail = try JSONDecoder().decode(NativeWatchDetail.self, from: Data(json.utf8))
        XCTAssertEqual(detail.destinationDescription, "nordics")
        XCTAssertEqual(detail.tripPlan, "multi_city")
    }

    func testRegionRouteEditClearsOldOrderedStopsAndReturnCity() throws {
        let update = NativeWatchRouteUpdate(originAirports: ["CPH"], destinationAirports: [],
            destinationCountries: [], destinationRegions: ["nordics"], destinationContinents: [],
            tripPlan: "multi_city", routeStops: nil)
        let json = try JSONSerialization.jsonObject(with: JSONEncoder().encode(update)) as! [String: Any]
        XCTAssertTrue(json["routeStops"] is NSNull)
        XCTAssertTrue(json["returnOriginAirports"] is NSNull)
        XCTAssertEqual(json["destinationRegions"] as? [String], ["nordics"])
        XCTAssertNil(json["frequency"], "Route edits must preserve watch frequency")
    }

    func testOrderedWatchRouteKeepsCitySequence() throws {
        let update = NativeWatchRouteUpdate(originAirports: ["CPH"], destinationAirports: ["HEL", "STO"],
            destinationCountries: [], destinationRegions: [], destinationContinents: [],
            tripPlan: "multi_city", routeStops: ["HEL", "STO"])
        let json = try JSONSerialization.jsonObject(with: JSONEncoder().encode(update)) as! [String: Any]
        XCTAssertEqual(json["routeStops"] as? [String], ["HEL", "STO"])
    }
}
