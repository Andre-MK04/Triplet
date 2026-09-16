import Foundation

struct HealthResponse: Decodable, Sendable {
    let status: String
}

enum APIError: LocalizedError, Sendable {
    case invalidResponse
    case unavailable
    case unauthorized
    case server(message: String, statusCode: Int)

    var errorDescription: String? {
        switch self {
        case .invalidResponse: "Farelin returned an unexpected response."
        case .unavailable: "Farelin could not be reached. Check your connection and try again."
        case .unauthorized: "Your session has expired. Please sign in again."
        case .server(let message, _): message
        }
    }
}

protocol NativeAuthServicing: Sendable {
    func legalVersions() async throws -> LegalVersions
    func nativeLogin(email: String, password: String) async throws -> NativeAuthTokens
    func nativeSignup(
        email: String,
        password: String,
        displayName: String?,
        legal: LegalVersions
    ) async throws -> NativeAuthTokens
    func nativeRefresh(refreshToken: String) async throws -> NativeAuthTokens
    func nativeLogout(refreshToken: String) async throws
    func currentUser() async throws -> AuthUser
    func requestVerificationCode() async throws -> VerificationDelivery
    func confirmVerificationCode(_ code: String) async throws -> AuthUser
    func setAccessToken(_ token: String?) async
}

