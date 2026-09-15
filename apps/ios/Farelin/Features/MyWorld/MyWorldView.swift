import MapKit
import SwiftUI

struct MyWorldView: View {
    let store: MyWorldStore
    let opportunities: OpportunityStore
    let tripDetailService: any TripDetailServicing
    let reauthenticate: (@MainActor @Sendable () async -> Bool)?
    let homeCoordinate: CLLocationCoordinate2D?
    let isActive: Bool
    let planTrip: (CountryCatalogEntry) -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.colorScheme) private var colorScheme
    @State private var autoRotate = true
    @State private var rotationTick = 0
    @State private var appeared = false

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 20) {
                    introduction
                    if store.isLoading, store.map == nil {
                        loadingState
                    } else if let map = store.map {
                        globe(map)
                        stats(map.stats)
                        countryBrowser
                    } else {
                        errorState
                    }
                }
                .padding(.horizontal, 18)
                .padding(.bottom, 36)
            }
            .background(Color(.systemBackground))
            .navigationTitle("My World")
            .refreshable { await store.load(force: true) }
            .task { await store.load() }
            .task { await opportunities.load() }
            .task(id: autoRotate && isActive) {
                guard autoRotate, isActive, !reduceMotion, !ProcessInfo.processInfo.isLowPowerModeEnabled else { return }
                while !Task.isCancelled {
                    try? await Task.sleep(for: .seconds(2.8))
                    guard !Task.isCancelled else { return }
                    rotationTick += 1
                }
            }
            .onAppear {
                if reduceMotion || ProcessInfo.processInfo.isLowPowerModeEnabled {
                    autoRotate = false
                }
                withAnimation(reduceMotion ? nil : .easeOut(duration: 0.55)) {
                    appeared = true
                }
            }
            .sheet(isPresented: Binding(
                get: { store.selectedCode != nil },
                set: { if !$0 { store.dismissSelection() } }
            )) {
                if let metadata = store.selectedCatalogEntry {
                    CountrySheet(
                        metadata: metadata,
                        country: store.selectedCountry,
                        trips: opportunities.feed?.trips.filter { $0.destination?.countryCode == metadata.code } ?? [],
                        boardLoaded: opportunities.feed != nil,
                        tripDetailService: tripDetailService,
                        reauthenticate: reauthenticate,
                        busy: store.updatingCode == metadata.code,
                        update: { change in await store.updateSelected(change) },
                        planTrip: {
                            store.dismissSelection()
                            planTrip(metadata)
                        }
                    )
                    .presentationDetents([.medium, .large])
                    .presentationDragIndicator(.visible)
                }
            }
            .sensoryFeedback(.selection, trigger: store.selectedCode)
        }
    }

    private var introduction: some View {
        VStack(alignment: .leading, spacing: 7) {
            Text("YOUR TRAVEL MAP")
                .font(.caption2.monospaced().weight(.semibold))
                .tracking(1.4)
                .foregroundStyle(FarelinColor.mint)
            Text("The places that made you.")
                .font(.system(size: 32, weight: .bold, design: .rounded))
                .tracking(-0.8)
            Text("Rotate the globe, choose a country, and keep your travel history in sync with Farelin on the web.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .lineSpacing(3)
        }
        .padding(.top, 8)
        .opacity(appeared ? 1 : 0)
        .offset(y: appeared ? 0 : 8)
    }

    private func globe(_ map: TravelMapResponse) -> some View {
        ZStack(alignment: .topTrailing) {
            InteractiveTravelGlobe(
                countryStates: Dictionary(uniqueKeysWithValues: map.countries.map { ($0.code, $0.primaryStatus) }),
                countryCodesByAlpha3: Dictionary(uniqueKeysWithValues: store.catalog.map { ($0.alpha3, $0.code) }),
                selectedCode: store.selectedCode,
                homeCoordinate: homeCoordinate,
                rotationTick: rotationTick,
                colorScheme: colorScheme,
                onSelect: store.select,
                onInteract: { autoRotate = false }
            )
            .frame(height: 410)
            .clipShape(.rect(cornerRadius: 28))
            .overlay {
                RoundedRectangle(cornerRadius: 28)
                    .stroke(Color(.separator).opacity(0.45), lineWidth: 0.5)
            }
            .accessibilityLabel("Interactive travel globe")
            .accessibilityHint("Drag to rotate, pinch to zoom, or use the country list below.")

            Button {
                autoRotate.toggle()
            } label: {
                Image(systemName: autoRotate ? "pause.fill" : "play.fill")
                    .font(.caption.weight(.bold))
                    .frame(width: 38, height: 38)
                    .background(.ultraThinMaterial, in: Circle())
            }
            .padding(12)
            .accessibilityLabel(autoRotate ? "Pause globe rotation" : "Resume globe rotation")

            VStack {
                Spacer()
                HStack(spacing: 7) {
                    legendDot(FarelinColor.mint, "Visited")
                    legendDot(FarelinColor.coral, "Lived")
                    legendDot(FarelinColor.gold, "Wishlist")
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 9)
                .background(.ultraThinMaterial, in: Capsule())
                .padding(12)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .scaleEffect(appeared ? 1 : 0.97)
        .opacity(appeared ? 1 : 0)
    }

    private func legendDot(_ color: Color, _ label: String) -> some View {
        HStack(spacing: 4) {
            Circle().fill(color).frame(width: 7, height: 7)
            Text(label).font(.system(size: 9, weight: .semibold, design: .monospaced))
        }
    }

    private func stats(_ stats: TravelMapStats) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("YOUR FOOTPRINT")
                .font(.caption2.monospaced().weight(.semibold))
                .tracking(1.2)
                .foregroundStyle(.secondary)
            HStack(spacing: 10) {
                WorldStat(value: "\(stats.countriesVisited)", label: "Countries")
                WorldStat(value: String(format: "%.1f%%", stats.worldExploredPercentage), label: "World")
                WorldStat(value: "\(stats.continentsVisited)", label: "Continents")
                WorldStat(value: "\(stats.wishlistCountries)", label: "Wishlist")
            }
        }
        .contentTransition(.numericText())
    }

    private var countryBrowser: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("FIND A COUNTRY")
                .font(.caption2.monospaced().weight(.semibold))
                .tracking(1.2)
                .foregroundStyle(.secondary)
            Label {
                TextField("Country name or code", text: Binding(
                    get: { store.query },
                    set: { store.query = $0 }
                ))
                    .textInputAutocapitalization(.words)
                    .autocorrectionDisabled()
            } icon: {
                Image(systemName: "magnifyingglass").foregroundStyle(.secondary)
            }
            .padding(.horizontal, 14)
            .frame(minHeight: 48)
            .background(Color(.secondarySystemBackground), in: .rect(cornerRadius: 14))

            LazyVStack(spacing: 0) {
                ForEach(store.filteredCatalog) { country in
                    Button {
                        store.select(country.code)
                    } label: {
                        HStack(spacing: 12) {
                            Circle()
                                .fill(statusColor(store.countriesByCode[country.code]?.primaryStatus))
                                .frame(width: 9, height: 9)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(country.name)
                                    .font(.subheadline.weight(.semibold))
                                    .foregroundStyle(.primary)
                                Text("\(country.continent) · \(country.code)")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(.tertiary)
                        }
                        .padding(.vertical, 12)
                    }
                    .buttonStyle(.plain)
                    if country.id != store.filteredCatalog.last?.id { Divider() }
                }
            }
            .padding(.horizontal, 16)
            .background(Color(.secondarySystemBackground), in: .rect(cornerRadius: 20))
        }
    }

    private var loadingState: some View {
        VStack(spacing: 14) {
            ProgressView().tint(FarelinColor.mint)
            Text("Drawing your world…")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, minHeight: 360)
        .farelinCard()
    }

    private var errorState: some View {
        VStack(alignment: .leading, spacing: 13) {
            Label("Your world could not load", systemImage: "globe.badge.chevron.backward")
                .font(.headline)
            Text(store.errorMessage ?? "Check your connection and try again.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Button("Try again") { Task { await store.load(force: true) } }
                .buttonStyle(FarelinPrimaryButtonStyle())
        }
        .farelinCard()
    }

    private func statusColor(_ status: String?) -> Color {
        switch status {
        case "lived": FarelinColor.coral
        case "visited": FarelinColor.mint
        case "wishlist": FarelinColor.gold
        default: Color.secondary.opacity(0.35)
        }
    }
}

