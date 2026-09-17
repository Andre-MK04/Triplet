import SwiftUI

struct NativeWatchRouteUpdate: Encodable, Sendable {
    let originAirports: [String]
    let destinationAirports: [String]
    let destinationCountries: [String]
    let destinationRegions: [String]
    let destinationContinents: [String]
    let tripPlan: String
    let routeStops: [String]?

    enum CodingKeys: CodingKey { case originAirports, destinationAirports, destinationCountries, destinationRegions, destinationContinents, tripPlan, routeStops, returnOriginAirports }
    func encode(to encoder: any Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(originAirports, forKey: .originAirports)
        try c.encode(destinationAirports, forKey: .destinationAirports)
        try c.encode(destinationCountries, forKey: .destinationCountries)
        try c.encode(destinationRegions, forKey: .destinationRegions)
        try c.encode(destinationContinents, forKey: .destinationContinents)
        try c.encode(tripPlan, forKey: .tripPlan)
        // Explicit null clears an old ordered chain when a region is chosen.
        if let routeStops { try c.encode(routeStops, forKey: .routeStops) }
        else { try c.encodeNil(forKey: .routeStops) }
        // Route edits choose a new destination scope; clear an old return-city constraint.
        try c.encodeNil(forKey: .returnOriginAirports)
    }
}

struct WatchRouteEditor: View {
    let watch: NativeWatchDetail
    let service: any WatchManagementServicing
    let originLimit: Int
    let save: (NativeWatchRouteUpdate) async -> String?
    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var origins: [String]
    @State private var places: [FlightPlaceResult]
    @State private var shape: String
    @State private var airportQuery = ""
    @State private var placeQuery = ""
    @State private var airports: [AirportResult] = []
    @State private var placeResults: [FlightPlaceResult] = []
    @State private var searchingAirport = false
    @State private var searchingPlace = false
    @State private var busy = false
    @State private var error: String?
    @State private var saved = false