actor APIClient: NativeAuthServicing, NativeAccountServicing, NativeIdentityServicing, NativePushServicing, WatchManagementServicing, DashboardServicing, TravelProfileServicing, TripSearchServicing, OpportunityServicing, TripDetailServicing, TravelMapServicing, NativeWatchCreating, NativeFareSaving {
    private let baseURL: URL
    private let session: URLSession
    private var accessToken: String?

    init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    func health() async throws -> HealthResponse {
        try await send(path: "health", method: "GET", response: HealthResponse.self)
    }

    func pushStatus() async throws -> NativePushStatus {
        try await send(path: "me/push/status", method: "GET", authenticated: true, response: NativePushStatus.self)
    }
    func registerPush(_ registration: NativePushRegistration) async throws -> NativePushDevice {
        try await send(path: "me/push/devices", method: "POST", body: registration, authenticated: true, response: NativePushDevice.self)
    }
    func disconnectPush(id: String) async throws {
        _ = try await send(path: "me/push/devices/\(id)", method: "DELETE", authenticated: true, response: MutationAcknowledgement.self)
    }

    func identityProviders() async throws -> NativeIdentityProviders {
        try await send(path: "auth/native/providers", method: "GET", response: NativeIdentityProviders.self)
    }
    func identityChallenge() async throws -> NativeIdentityChallenge {
        try await send(path: "auth/native/challenge", method: "POST", body: EmptyPayload(), response: NativeIdentityChallenge.self)
    }
    func identityLogin(provider: String, payload: NativeIdentityPayload) async throws -> NativeAuthTokens {
        try await send(path: "auth/native/oauth/\(provider)", method: "POST", body: payload, response: NativeAuthTokens.self)
    }

    func forgotPassword(email: String) async throws {
        _ = try await send(path: "auth/forgot-password", method: "POST",
                           body: EmailPayload(email: email), response: MessageResponse.self)
    }

    func resetPassword(token: String, password: String) async throws {
        _ = try await send(path: "auth/reset-password", method: "POST",
                           body: ResetPasswordPayload(token: token, newPassword: password), response: MutationAcknowledgement.self)
    }

    func changePassword(current: String, new: String) async throws {
        _ = try await send(path: "auth/change-password", method: "POST",
                           body: ChangePasswordPayload(currentPassword: current, newPassword: new),
                           authenticated: true, response: MutationAcknowledgement.self)
    }

    func deleteAccount() async throws {
        _ = try await send(path: "auth/me", method: "DELETE", authenticated: true, response: MutationAcknowledgement.self)
    }

    func exportAccount() async throws -> AccountExport {
        try await send(path: "me/export", method: "GET", authenticated: true, response: AccountExport.self)
    }

    func dashboard() async throws -> DashboardResponse {
        try await send(
            path: "me/dashboard",
            method: "GET",
            authenticated: true,
            response: DashboardResponse.self
        )
    }

    func createWatch(_ request: NativeSavedWatchRequest) async throws -> SavedWatchSummary {
        try await send(
            path: "me/saved-searches",
            method: "POST",
            body: request,
            authenticated: true,
            response: SavedWatchSummary.self
        )
    }

    func watch(id: String) async throws -> NativeWatchDetail {
        try await send(path: "me/saved-searches/\(id)", method: "GET", authenticated: true, response: NativeWatchDetail.self)
    }
    func updateWatch(id: String, update: NativeWatchUpdate) async throws -> NativeWatchDetail {
        try await send(path: "me/saved-searches/\(id)", method: "PATCH", body: update, authenticated: true, response: NativeWatchDetail.self)
    }
    func previewWatch(id: String) async throws -> NativeWatchPreview {
        try await send(path: "me/saved-searches/\(id)/preview", method: "POST", body: EmptyPayload(), authenticated: true, response: NativeWatchPreview.self)
    }
    func watchInsights(id: String) async throws -> NativeWatchInsights {
        try await send(path: "me/saved-searches/\(id)/insights", method: "GET", authenticated: true, response: NativeWatchInsights.self)
    }
    func updateWatchRoute(id: String, update: NativeWatchRouteUpdate) async throws -> NativeWatchDetail {
        try await send(path: "me/saved-searches/\(id)", method: "PATCH", body: update, authenticated: true, response: NativeWatchDetail.self)
    }
    func watchAirports(query: String) async throws -> [AirportResult] {
        try await searchAirports(query, latitude: nil, longitude: nil)
    }
    func watchPlaces(query: String) async throws -> [FlightPlaceResult] { try await searchPlaces(query) }

    func savedFares() async throws -> [SavedFareSummary] {
        try await send(path: "me/saved-fares", method: "GET", authenticated: true, response: [SavedFareSummary].self)
    }

    func saveFare(suggestionId: String) async throws -> SavedFareSummary {
        try await send(path: "me/saved-fares/\(suggestionId)", method: "POST",
                       body: EmptyPayload(), authenticated: true, response: SavedFareSummary.self)
    }

    func deleteSavedFare(id: String) async throws {
        _ = try await send(path: "me/saved-fares/\(id)", method: "DELETE",
                           authenticated: true, response: SavedFareDeletionResponse.self)
    }

    func pauseWatch(id: String) async throws -> SavedWatchSummary {
        try await send(
            path: "me/saved-searches/\(id)/pause",
            method: "POST",
            body: EmptyPayload(),
            authenticated: true,
            response: SavedWatchSummary.self
        )
    }

    func resumeWatch(id: String) async throws -> SavedWatchSummary {
        try await send(
            path: "me/saved-searches/\(id)/resume",
            method: "POST",
            body: EmptyPayload(),
            authenticated: true,
            response: SavedWatchSummary.self
        )
    }

    func deleteWatch(id: String) async throws {
        _ = try await send(
            path: "me/saved-searches/\(id)",
            method: "DELETE",
            authenticated: true,
            response: MutationAcknowledgement.self
        )
    }

    func travelProfile() async throws -> TravelProfileResponse {
        try await send(
            path: "me/travel-profile",
            method: "GET",
            authenticated: true,
            response: TravelProfileResponse.self
        )
    }

    func updateTravelProfile(_ payload: TravelProfilePayload) async throws -> TravelProfileResponse {
        try await send(
            path: "me/travel-profile",
            method: "PUT",
            body: payload,
            authenticated: true,
            response: TravelProfileResponse.self
        )
    }

    func searchLocations(_ query: String) async throws -> [LocationResult] {
        try await send(
            path: "locations/search",
            method: "GET",
            queryItems: [URLQueryItem(name: "q", value: query)],
            response: [LocationResult].self
        )
    }

    func recommendedAirports(
        latitude: Double,
        longitude: Double,
        maxDistanceKm: Int
    ) async throws -> [AirportResult] {
        try await send(
            path: "airports/recommended",
            method: "GET",
            queryItems: [
                URLQueryItem(name: "lat", value: String(latitude)),
                URLQueryItem(name: "lon", value: String(longitude)),
                URLQueryItem(name: "maxDistanceKm", value: String(maxDistanceKm)),
                URLQueryItem(name: "originsOnly", value: "true"),
            ],
            response: [AirportResult].self
        )
    }

    func searchAirports(
        _ query: String,
        latitude: Double?,
        longitude: Double?
    ) async throws -> [AirportResult] {
        var queryItems = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "originsOnly", value: "true"),
        ]
        if let latitude, let longitude {
            queryItems.append(URLQueryItem(name: "lat", value: String(latitude)))
            queryItems.append(URLQueryItem(name: "lon", value: String(longitude)))
        }
        return try await send(
            path: "airports/search",
            method: "GET",
            queryItems: queryItems,
            response: [AirportResult].self
        )
    }

    func searchTrips(_ request: FarelinAISearchRequest) async throws -> FarelinAISearchResponse {
        try await send(
            path: "ai/search",
            method: "POST",
            body: request,
            authenticated: true,
            response: FarelinAISearchResponse.self
        )
    }

    func opportunities() async throws -> NativeOpportunityFeed {
        try await send(path: "me/opportunities", method: "GET", authenticated: true, response: NativeOpportunityFeed.self)
    }

    func advancedSearch(_ request: FarelinAdvancedSearchRequest) async throws -> FarelinAISearchResponse {
        try await send(
            path: "trips/advanced-search",
            method: "POST",
            body: request,
            authenticated: true,
            timeoutInterval: 60,
            response: FarelinAISearchResponse.self
        )
    }

    func searchPlaces(_ query: String) async throws -> [FlightPlaceResult] {
        try await send(
            path: "places/search",
            method: "GET",
            queryItems: [URLQueryItem(name: "q", value: query)],
            response: [FlightPlaceResult].self
        )
    }

    func tripSuggestion(id: String) async throws -> TripSuggestionResponse {
        try await send(
            path: "trips/suggestions/\(id)",
            method: "GET",
            authenticated: true,
            response: TripSuggestionResponse.self
        )
    }

    func generateItinerary(suggestionID: String) async throws -> ItineraryGenerationResponse {
        try await send(
            path: "trips/suggestions/\(suggestionID)/plan",
            method: "POST",
            body: EmptyPayload(),
            authenticated: true,
            timeoutInterval: 60,
            response: ItineraryGenerationResponse.self
        )
    }

    func countryCatalog() async throws -> CountryCatalogResponse {
        try await send(
            path: "countries",
            method: "GET",
            response: CountryCatalogResponse.self
        )
    }

    func travelMap() async throws -> TravelMapResponse {
        try await send(
            path: "me/travel-map",
            method: "GET",
            authenticated: true,
            response: TravelMapResponse.self
        )
    }

    func updateCountry(_ code: String, update: CountryStateUpdate) async throws -> TravelMapCountry {
        try await send(
            path: "me/travel-map/countries/\(code)",
            method: "PATCH",
            body: update,
            authenticated: true,
            response: TravelMapCountry.self
        )
    }

    func setAccessToken(_ token: String?) {
        accessToken = token
    }

    func legalVersions() async throws -> LegalVersions {
        let response = try await send(path: "billing/plans", method: "GET", response: PlansEnvelope.self)
        return LegalVersions(termsVersion: response.termsVersion, privacyVersion: response.privacyVersion)
    }

    func nativeLogin(email: String, password: String) async throws -> NativeAuthTokens {
        try await send(
            path: "auth/native/login",
            method: "POST",
            body: LoginPayload(email: email, password: password),
            response: NativeAuthTokens.self
        )
    }

    func nativeSignup(
        email: String,
        password: String,
        displayName: String?,
        legal: LegalVersions
    ) async throws -> NativeAuthTokens {
        try await send(
            path: "auth/native/signup",
            method: "POST",
            body: SignupPayload(
                email: email,
                password: password,
                displayName: displayName,
                acceptedTermsVersion: legal.termsVersion,
                acknowledgedPrivacyVersion: legal.privacyVersion
            ),
            response: NativeAuthTokens.self
        )
    }

    func nativeRefresh(refreshToken: String) async throws -> NativeAuthTokens {
        try await send(
            path: "auth/native/refresh",
            method: "POST",
            body: RefreshPayload(refreshToken: refreshToken),
            response: NativeAuthTokens.self
        )
    }

    func nativeLogout(refreshToken: String) async throws {
        _ = try await send(
            path: "auth/native/logout",
            method: "POST",
            body: RefreshPayload(refreshToken: refreshToken),
            response: LogoutResponse.self
        )
    }

    func currentUser() async throws -> AuthUser {
        let response = try await send(
            path: "auth/me",
            method: "GET",
            authenticated: true,
            response: AuthEnvelope.self
        )
        return response.user
    }

    func requestVerificationCode() async throws -> VerificationDelivery {
        try await send(
            path: "auth/native/verify-email/request",
            method: "POST",
            authenticated: true,
            response: VerificationDelivery.self
        )
    }

    func confirmVerificationCode(_ code: String) async throws -> AuthUser {
        let response = try await send(
            path: "auth/native/verify-email/confirm",
            method: "POST",
            body: VerificationCodePayload(code: code),
            authenticated: true,
            response: AuthEnvelope.self
        )
        return response.user
    }

    private func send<Response: Decodable & Sendable>(
        path: String,
        method: String,
        queryItems: [URLQueryItem] = [],
        authenticated: Bool = false,
        timeoutInterval: TimeInterval = 20,
        response: Response.Type
    ) async throws -> Response {
        try await send(
            path: path,
            method: method,
            queryItems: queryItems,
            body: Optional<EmptyPayload>.none,
            authenticated: authenticated,
            timeoutInterval: timeoutInterval,
            response: response
        )
    }

    private func send<Body: Encodable & Sendable, Response: Decodable & Sendable>(
        path: String,
        method: String,
        queryItems: [URLQueryItem] = [],
        body: Body?,
        authenticated: Bool = false,
        timeoutInterval: TimeInterval = 20,
        response: Response.Type
    ) async throws -> Response {
        guard var components = URLComponents(
            url: baseURL.appending(path: path),
            resolvingAgainstBaseURL: false
        ) else {
            throw APIError.invalidResponse
        }
        if !queryItems.isEmpty {
            components.queryItems = queryItems
        }
        guard let url = components.url else { throw APIError.invalidResponse }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = timeoutInterval
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let body {
            request.httpBody = try JSONEncoder().encode(body)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        if authenticated {
            guard let accessToken else { throw APIError.unauthorized }
            request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        }

        do {
            let (data, urlResponse) = try await session.data(for: request)
            guard let http = urlResponse as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }
            if http.statusCode == 401 {
                throw APIError.unauthorized
            }
            guard (200 ..< 300).contains(http.statusCode) else {
                let detail = (try? JSONDecoder().decode(APIErrorEnvelope.self, from: data).detail)
                    ?? "Farelin could not complete that request."
                let message = http.statusCode == 404 && detail == "Not Found"
                    ? "This feature isn't available on the connected Farelin server yet. Please try again after the app and server are updated."
                    : detail
                throw APIError.server(message: message, statusCode: http.statusCode)
            }
            do {
                return try JSONDecoder().decode(Response.self, from: data)
            } catch {
                throw APIError.invalidResponse
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw APIError.unavailable
        }
    }
}

private struct EmptyPayload: Encodable, Sendable {}
private struct EmailPayload: Encodable, Sendable { let email: String }
private struct ResetPasswordPayload: Encodable, Sendable { let token: String; let newPassword: String }
private struct ChangePasswordPayload: Encodable, Sendable { let currentPassword: String; let newPassword: String }
private struct MessageResponse: Decodable, Sendable { let message: String }
private struct APIErrorEnvelope: Decodable, Sendable { let detail: String }
private struct MutationAcknowledgement: Decodable, Sendable { let ok: Bool }
private struct SavedFareDeletionResponse: Decodable, Sendable { let deleted: Bool }