private struct WorldStat: View {
    let value: String
    let label: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(value)
                .font(.headline.monospacedDigit())
            Text(label)
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color(.secondarySystemBackground), in: .rect(cornerRadius: 15))
        .accessibilityElement(children: .combine)
    }
}

private struct CountrySheet: View {
    let metadata: CountryCatalogEntry
    let country: TravelMapCountry?
    let trips: [SearchTrip]
    let boardLoaded: Bool
    let tripDetailService: any TripDetailServicing
    let reauthenticate: (@MainActor @Sendable () async -> Bool)?
    let busy: Bool
    let update: (CountryStateUpdate) async -> Void
    let planTrip: () -> Void

    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    VStack(alignment: .leading, spacing: 5) {
                        Text("\(metadata.continent.uppercased()) · \(metadata.code)")
                            .font(.caption2.monospaced().weight(.semibold))
                            .tracking(1.2)
                            .foregroundStyle(FarelinColor.mint)
                        Text(metadata.name)
                            .font(.system(size: 34, weight: .bold, design: .rounded))
                        Text(statusLabel)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.secondary)
                    }

                    VStack(spacing: 0) {
                        stateButton(
                            title: country?.visited == true ? "Visited" : "Mark as visited",
                            symbol: "checkmark.circle.fill",
                            selected: country?.visited == true,
                            update: CountryStateUpdate(visited: country?.visited != true)
                        )
                        Divider()
                        stateButton(
                            title: country?.lived == true ? "Lived here" : "I lived here",
                            symbol: "house.fill",
                            selected: country?.lived == true,
                            update: CountryStateUpdate(lived: country?.lived != true)
                        )
                        Divider()
                        stateButton(
                            title: country?.wishlist == true ? "On your wishlist" : "Add to wishlist",
                            symbol: "heart.fill",
                            selected: country?.wishlist == true,
                            update: CountryStateUpdate(wishlist: country?.wishlist != true)
                        )
                    }
                    .padding(.horizontal, 16)
                    .background(Color(.secondarySystemBackground), in: .rect(cornerRadius: 20))

                    VStack(alignment: .leading, spacing: 10) {
                        Text("OBSERVED RETURNS")
                            .font(.caption2.monospaced().weight(.semibold))
                            .foregroundStyle(FarelinColor.mint)
                        if trips.isEmpty {
                            Text(boardLoaded
                                 ? "No return fares to this country are in your current opportunity board. This is not proof that there are no flights; explore a wider search."
                                 : "Your personal observed-fare board is still loading or unavailable. Explore a wider search below.")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        } else {
                            Text("\(trips.count) observed \(trips.count == 1 ? "trip" : "trips") from your airports. Check final prices with the provider.")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            ForEach(trips.prefix(3)) { trip in
                                NavigationLink {
                                    TripDetailView(trip: trip, service: tripDetailService, reauthenticate: reauthenticate)
                                } label: {
                                    HStack {
                                        VStack(alignment: .leading) {
                                            Text(trip.routeTitle).font(.subheadline.weight(.semibold))
                                            Text("\(FarelinSearchFormat.shortDate(trip.outboundFlight.departureDateTime))–\(FarelinSearchFormat.shortDate(trip.returnFlight.departureDateTime))")
                                                .font(.caption).foregroundStyle(.secondary)
                                        }
                                        Spacer()
                                        Text(FarelinSearchFormat.priceHeadline(trip)).font(.subheadline.weight(.semibold))
                                    }
                                }
                                .buttonStyle(.plain)
                                if let url = trip.checkPriceURL {
                                    Link("Check price with provider ↗", destination: url)
                                        .font(.caption.weight(.semibold))
                                        .foregroundStyle(FarelinColor.mint)
                                }
                            }
                        }
                    }
                    .farelinCard()

                    if let country, !country.visits.isEmpty {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("MEMORIES")
                                .font(.caption2.monospaced().weight(.semibold))
                                .tracking(1.1)
                                .foregroundStyle(.secondary)
                            ForEach(country.visits) { visit in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(visit.kind == "lived" ? "Lived here" : "Visit")
                                        .font(.subheadline.weight(.semibold))
                                    Text(visitPeriod(visit))
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    if let note = visit.note, !note.isEmpty {
                                        Text(note).font(.caption).foregroundStyle(.secondary)
                                    }
                                }
                                .farelinCard()
                            }
                        }
                    }

                    Button("Find a trip to \(metadata.name)", action: planTrip)
                        .buttonStyle(FarelinPrimaryButtonStyle())
                }
                .padding(20)
            }
            .background(Color(.systemBackground))
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }

    private var statusLabel: String {
        switch country?.primaryStatus {
        case "lived": "Lived here"
        case "visited": "Visited"
        case "wishlist": "Wishlist"
        default: "Not mapped yet"
        }
    }

    private func stateButton(
        title: String,
        symbol: String,
        selected: Bool,
        update change: CountryStateUpdate
    ) -> some View {
        Button {
            Task { await update(change) }
        } label: {
            HStack {
                Image(systemName: symbol)
                    .foregroundStyle(selected ? FarelinColor.mint : .secondary)
                    .frame(width: 26)
                Text(title).foregroundStyle(.primary)
                Spacer()
                if busy {
                    ProgressView().controlSize(.small)
                } else if selected {
                    Image(systemName: "checkmark").foregroundStyle(FarelinColor.mint)
                }
            }
            .padding(.vertical, 15)
        }
        .buttonStyle(.plain)
        .disabled(busy)
    }

    private func visitPeriod(_ visit: CountryVisit) -> String {
        let start = visit.startDate ?? "Date not recorded"
        guard let end = visit.endDate else { return start }
        return "\(start) – \(end)"
    }
}

