import MapKit
import SceneKit
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
    @Environment(\.scenePhase) private var scenePhase
    @State private var autoRotate = true
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
            FarelinSectionLabel(title: "MY WORLD", accented: true)
            Text("The places that made you.")
                .font(.system(size: 29, weight: .bold, design: .rounded))
                .tracking(-0.8)
            Text("Turn the Earth. Tap a place. Make it yours.")
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
                isRotating: autoRotate && isActive && scenePhase == .active && !reduceMotion && !ProcessInfo.processInfo.isLowPowerModeEnabled,
                colorScheme: colorScheme,
                onSelect: store.select,
                onInteract: { autoRotate = false }
            )
            .aspectRatio(1, contentMode: .fit)
            .frame(maxWidth: 430)
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
            FarelinSectionLabel(title: "YOUR FOOTPRINT")
            HStack(alignment: .firstTextBaseline) {
                Text("\(stats.countriesVisited)")
                    .font(.system(size: 44, weight: .bold, design: .rounded).monospacedDigit())
                Text("countries visited")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Spacer()
                Text(String(format: "%.1f%%", stats.worldExploredPercentage))
                    .font(.title3.monospacedDigit().weight(.semibold))
                    .foregroundStyle(FarelinColor.mint)
            }
            Divider()
            HStack(spacing: 16) {
                WorldStat(value: "\(stats.countriesLivedIn)", label: "Lived in")
                WorldStat(value: "\(stats.wishlistCountries)", label: "Wishlist")
                WorldStat(value: "\(stats.continentsVisited)", label: "Continents")
            }
            Text("Your history stays in sync with Farelin on the web.")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .contentTransition(.numericText())
    }

    private var countryBrowser: some View {
        VStack(alignment: .leading, spacing: 12) {
            FarelinSectionLabel(title: "FIND A COUNTRY")
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
                    Divider()
                }
            }
            Text("Browse the full country list, or search by name or code.")
                .font(.caption)
                .foregroundStyle(.secondary)
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
                .font(.title3.monospacedDigit().weight(.semibold))
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
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
    let isRotating: Bool
    let colorScheme: ColorScheme
    let onSelect: (String) -> Void
    let onInteract: () -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(onSelect: onSelect, onInteract: onInteract)
    }

    func makeUIView(context: Context) -> SCNView {
        let view = SCNView(frame: .zero)
        view.isOpaque = false
        view.backgroundColor = .clear
        view.antialiasingMode = .multisampling2X
        view.preferredFramesPerSecond = 60
        view.rendersContinuously = false
        view.allowsCameraControl = false
        let scene = SCNScene()
        scene.background.contents = UIColor.clear
        let sphere = SCNSphere(radius: 1)
        sphere.segmentCount = 144
        let material = SCNMaterial()
        material.lightingModel = .physicallyBased
        material.roughness.contents = NSNumber(value: 0.85)
        material.metalness.contents = NSNumber(value: 0.03)
        sphere.firstMaterial = material
        let earth = SCNNode(geometry: sphere)
        earth.categoryBitMask = 1
        earth.eulerAngles = SCNVector3(0.45, -0.08, 0)
        let gridSphere = SCNSphere(radius: 1.012)
        gridSphere.segmentCount = 48
        let gridMaterial = SCNMaterial()
        gridMaterial.lightingModel = .constant
        gridMaterial.fillMode = .lines
        gridMaterial.isDoubleSided = true
        gridMaterial.writesToDepthBuffer = false
        gridMaterial.transparency = 0.18
        gridSphere.firstMaterial = gridMaterial
        let wireframe = SCNNode(geometry: gridSphere)
        wireframe.categoryBitMask = 2 // decorative: country taps hit the base sphere
        earth.addChildNode(wireframe)
        scene.rootNode.addChildNode(earth)

        let camera = SCNNode()
        camera.camera = SCNCamera()
        camera.camera?.fieldOfView = 48
        camera.position = SCNVector3(0, 0, 3.25)
        scene.rootNode.addChildNode(camera)
        view.pointOfView = camera

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
        view.scene = scene
        context.coordinator.earth = earth
        context.coordinator.wireframe = wireframe
        context.coordinator.camera = camera
        context.coordinator.geometry = EarthCountryGeometry.load(alpha3ToCode: countryCodesByAlpha3)
        context.coordinator.installGestures(on: view)
        return view
    }

    func updateUIView(_ view: SCNView, context: Context) {
        context.coordinator.onSelect = onSelect
        context.coordinator.onInteract = onInteract
        context.coordinator.update(
            view: view, states: countryStates, selected: selectedCode,
            home: homeCoordinate, light: colorScheme == .light
        )
        context.coordinator.setRotating(isRotating, view: view)
    }

    static func dismantleUIView(_ view: SCNView, coordinator: Coordinator) {
        coordinator.stopRendering()
    }

    @MainActor
    final class Coordinator: NSObject, UIGestureRecognizerDelegate {
        var onSelect: (String) -> Void
        var onInteract: () -> Void
        var earth: SCNNode?
        var wireframe: SCNNode?
        var camera: SCNNode?
        var geometry = EarthCountryGeometry(polygons: [])
        private var styleSignature = ""
        private var displayLink: CADisplayLink?
        private var lastFrame: CFTimeInterval?

        init(onSelect: @escaping (String) -> Void, onInteract: @escaping () -> Void) {
            self.onSelect = onSelect
            self.onInteract = onInteract
        }

        func installGestures(on view: SCNView) {
            let pan = UIPanGestureRecognizer(target: self, action: #selector(didPan(_:)))
            pan.delegate = self
            view.addGestureRecognizer(pan)
            let pinch = UIPinchGestureRecognizer(target: self, action: #selector(didPinch(_:)))
            pinch.delegate = self
            view.addGestureRecognizer(pinch)
            let tap = UITapGestureRecognizer(target: self, action: #selector(didTap(_:)))
            tap.require(toFail: pan)
            tap.require(toFail: pinch)
            view.addGestureRecognizer(tap)
        }

        func update(
            view: SCNView, states: [String: String], selected: String?,
            home: CLLocationCoordinate2D?, light: Bool
        ) {
            let signature = states.keys.sorted().map { "\($0):\(states[$0] ?? "")" }.joined(separator: ",")
                + "|\(selected ?? "none")|\(light)|\(home?.latitude ?? 0),\(home?.longitude ?? 0)"
            guard signature != styleSignature else { return }
            styleSignature = signature
            view.backgroundColor = .clear
            view.scene?.background.contents = UIColor.clear
            wireframe?.geometry?.firstMaterial?.diffuse.contents = light
                ? UIColor(red: 0.51, green: 0.60, blue: 0.64, alpha: 1)
                : UIColor(red: 0.09, green: 0.15, blue: 0.19, alpha: 1)
            earth?.geometry?.firstMaterial?.diffuse.contents =
                geometry.texture(states: states, selected: selected, home: home, light: light)
        }

        func setRotating(_ enabled: Bool, view: SCNView) {
            view.rendersContinuously = enabled
            guard enabled else { stopRendering(); return }
            guard displayLink == nil else { return }
            let link = CADisplayLink(target: self, selector: #selector(renderFrame(_:)))
            let maximum = Float(view.window?.screen.maximumFramesPerSecond ?? 60)
            view.preferredFramesPerSecond = Int(maximum)
            link.preferredFrameRateRange = CAFrameRateRange(minimum: 30, maximum: maximum, preferred: maximum)
            link.add(to: .main, forMode: .common)
            displayLink = link
        }

        func stopRendering() {
            displayLink?.invalidate()
            displayLink = nil
            lastFrame = nil
        }

        @objc private func renderFrame(_ link: CADisplayLink) {
            defer { lastFrame = link.timestamp }
            guard let previous = lastFrame, let earth else { return }
            let delta = min(0.05, max(0, link.timestamp - previous))
            SCNTransaction.begin()
            SCNTransaction.disableActions = true
            earth.eulerAngles.y += Float(delta) * 0.035
            SCNTransaction.commit()
        }

        @objc private func didPan(_ gesture: UIPanGestureRecognizer) {
            guard let view = gesture.view, let earth else { return }
            if gesture.state == .began { stopRendering(); onInteract() }
            guard gesture.state == .changed else { return }
            let delta = gesture.translation(in: view)
            earth.eulerAngles.y += Float(delta.x / max(view.bounds.width, 1)) * 3.2
            earth.eulerAngles.x = min(0.8, max(-0.8,
                earth.eulerAngles.x + Float(delta.y / max(view.bounds.height, 1)) * 2))
            gesture.setTranslation(.zero, in: view)
        }

        @objc private func didPinch(_ gesture: UIPinchGestureRecognizer) {
            guard let camera else { return }
            if gesture.state == .began { stopRendering(); onInteract() }
            guard gesture.state == .changed else { return }
            camera.position.z = Float(min(4.8, max(2.35, Double(camera.position.z) / gesture.scale)))
            gesture.scale = 1
        }

        @objc private func didTap(_ gesture: UITapGestureRecognizer) {
            guard let view = gesture.view as? SCNView, let earth,
                  let hit = view.hitTest(gesture.location(in: view), options: [
                    .rootNode: earth, .categoryBitMask: NSNumber(value: 1)
                  ]).first,
                  hit.node == earth else { return }
            let coordinate = EarthCountryGeometry.coordinate(at: hit.localCoordinates)
            if let code = geometry.country(at: coordinate.latitude, longitude: coordinate.longitude) {
                onSelect(code)
            }
        }

        func gestureRecognizer(
            _ gestureRecognizer: UIGestureRecognizer,
            shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer
        ) -> Bool { false }
    }
}

struct EarthCountryGeometry {
    @MainActor private static var cached: (signature: String, geometry: EarthCountryGeometry)?

    struct Polygon {
        let code: String
        let selectable: Bool
        let points: [CGPoint] // longitude/latitude; longitude unwrapped over the date line
        var holes: [[CGPoint]] = []

        func contains(latitude: Double, longitude: Double) -> Bool {
            Self.ringContains(points, latitude: latitude, longitude: longitude)
                && !holes.contains { Self.ringContains($0, latitude: latitude, longitude: longitude) }
        }

        private static func ringContains(_ ring: [CGPoint], latitude: Double, longitude: Double) -> Bool {
            guard ring.count >= 3 else { return false }
            // Cheap latitude bound before point-in-polygon, with no temporary
            // arrays allocated by filtering the full catalogue on every tap.
            guard latitude >= ring.reduce(90.0, { min($0, Double($1.y)) }),
                  latitude <= ring.reduce(-90.0, { max($0, Double($1.y)) }) else { return false }
            let base = Double(ring[0].x)
            let aligned = longitude + 360 * ((base - longitude) / 360).rounded()
            for x in [aligned - 360, aligned, aligned + 360] {
                var inside = false
                var previous = ring[ring.count - 1]
                for point in ring {
                    let py = Double(point.y), previousY = Double(previous.y)
                    if (py > latitude) != (previousY > latitude) {
                        let crossing = Double(point.x) +
                            (latitude - py) * (Double(previous.x) - Double(point.x)) / (previousY - py)
                        if x < crossing { inside.toggle() }
                    }
                    previous = point
                }
                if inside { return true }
            }
            return false
        }

        var approximateArea: Double {
            let xs = points.map(\.x), ys = points.map(\.y)
            return Double((xs.max() ?? 0) - (xs.min() ?? 0)) *
                Double((ys.max() ?? 0) - (ys.min() ?? 0))
        }
    }

    let polygons: [Polygon]

    static func coordinate(at point: SCNVector3) -> CLLocationCoordinate2D {
        let x = Double(point.x), y = Double(point.y), z = Double(point.z)
        let radius = sqrt(x * x + y * y + z * z)
        guard radius > 0 else { return CLLocationCoordinate2D(latitude: 0, longitude: 0) }
        return CLLocationCoordinate2D(latitude: asin(min(1, max(-1, y / radius))) * 180 / .pi,
                                      longitude: atan2(x, z) * 180 / .pi)
    }

    func country(at latitude: Double, longitude: Double) -> String? {
        guard latitude.isFinite, longitude.isFinite, abs(latitude) <= 90 else { return nil }
        var best: Polygon?
        for polygon in polygons where polygon.selectable {
            if polygon.contains(latitude: latitude, longitude: longitude),
               best == nil || polygon.approximateArea < best!.approximateArea { best = polygon }
        }
        return best?.code
    }

    @MainActor static func load(alpha3ToCode: [String: String]) -> EarthCountryGeometry {
        let signature = alpha3ToCode.keys.sorted()
            .map { "\($0):\(alpha3ToCode[$0] ?? "")" }.joined(separator: ",")
        if let cached, cached.signature == signature { return cached.geometry }
        guard let url = Bundle.main.url(forResource: "NaturalEarthCountries", withExtension: "geojson"),
              let data = try? Data(contentsOf: url),
              let document = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let features = document["features"] as? [[String: Any]] else {
            return EarthCountryGeometry(polygons: [])
        }
        let validCodes = Set(alpha3ToCode.values)
        var polygons: [Polygon] = []
        for feature in features {
            guard let json = feature["properties"] as? [String: Any],
                  let shape = feature["geometry"] as? [String: Any],
                  let iso2 = json["ISO_A2"] as? String,
                  let alpha3 = json["ADM0_A3"] as? String else { continue }
            let code = iso2.count == 2 && iso2 != "-99" ? iso2 : alpha3ToCode[alpha3]
            guard let code else { continue }
            let groups: [[[[Double]]]]
            if shape["type"] as? String == "Polygon", let rings = shape["coordinates"] as? [[[Double]]] {
                groups = [rings]
            } else if shape["type"] as? String == "MultiPolygon", let multi = shape["coordinates"] as? [[[[Double]]]] {
                groups = multi
            } else { continue }
            for rings in groups {
                guard let outer = rings.first else { continue }
                let points = unwrapRing(outer)
                guard points.count >= 3 else { continue }
                polygons.append(Polygon(code: code, selectable: validCodes.contains(code), points: points,
                                        holes: rings.dropFirst().map(unwrapRing)))
            }
        }
        let geography = EarthCountryGeometry(polygons: polygons)
        cached = (signature, geography)
        return geography
    }

    static func unwrapRing(_ raw: [[Double]]) -> [CGPoint] {
        var points: [CGPoint] = []
        for coordinate in raw where coordinate.count >= 2 {
            var longitude = coordinate[0]
            if let previous = points.last {
                while longitude - Double(previous.x) > 180 { longitude -= 360 }
                while longitude - Double(previous.x) < -180 { longitude += 360 }
            }
            points.append(CGPoint(x: longitude, y: coordinate[1]))
        }
        // A closed ring winding a full turn encloses a pole. Closing its
        // unwrapped coastline by a chord paints/selects the complement. Close
        // along the relevant pole instead; this is a ring-topology rule, not
        // an Antarctica country/material exception. Decode raw GeoJSON because
        // Mercator MKMapPoint projection also clips polar coordinates.
        if let first = points.first, let last = points.last, abs(last.x - first.x) > 359 {
            let pole: CGFloat = points.reduce(0) { $0 + $1.y } < 0 ? -90 : 90
            points.append(CGPoint(x: last.x, y: pole))
            points.append(CGPoint(x: first.x, y: pole))
            points.append(first)
        }
        return points
    }

    func texture(
        states: [String: String], selected: String?,
        home: CLLocationCoordinate2D? = nil, light: Bool
    ) -> UIImage {
        // Higher-resolution equirectangular country layer; the web globe uses
        // the same Natural Earth scale but renders its polygons as meshes.
        let width: CGFloat = 2048, height: CGFloat = 1024
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = true
        return UIGraphicsImageRenderer(size: CGSize(width: width, height: height), format: format).image { output in
            let ctx = output.cgContext
            let sea = light
                ? UIColor(red: 0.85, green: 0.92, blue: 0.94, alpha: 1)
                : UIColor(red: 0.055, green: 0.115, blue: 0.155, alpha: 1)
            ctx.setFillColor(sea.cgColor)
            ctx.fill(CGRect(x: 0, y: 0, width: width, height: height))
            ctx.setStrokeColor((light ? UIColor.black : UIColor.white).withAlphaComponent(0.07).cgColor)
            ctx.setLineWidth(1)
            for x in stride(from: 0, through: Int(width), by: 128) {
                ctx.move(to: CGPoint(x: CGFloat(x), y: 0)); ctx.addLine(to: CGPoint(x: CGFloat(x), y: height))
            }
            for y in stride(from: 0, through: Int(height), by: 128) {
                ctx.move(to: CGPoint(x: 0, y: CGFloat(y))); ctx.addLine(to: CGPoint(x: width, y: CGFloat(y)))
            }
            ctx.strokePath()
            for polygon in polygons {
                let color: UIColor
                switch states[polygon.code] {
                case "lived": color = UIColor(FarelinColor.coral)
                case "visited": color = UIColor(FarelinColor.mint)
                case "wishlist": color = UIColor(FarelinColor.gold)
                default:
                    color = light
                        ? UIColor(red: 0.51, green: 0.60, blue: 0.64, alpha: 1)
                        : UIColor(red: 0.37, green: 0.50, blue: 0.56, alpha: 1)
                }
                ctx.setFillColor(color.cgColor)
                ctx.setStrokeColor((light ? UIColor.white : UIColor.black)
                    .withAlphaComponent(polygon.code == selected ? 0.85 : 0.38).cgColor)
                ctx.setLineWidth(polygon.code == selected ? 2.6 : 0.9)
                for offset in [-width, 0, width] {
                    guard let first = polygon.points.first else { continue }
                    ctx.beginPath()
                    ctx.move(to: pixel(first, width: width, height: height, offset: offset))
                    for point in polygon.points.dropFirst() {
                        ctx.addLine(to: pixel(point, width: width, height: height, offset: offset))
                    }
                    ctx.closePath()
                    for hole in polygon.holes {
                        guard let start = hole.first else { continue }
                        ctx.move(to: pixel(start, width: width, height: height, offset: offset))
                        for point in hole.dropFirst() {
                            ctx.addLine(to: pixel(point, width: width, height: height, offset: offset))
                        }
                        ctx.closePath()
                    }
                    ctx.drawPath(using: .eoFillStroke)
                }
            }
            // A subtle triangular route-grid echoes the web globe's polygon
            // surface without adding a second expensive SceneKit mesh.
            ctx.setStrokeColor((light ? UIColor.black : UIColor.white).withAlphaComponent(0.065).cgColor)
            ctx.setLineWidth(0.75)
            for y in stride(from: 0, to: Int(height), by: 128) {
                for x in stride(from: 0, to: Int(width), by: 128) {
                    ctx.move(to: CGPoint(x: CGFloat(x), y: CGFloat(y)))
                    ctx.addLine(to: CGPoint(x: CGFloat(x + 128), y: CGFloat(y + 128)))
                }
            }
            ctx.strokePath()
            // Stable golden-spiral dots mirror RouteGlobe's point sphere.
            // Drawing into one texture keeps the native iPhone globe to a
            // single country-layer draw call rather than 700 SceneKit nodes.
            ctx.setFillColor((light
                ? UIColor(red: 0.32, green: 0.42, blue: 0.47, alpha: 0.55)
                : UIColor(red: 0.24, green: 0.35, blue: 0.43, alpha: 0.72)).cgColor)
            for index in 0..<700 {
                let vertical = 1 - Double(index) / 699 * 2
                let latitude = asin(vertical) * 180 / .pi
                let longitude = (Double(index) * 2.399963 * 180 / .pi)
                    .truncatingRemainder(dividingBy: 360) - 180
                let dot = pixel(CGPoint(x: longitude, y: latitude), width: width, height: height, offset: 0)
                ctx.fillEllipse(in: CGRect(x: dot.x - 1.25, y: dot.y - 1.25, width: 2.5, height: 2.5))
            }
            if let home {
                let origin = CGPoint(x: home.longitude, y: home.latitude)
                let wishlist = states.filter { $0.value == "wishlist" }.keys.sorted().prefix(4)
                ctx.setStrokeColor(UIColor(FarelinColor.mint).withAlphaComponent(0.68).cgColor)
                ctx.setLineWidth(1.8)
                ctx.setLineDash(phase: 0, lengths: [5, 5])
                for code in wishlist {
                    guard let destination = countryCenter(code) else { continue }
                    var end = destination
                    while end.x - origin.x > 180 { end.x -= 360 }
                    while end.x - origin.x < -180 { end.x += 360 }
                    for offset in [-width, 0, width] {
                        let startPixel = pixel(origin, width: width, height: height, offset: offset)
                        let endPixel = pixel(end, width: width, height: height, offset: offset)
                        ctx.beginPath()
                        ctx.move(to: startPixel)
                        ctx.addQuadCurve(
                            to: endPixel,
                            control: CGPoint(x: (startPixel.x + endPixel.x) / 2,
                                             y: min(startPixel.y, endPixel.y) - 34)
                        )
                        ctx.strokePath()
                    }
                }
                ctx.setLineDash(phase: 0, lengths: [])
                let marker = pixel(origin, width: width, height: height, offset: 0)
                ctx.setFillColor(UIColor(FarelinColor.coral).cgColor)
                ctx.fillEllipse(in: CGRect(x: marker.x - 4, y: marker.y - 4, width: 8, height: 8))
            }
        }
    }

    private func countryCenter(_ code: String) -> CGPoint? {
        guard let polygon = polygons.filter({ $0.code == code })
            .max(by: { $0.approximateArea < $1.approximateArea }) else { return nil }
        let xs = polygon.points.map(\.x), ys = polygon.points.map(\.y)
        return CGPoint(x: ((xs.min() ?? 0) + (xs.max() ?? 0)) / 2,
                       y: ((ys.min() ?? 0) + (ys.max() ?? 0)) / 2)
    }

    private func pixel(_ point: CGPoint, width: CGFloat, height: CGFloat, offset: CGFloat) -> CGPoint {
        CGPoint(x: (point.x + 180) / 360 * width + offset,
                y: (90 - point.y) / 180 * height)
    }
}