    init(watch: NativeWatchDetail, service: any WatchManagementServicing, originLimit: Int,
         save: @escaping (NativeWatchRouteUpdate) async -> String?) {
        self.watch = watch; self.service = service; self.originLimit = originLimit; self.save = save
        _origins = State(initialValue: watch.originAirports)
        _shape = State(initialValue: watch.tripPlan)
        let scope: [(String, String)]
        if let stops = watch.routeStops, watch.tripPlan == "multi_city" {
            scope = stops.map { ("city", $0) }
        } else {
            scope = (watch.destinationAirports ?? []).map { ("airport", $0) } +
                watch.destinationCountries.map { ("country", $0) } +
                watch.destinationRegions.map { ("region", $0) } +
                watch.destinationContinents.map { ("continent", $0) }
        }
        _places = State(initialValue: scope.map { kind, code in
            FlightPlaceResult(code: code, kind: kind, name: code, subtitle: kind.capitalized,
                              city: nil, countryCode: nil, countryName: nil, continent: nil,
                              searchCodes: kind == "airport" || kind == "city" ? [code] : [])
        })
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Origin airports · up to \(originLimit)") {
                    ForEach(origins, id: \.self) { code in
                        HStack {
                            Text(code).monospaced()
                            Spacer()
                            Button("Remove \(code)", systemImage: "minus.circle") { origins.removeAll { $0 == code } }
                                .labelStyle(.iconOnly)
                        }
                    }
                    TextField("Search origin city, airport or IATA", text: $airportQuery).autocorrectionDisabled()
                    if searchingAirport { ProgressView("Finding airports…") }
                    if airportQuery.count >= 2, !searchingAirport, airports.isEmpty {
                        Text("No airport matches. Try the city name or IATA code.").font(.caption).foregroundStyle(FarelinColor.mist)
                    }
                    ForEach(airports.filter { !origins.contains($0.iataCode) }) { airport in
                        Button {
                            guard origins.count < originLimit else {
                                error = "Your current plan allows up to \(originLimit) origin airports."; return
                            }
                            origins.append(airport.iataCode); airportQuery = ""; airports = []
                        } label: {
                            VStack(alignment: .leading) {
                                Text("\(airport.name) · \(airport.iataCode)")
                                Text(airport.countryName).font(.caption).foregroundStyle(FarelinColor.mist)
                            }
                        }
                    }
                }
                Section("Trip shape") {
                    Picker("Journey", selection: $shape) {
                        Text("Return").tag("return")
                        Text("Open-jaw").tag("open_jaw")
                        Text("Multi-city").tag("multi_city")
                    }
                    Text("Choose cities in order, or a region/country for the engine to explore using observed fares.")
                        .font(.caption).foregroundStyle(FarelinColor.mist)
                }
                Section(shape == "multi_city" ? "Cities in order or region" : "Destinations") {
                    ForEach(places) { place in
                        HStack {
                            VStack(alignment: .leading) {
                                Text(place.name)
                                Text(place.subtitle).font(.caption).foregroundStyle(FarelinColor.mist)
                            }
                            Spacer()
                            Button("Remove \(place.name)", systemImage: "minus.circle") { places.removeAll { $0.id == place.id } }
                                .labelStyle(.iconOnly)
                        }
                    }
                    .onMove { places.move(fromOffsets: $0, toOffset: $1) }
                    TextField("Search cities, regions or countries", text: $placeQuery).autocorrectionDisabled()
                    if searchingPlace { ProgressView("Finding places…") }
                    if placeQuery.count >= 2, !searchingPlace, placeResults.isEmpty {
                        Text("No place matches. Try a city, country or region name.").font(.caption).foregroundStyle(FarelinColor.mist)
                    }
                    ForEach(placeResults.filter { p in !places.contains(where: { $0.id == p.id }) }) { place in
                        Button {
                            guard places.count < 6 else { error = "Choose up to six destinations."; return }
                            places.append(place); placeQuery = ""; placeResults = []
                        } label: {
                            VStack(alignment: .leading) {
                                Text(place.name)
                                Text(place.subtitle).font(.caption).foregroundStyle(FarelinColor.mist)
                            }
                        }
                    }
                }
                if let error { Section { Text(error).font(.footnote).foregroundStyle(FarelinColor.coral) } }
            }
            .navigationTitle("Edit route")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() }.disabled(busy) }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { Task { await submit() } }.disabled(busy || origins.isEmpty || origins.count > originLimit)
                }
                ToolbarItem(placement: .bottomBar) { EditButton() }
            }
            .interactiveDismissDisabled(busy)
            .sensoryFeedback(.selection, trigger: origins.count)
            .sensoryFeedback(.selection, trigger: places.count)
            .sensoryFeedback(.success, trigger: saved)
            .animation(reduceMotion ? nil : .easeOut(duration: 0.18), value: origins)
            .animation(reduceMotion ? nil : .easeOut(duration: 0.18), value: places.map(\.id))
            .task(id: airportQuery) { await searchAirports() }
            .task(id: placeQuery) { await searchPlaces() }
        }
    }

    private func searchAirports() async {
        let query = airportQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        guard query.count >= 2 else { airports = []; return }
        searchingAirport = true
        defer { searchingAirport = false }
        do {
            try await Task.sleep(for: .milliseconds(300))
            let results = try await service.watchAirports(query: query)
            try Task.checkCancellation()
            airports = results
        } catch is CancellationError {} catch { self.error = "Airport suggestions could not load. Please try again." }
    }
    private func searchPlaces() async {
        let query = placeQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        guard query.count >= 2 else { placeResults = []; return }
        searchingPlace = true
        defer { searchingPlace = false }
        do {
            try await Task.sleep(for: .milliseconds(300))
            let results = try await service.watchPlaces(query: query)
            try Task.checkCancellation()
            placeResults = results
        } catch is CancellationError {} catch { self.error = "Place suggestions could not load. Please try again." }
    }
    private func submit() async {
        guard !busy else { return }
        let cities = places.filter { ["airport", "city"].contains($0.kind) }
        let broad = places.filter { !["airport", "city"].contains($0.kind) }
        if shape == "multi_city", broad.isEmpty, cities.count < 2 {
            error = "Choose at least two cities, or a country/region to explore."; return
        }
        if shape == "multi_city", !cities.isEmpty, !broad.isEmpty {
            error = "Choose an ordered city route or a geographic region, not both."; return
        }
        let update = NativeWatchRouteUpdate(originAirports: origins,
            destinationAirports: cities.flatMap(\.searchCodes),
            destinationCountries: broad.filter { $0.kind == "country" }.map(\.code),
            destinationRegions: broad.filter { $0.kind == "region" }.map(\.code),
            destinationContinents: broad.filter { $0.kind == "continent" }.map(\.code), tripPlan: shape,
            routeStops: shape == "multi_city" && !cities.isEmpty ? cities.map(\.code) : nil)
        busy = true; error = nil
        error = await save(update)
        saved = error == nil; busy = false
    }
}