private struct InteractiveTravelGlobe: UIViewRepresentable {
    let countryStates: [String: String]
    let countryCodesByAlpha3: [String: String]
    let selectedCode: String?
    let homeCoordinate: CLLocationCoordinate2D?
    let rotationTick: Int
    let colorScheme: ColorScheme
    let onSelect: (String) -> Void
    let onInteract: () -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(onSelect: onSelect, onInteract: onInteract)
    }

    func makeUIView(context: Context) -> MKMapView {
        let map = MKMapView(frame: .zero)
        map.delegate = context.coordinator
        map.preferredConfiguration = MKStandardMapConfiguration(elevationStyle: .realistic, emphasisStyle: .muted)
        map.pointOfInterestFilter = .excludingAll
        map.showsCompass = true
        map.isPitchEnabled = true
        map.isRotateEnabled = true
        map.setCameraZoomRange(MKMapView.CameraZoomRange(minCenterCoordinateDistance: 900_000, maxCenterCoordinateDistance: 48_000_000), animated: false)
        map.camera = MKMapCamera(
            lookingAtCenter: CLLocationCoordinate2D(latitude: 26, longitude: 10),
            fromDistance: 34_000_000,
            pitch: 0,
            heading: 0
        )
        context.coordinator.installGeometry(on: map, countryCodesByAlpha3: countryCodesByAlpha3)
        let tap = UITapGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.didTapMap(_:)))
        tap.delegate = context.coordinator
        map.addGestureRecognizer(tap)
        let pan = UIPanGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.didInteract(_:)))
        pan.delegate = context.coordinator
        map.addGestureRecognizer(pan)
        let pinch = UIPinchGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.didInteract(_:)))
        pinch.delegate = context.coordinator
        map.addGestureRecognizer(pinch)
        return map
    }

    func updateUIView(_ map: MKMapView, context: Context) {
        context.coordinator.onSelect = onSelect
        context.coordinator.onInteract = onInteract
        context.coordinator.update(
            map: map,
            countryStates: countryStates,
            selectedCode: selectedCode,
            homeCoordinate: homeCoordinate,
            colorScheme: colorScheme
        )
        context.coordinator.rotate(map: map, tick: rotationTick)
    }

    @MainActor
    final class Coordinator: NSObject, MKMapViewDelegate, UIGestureRecognizerDelegate {
        var onSelect: (String) -> Void
        var onInteract: () -> Void
        private var stateByCode: [String: String] = [:]
        private var selectedCode: String?
        private var light = true
        private var lastStyleSignature = ""
        private var lastRotationTick = 0
        private var routeSignature = ""
        private var codeByOverlay: [ObjectIdentifier: String] = [:]
        private var overlaysByCode: [String: [MKPolygon]] = [:]

        init(onSelect: @escaping (String) -> Void, onInteract: @escaping () -> Void) {
            self.onSelect = onSelect
            self.onInteract = onInteract
        }

        func installGeometry(on map: MKMapView, countryCodesByAlpha3: [String: String]) {
            guard
                let url = Bundle.main.url(forResource: "NaturalEarthCountries", withExtension: "geojson"),
                let data = try? Data(contentsOf: url),
                let objects = try? MKGeoJSONDecoder().decode(data)
            else { return }

            var polygons: [MKPolygon] = []
            for object in objects {
                guard
                    let feature = object as? MKGeoJSONFeature,
                    let properties = feature.properties,
                    let json = try? JSONSerialization.jsonObject(with: properties) as? [String: Any],
                    let iso2 = json["ISO_A2"] as? String,
                    let alpha3 = json["ADM0_A3"] as? String,
                    let code = iso2.count == 2 && iso2 != "-99"
                        ? iso2
                        : countryCodesByAlpha3[alpha3],
                    code.count == 2,
                    countryCodesByAlpha3.values.contains(code)
                else { continue }
                for geometry in feature.geometry {
                    let shapes: [MKPolygon]
                    if let polygon = geometry as? MKPolygon {
                        shapes = [polygon]
                    } else if let multiPolygon = geometry as? MKMultiPolygon {
                        shapes = multiPolygon.polygons
                    } else {
                        continue
                    }
                    for polygon in shapes {
                        codeByOverlay[ObjectIdentifier(polygon)] = code
                        overlaysByCode[code, default: []].append(polygon)
                        polygons.append(polygon)
                    }
                }
            }
            map.addOverlays(polygons, level: .aboveRoads)
        }

        func update(
            map: MKMapView,
            countryStates: [String: String],
            selectedCode: String?,
            homeCoordinate: CLLocationCoordinate2D?,
            colorScheme: ColorScheme
        ) {
            let signature = [
                countryStates.keys.sorted().map { "\($0):\(countryStates[$0] ?? "")" }.joined(separator: ","),
                selectedCode ?? "none",
                colorScheme == .light ? "light" : "dark",
            ].joined(separator: "|")
            if signature != lastStyleSignature {
                lastStyleSignature = signature
                stateByCode = countryStates
                self.selectedCode = selectedCode
                light = colorScheme == .light
                for overlay in map.overlays {
                    guard let renderer = map.renderer(for: overlay) as? MKPolygonRenderer else { continue }
                    applyStyle(renderer, overlay: overlay)
                    renderer.setNeedsDisplay()
                }
            }
            updateRoutes(map: map, homeCoordinate: homeCoordinate)
        }

        func rotate(map: MKMapView, tick: Int) {
            guard tick != lastRotationTick else { return }
            lastRotationTick = tick
            let camera = map.camera
            var longitude = camera.centerCoordinate.longitude + 8
            if longitude > 180 { longitude -= 360 }
            camera.centerCoordinate = CLLocationCoordinate2D(
                latitude: camera.centerCoordinate.latitude,
                longitude: longitude
            )
            map.setCamera(camera, animated: true)
        }

        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            if let line = overlay as? MKGeodesicPolyline {
                let renderer = MKPolylineRenderer(polyline: line)
                renderer.strokeColor = UIColor(FarelinColor.mint).withAlphaComponent(0.78)
                renderer.lineWidth = 2
                renderer.lineDashPattern = [5, 5]
                return renderer
            }
            guard let polygon = overlay as? MKPolygon else { return MKOverlayRenderer(overlay: overlay) }
            let renderer = MKPolygonRenderer(polygon: polygon)
            applyStyle(renderer, overlay: overlay)
            return renderer
        }

        func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            guard annotation.title == "Farelin home" else { return nil }
            let identifier = "farelin-home"
            let view = mapView.dequeueReusableAnnotationView(withIdentifier: identifier) as? MKMarkerAnnotationView
                ?? MKMarkerAnnotationView(annotation: annotation, reuseIdentifier: identifier)
            view.annotation = annotation
            view.glyphImage = UIImage(systemName: "paperplane.fill")
            view.markerTintColor = UIColor(FarelinColor.coral)
            view.displayPriority = .required
            return view
        }

        @objc func didTapMap(_ recognizer: UITapGestureRecognizer) {
            guard let map = recognizer.view as? MKMapView else { return }
            let point = recognizer.location(in: map)
            let mapPoint = MKMapPoint(map.convert(point, toCoordinateFrom: map))
            var best: (code: String, area: Double)?
            for (code, polygons) in overlaysByCode {
                for polygon in polygons where polygon.boundingMapRect.contains(mapPoint) {
                    guard let renderer = map.renderer(for: polygon) as? MKPolygonRenderer else { continue }
                    let rendererPoint = renderer.point(for: mapPoint)
                    guard renderer.path?.contains(rendererPoint) == true else { continue }
                    let area = polygon.boundingMapRect.size.width * polygon.boundingMapRect.size.height
                    if best == nil || area < best!.area { best = (code, area) }
                }
            }
            if let code = best?.code { onSelect(code) }
        }

        @objc func didInteract(_ recognizer: UIGestureRecognizer) {
            if recognizer.state == .began { onInteract() }
        }

        func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer) -> Bool {
            true
        }

        private func applyStyle(_ renderer: MKPolygonRenderer, overlay: MKOverlay) {
            guard let code = codeByOverlay[ObjectIdentifier(overlay as AnyObject)] else { return }
            let selected = code == selectedCode
            let color: UIColor
            switch stateByCode[code] {
            case "lived": color = UIColor(FarelinColor.coral)
            case "visited": color = UIColor(FarelinColor.mint)
            case "wishlist": color = UIColor(FarelinColor.gold)
            default: color = light ? UIColor.systemGray3 : UIColor.systemGray
            }
            renderer.fillColor = color.withAlphaComponent(selected ? 0.86 : (stateByCode[code] == nil ? 0.16 : 0.58))
            renderer.strokeColor = selected
                ? UIColor(FarelinColor.mint)
                : UIColor.separator.withAlphaComponent(light ? 0.42 : 0.28)
            renderer.lineWidth = selected ? 1.6 : 0.45
        }

        private func updateRoutes(map: MKMapView, homeCoordinate: CLLocationCoordinate2D?) {
            let routeCodes = stateByCode
                .filter { $0.value == "wishlist" }
                .map(\.key)
                .sorted()
                .prefix(4)
            let signature = [
                homeCoordinate.map { "\($0.latitude),\($0.longitude)" } ?? "none",
                routeCodes.joined(separator: ","),
            ].joined(separator: "|")
            guard signature != routeSignature else { return }
            routeSignature = signature
            let oldRoutes = map.overlays.compactMap { $0 as? MKGeodesicPolyline }
            map.removeOverlays(oldRoutes)
            map.removeAnnotations(map.annotations.filter { $0.title == "Farelin home" })
            guard let homeCoordinate else { return }
            let home = MKPointAnnotation()
            home.coordinate = homeCoordinate
            home.title = "Farelin home"
            map.addAnnotation(home)
            for code in routeCodes {
                guard let destination = countryCenter(code) else { continue }
                var coordinates = [homeCoordinate, destination]
                map.addOverlay(MKGeodesicPolyline(coordinates: &coordinates, count: coordinates.count), level: .aboveLabels)
            }
        }

        private func countryCenter(_ code: String) -> CLLocationCoordinate2D? {
            guard let polygons = overlaysByCode[code], let largest = polygons.max(by: {
                $0.boundingMapRect.size.width * $0.boundingMapRect.size.height
                    < $1.boundingMapRect.size.width * $1.boundingMapRect.size.height
            }) else { return nil }
            return MKMapPoint(x: largest.boundingMapRect.midX, y: largest.boundingMapRect.midY).coordinate
        }
    }
}
